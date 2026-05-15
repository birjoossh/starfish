"""MTO database loader — T+1 UPDATE pass on fact_eod_price.

The bhavcopy loader writes fact_eod_price rows with ``delivery_qty`` /
``delivery_pct`` set to NULL. The MTO loader runs on T+1 and patches those
columns in place for the prior trading day. We do NOT insert new rows here —
the (trade_date, symbol) row must already exist from the bhavcopy load.

Idempotency: UPDATE-by-PK means re-running is a no-op for already-patched
rows. The ingestion_log row records what was touched.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Iterable

import pandas as pd
from sqlalchemy import text

from config.database import get_engine

logger = logging.getLogger(__name__)


class MTOLoader:
    """Update fact_eod_price delivery columns from an MTO DataFrame."""

    def __init__(self):
        self.engine = get_engine()

    def load(self, df: pd.DataFrame, source_file: str = "") -> dict:
        """Apply delivery rows to fact_eod_price.

        Args:
            df: DataFrame from :class:`MTOParser.parse` with columns
                ``trade_date, symbol, delivery_qty, delivery_pct``.
            source_file: Source filename written into ``ingestion_log``.

        Returns:
            Dict ``{rows_total, rows_updated, rows_failed, status}``.
        """
        if df.empty:
            logger.warning("Empty MTO DataFrame, nothing to load")
            return {
                "rows_total": 0, "rows_updated": 0,
                "rows_failed": 0, "status": "success",
            }

        with self.engine.connect() as conn:
            valid_symbols = {
                row[0] for row in conn.execute(text("SELECT symbol FROM dim_stock"))
            }

        original_count = len(df)
        df = df[df["symbol"].isin(valid_symbols)].copy()
        if df.empty:
            logger.warning("No MTO rows match dim_stock; skipping update")
            return {
                "rows_total": original_count, "rows_updated": 0,
                "rows_failed": original_count, "status": "success",
            }

        rows_total = len(df)
        rows_updated = 0
        rows_failed = 0
        error_message: str | None = None
        started_at = datetime.now()
        status = "success"

        try:
            update_sql = text("""
                UPDATE fact_eod_price
                   SET delivery_qty = :delivery_qty,
                       delivery_pct = :delivery_pct
                 WHERE trade_date = :trade_date
                   AND symbol     = :symbol
            """)

            records = self._records(df)
            with self.engine.connect() as conn:
                result = conn.execute(update_sql, records)
                rows_updated = result.rowcount
                rows_failed = rows_total - rows_updated
                conn.commit()

            if rows_updated == 0:
                status = "failed"
                error_message = (
                    "No fact_eod_price rows updated — the bhavcopy load for "
                    "this trade_date may not have run yet."
                )
            elif rows_failed > 0:
                status = "partial"

            logger.info(
                "MTO updated %d/%d rows in fact_eod_price (%d unmatched)",
                rows_updated, rows_total, rows_failed,
            )

        except Exception as e:  # pragma: no cover — DB-side failure path
            rows_failed = rows_total
            status = "failed"
            error_message = str(e)
            logger.error("MTO load failed: %s", e)

        completed_at = datetime.now()
        self._log_ingestion(
            source_file=source_file,
            rows_inserted=rows_updated,
            rows_failed=rows_failed,
            status=status,
            error_message=error_message,
            started_at=started_at,
            completed_at=completed_at,
        )

        return {
            "rows_total": rows_total,
            "rows_updated": rows_updated,
            "rows_failed": rows_failed,
            "status": status,
        }

    @staticmethod
    def _records(df: pd.DataFrame) -> list[dict]:
        records = df.to_dict("records")
        for rec in records:
            for k, v in list(rec.items()):
                if pd.isna(v):
                    rec[k] = None
                elif k == "delivery_qty" and v is not None:
                    rec[k] = int(v)
                elif k == "delivery_pct" and v is not None:
                    rec[k] = float(v)
        return records

    def _log_ingestion(
        self,
        *,
        source_file: str,
        rows_inserted: int,
        rows_failed: int,
        status: str,
        error_message: str | None,
        started_at: datetime,
        completed_at: datetime,
    ) -> None:
        try:
            log_sql = text("""
                INSERT INTO ingestion_log (
                    source_file, table_name, rows_inserted, rows_failed,
                    status, error_message, started_at, completed_at
                ) VALUES (
                    :source_file, :table_name, :rows_inserted, :rows_failed,
                    :status, :error_message, :started_at, :completed_at
                )
            """)
            with self.engine.connect() as conn:
                conn.execute(log_sql, {
                    "source_file": source_file,
                    "table_name": "fact_eod_price.delivery",
                    "rows_inserted": rows_inserted,
                    "rows_failed": rows_failed,
                    "status": status,
                    "error_message": error_message,
                    "started_at": started_at,
                    "completed_at": completed_at,
                })
                conn.commit()
        except Exception as e:
            logger.warning("Failed to write MTO ingestion log: %s", e)
