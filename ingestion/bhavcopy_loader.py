"""Bhavcopy database loader with idempotent upsert and ingestion log.

Loads parsed bhavcopy DataFrames into fact_eod_price using
INSERT ... ON CONFLICT DO NOTHING for idempotency.
Every load operation is recorded in ingestion_log.

Usage:
    from ingestion.bhavcopy_loader import BhavcopyLoader
    loader = BhavcopyLoader()
    stats = loader.load(df)
"""

from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd
from sqlalchemy import text

from config.database import get_engine, get_session

logger = logging.getLogger(__name__)


class BhavcopyLoader:
    """Load bhavcopy DataFrames into fact_eod_price.

    Features:
    - Idempotent: INSERT ... ON CONFLICT (trade_date, symbol) DO NOTHING
    - Ingestion logging: every run recorded in ingestion_log table
    - Row count validation: logs inserted/failed counts
    """

    def __init__(self):
        self.engine = get_engine()

    def load(self, df: pd.DataFrame, source_file: str = "") -> dict:
        """Load a bhavcopy DataFrame into fact_eod_price.

        Args:
            df: DataFrame from BhavcopyParser.parse().
            source_file: Source filename for ingestion log.

        Returns:
            Dict with keys: rows_total, rows_inserted, rows_failed, status.
        """
        if df.empty:
            logger.warning("Empty DataFrame, nothing to load")
            return {"rows_total": 0, "rows_inserted": 0, "rows_failed": 0, "status": "success"}

        # Fetch allowed symbols from dim_stock to prevent FK violations
        with self.engine.connect() as conn:
            valid_symbols = set(row[0] for row in conn.execute(text("SELECT symbol FROM dim_stock")))
            
        original_count = len(df)
        df = df[df["symbol"].isin(valid_symbols)].copy()
        logger.info(f"Filtered Bhavcopy to {len(df)} rows matching dim_stock constituents (from {original_count} total)")

        if df.empty:
            logger.warning("No rows remaining after dim_stock filter. Nothing to load.")
            return {"rows_total": original_count, "rows_inserted": 0, "rows_failed": original_count, "status": "success"}

        rows_total = len(df)
        rows_inserted = 0
        rows_failed = 0
        error_message = None
        started_at = datetime.now()

        try:
            # Use raw SQL for idempotent upsert
            upsert_sql = text("""
                INSERT INTO fact_eod_price (
                    trade_date, symbol, open, high, low, close, prev_close,
                    total_traded_qty, total_traded_value_lakh, total_trades,
                    series, delivery_qty, delivery_pct, source_file
                ) VALUES (
                    :trade_date, :symbol, :open, :high, :low, :close, :prev_close,
                    :total_traded_qty, :total_traded_value_lakh, :total_trades,
                    :series, :delivery_qty, :delivery_pct, :source_file
                )
                ON CONFLICT (trade_date, symbol) DO NOTHING
            """)

            with self.engine.connect() as conn:
                records = df.to_dict("records")

                # Convert pandas NA to None for SQLAlchemy
                for rec in records:
                    for key, val in rec.items():
                        if pd.isna(val):
                            rec[key] = None

                result = conn.execute(upsert_sql, records)
                rows_inserted = result.rowcount
                rows_failed = rows_total - rows_inserted
                conn.commit()

            status = "success" if rows_failed == 0 else "partial"
            logger.info(
                f"Loaded {rows_inserted}/{rows_total} rows into fact_eod_price "
                f"({rows_failed} duplicates skipped)"
            )

        except Exception as e:
            rows_failed = rows_total
            status = "failed"
            error_message = str(e)
            logger.error(f"Failed to load bhavcopy: {e}")

        completed_at = datetime.now()

        # Record in ingestion log
        self._log_ingestion(
            source_file=source_file,
            table_name="fact_eod_price",
            rows_inserted=rows_inserted,
            rows_failed=rows_failed,
            status=status,
            error_message=error_message,
            started_at=started_at,
            completed_at=completed_at,
        )

        return {
            "rows_total": rows_total,
            "rows_inserted": rows_inserted,
            "rows_failed": rows_failed,
            "status": status,
        }

    def _log_ingestion(
        self,
        source_file: str,
        table_name: str,
        rows_inserted: int,
        rows_failed: int,
        status: str,
        error_message: str | None,
        started_at: datetime,
        completed_at: datetime,
    ) -> None:
        """Record an ingestion run in the ingestion_log table."""
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
                    "table_name": table_name,
                    "rows_inserted": rows_inserted,
                    "rows_failed": rows_failed,
                    "status": status,
                    "error_message": error_message,
                    "started_at": started_at,
                    "completed_at": completed_at,
                })
                conn.commit()
        except Exception as e:
            # Log ingestion failure is non-fatal
            logger.warning(f"Failed to write ingestion log: {e}")
