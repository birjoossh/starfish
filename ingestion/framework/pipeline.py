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
import shutil
from datetime import date, datetime
from pathlib import Path
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
        processed_dir: Optional destination directory. After a successful
            load the source file is moved here. On failure the file is left
            in place for inspection. Set to ``None`` to disable the move.
    """

    def __init__(
        self,
        fetcher: BaseFetcher,
        loader: BaseLoader,
        source_name: str,
        table_name: str,
        ingestion_logger: Optional[IngestionLogger] = None,
        processed_dir: Optional[Path] = None,
    ) -> None:
        self.fetcher = fetcher
        self.loader = loader
        self.source_name = source_name
        self.table_name = table_name
        self._log = ingestion_logger or IngestionLogger()
        self.processed_dir = Path(processed_dir) if processed_dir else None

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
            self._archive_processed_file(path, trade_date)
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

    def _archive_processed_file(self, src: Path, trade_date: date) -> None:
        """Move *src* into ``processed_dir`` after a successful load.

        Silently no-ops when:
        - ``processed_dir`` is not configured
        - ``src`` is already inside ``processed_dir`` (idempotent re-runs)
        - ``src`` no longer exists on disk

        Move failures are logged as warnings but do **not** propagate —
        the data is already in the database, so an archive failure is
        a janitorial concern, not a pipeline failure.
        """
        if self.processed_dir is None:
            return
        try:
            src = Path(src).resolve()
            if not src.exists():
                return
            dest_dir = self.processed_dir.resolve()
            if dest_dir == src.parent:
                logger.debug(
                    "Pipeline[%s]: file already in processed_dir, skipping move",
                    self.source_name,
                )
                return
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / src.name
            # If a file with the same name already exists in the archive
            # (re-run for the same date), suffix with the trade_date.
            if dest.exists():
                dest = dest_dir / f"{src.stem}.{trade_date.isoformat()}{src.suffix}"
            shutil.move(str(src), str(dest))
            logger.info(
                "Pipeline[%s]: archived %s → %s",
                self.source_name, src.name, dest,
            )
        except OSError as exc:
            logger.warning(
                "Pipeline[%s]: could not archive %s: %s",
                self.source_name, src, exc,
            )
