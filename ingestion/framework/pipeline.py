"""Pipeline: orchestrates fetch → load → log for a single data source.

Usage::

    from ingestion.framework import Pipeline, HybridFetcher, EodPriceLoader

    pipeline = Pipeline(
        fetcher=HybridFetcher(http=NseHttpFetcher(SourceType.BHAVCOPY),
                               local=LocalFetcher(settings.project_root / "data/raw/bhavcopy")),
        loader=EodPriceLoader(),
        source_name="bhavcopy",
        table_name="fact_eod_price",
    )
    pipeline.run(date.today())
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from ingestion.framework.fetchers.base import BaseFetcher
from ingestion.framework.loaders.base import BaseLoader
from ingestion.framework.log import IngestionLogger

logger = logging.getLogger(__name__)


class Pipeline:
    """Wire one fetcher to one loader, write results to ``ingestion_log``.

    On success, calls :meth:`IngestionLogger.record_success`.
    On any exception, calls :meth:`IngestionLogger.record_failure` then
    **re-raises** so the caller (cron / ``daily_run.py``) receives a
    non-zero exit code.

    Args:
        fetcher: A :class:`~ingestion.framework.fetchers.base.BaseFetcher`.
        loader: A :class:`~ingestion.framework.loaders.base.BaseLoader`.
        source_name: Human-readable name written to ``ingestion_log.source_file``.
        table_name: DB table name written to ``ingestion_log.table_name``.
        ingestion_logger: Optional pre-constructed :class:`IngestionLogger`
            (injected for testing; defaults to ``IngestionLogger()``).
    """

    def __init__(
        self,
        fetcher: BaseFetcher,
        loader: BaseLoader,
        source_name: str,
        table_name: str,
        ingestion_logger: Optional[IngestionLogger] = None,
    ) -> None:
        self.fetcher = fetcher
        self.loader = loader
        self.source_name = source_name
        self.table_name = table_name
        self._log = ingestion_logger or IngestionLogger()

    def run(self, trade_date: date) -> int:
        """Execute the full fetch → load → log cycle for *trade_date*.

        Args:
            trade_date: The NSE trading date to ingest.

        Returns:
            Number of rows inserted/updated.

        Raises:
            Exception: Any fetch or load error is logged then re-raised.
        """
        started_at = datetime.utcnow()
        logger.info(
            "Pipeline[%s → %s]: starting for %s",
            self.source_name,
            self.table_name,
            trade_date,
        )
        try:
            path = self.fetcher.fetch(trade_date)
            rows = self.loader.load(path, trade_date)
            self._log.record_success(
                trade_date=trade_date,
                source_name=self.source_name,
                table_name=self.table_name,
                rows_inserted=rows,
                started_at=started_at,
            )
            logger.info(
                "Pipeline[%s]: completed %s — %d rows", self.source_name, trade_date, rows
            )
            return rows
        except Exception as exc:
            self._log.record_failure(
                trade_date=trade_date,
                source_name=self.source_name,
                table_name=self.table_name,
                error_message=str(exc),
                started_at=started_at,
            )
            logger.error(
                "Pipeline[%s]: FAILED for %s — %s", self.source_name, trade_date, exc
            )
            raise
