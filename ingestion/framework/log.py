"""Ingestion run logger — writes every pipeline run to ``ingestion_log``.

Uses the same ``ingestion_log`` table that the existing ``BhavcopyLoader``
already writes to, so all pipeline runs are visible in one place.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from config.database import get_engine

logger = logging.getLogger(__name__)


class IngestionLogger:
    """Write pipeline run records to the ``ingestion_log`` table.

    Both success and failure records are written. A write failure is
    **non-fatal** — the error is logged at WARNING level and swallowed so
    that a broken log table never prevents data from being ingested.

    Args:
        engine: SQLAlchemy engine. If None, uses ``get_engine()`` from
            ``config.database``.
    """

    _INSERT_SQL = text("""
        INSERT INTO ingestion_log (
            source_file, table_name, rows_inserted, rows_failed,
            status, error_message, started_at, completed_at
        ) VALUES (
            :source_file, :table_name, :rows_inserted, :rows_failed,
            :status, :error_message, :started_at, :completed_at
        )
    """)

    def __init__(self, engine: Optional[Engine] = None) -> None:
        self._engine = engine or get_engine()

    def record_success(
        self,
        trade_date: date,
        source_name: str,
        table_name: str,
        rows_inserted: int,
        started_at: datetime,
        rows_failed: int = 0,
    ) -> None:
        """Record a successful pipeline run.

        Args:
            trade_date: The trading date that was ingested.
            source_name: Human-readable source identifier (e.g. ``"bhavcopy"``).
            table_name: Target DB table (e.g. ``"fact_eod_price"``).
            rows_inserted: Number of rows inserted/updated.
            started_at: When the pipeline run started.
            rows_failed: Rows that could not be inserted (default 0).
        """
        self._write(
            source_file=f"{source_name}_{trade_date.strftime('%Y%m%d')}",
            table_name=table_name,
            rows_inserted=rows_inserted,
            rows_failed=rows_failed,
            status="success",
            error_message=None,
            started_at=started_at,
        )

    def record_failure(
        self,
        trade_date: date,
        source_name: str,
        table_name: str,
        error_message: str,
        started_at: datetime,
    ) -> None:
        """Record a failed pipeline run.

        Args:
            trade_date: The trading date that failed.
            source_name: Human-readable source identifier.
            table_name: Target DB table.
            error_message: Exception message or error description.
            started_at: When the pipeline run started.
        """
        self._write(
            source_file=f"{source_name}_{trade_date.strftime('%Y%m%d')}",
            table_name=table_name,
            rows_inserted=0,
            rows_failed=0,
            status="failed",
            error_message=error_message,
            started_at=started_at,
        )

    def _write(
        self,
        source_file: str,
        table_name: str,
        rows_inserted: int,
        rows_failed: int,
        status: str,
        error_message: Optional[str],
        started_at: datetime,
    ) -> None:
        """Internal write — swallows DB errors to stay non-fatal."""
        try:
            with self._engine.connect() as conn:
                conn.execute(
                    self._INSERT_SQL,
                    {
                        "source_file": source_file,
                        "table_name": table_name,
                        "rows_inserted": rows_inserted,
                        "rows_failed": rows_failed,
                        "status": status,
                        "error_message": error_message,
                        "started_at": started_at,
                        "completed_at": datetime.utcnow(),
                    },
                )
                conn.commit()
        except Exception as exc:
            logger.warning("IngestionLogger: failed to write log row: %s", exc)
