"""Event calendar loader — framework wrapper for NSE scraper chain (Source F).

Note: The spec defines ``fact_event_calendar`` but this table does not yet
exist in the schema. This loader targets the existing ``fact_corporate_event``
table which is functionally equivalent. The table will be renamed/migrated
in a future schema phase.

The legacy :class:`CorporateEventsIngestor` only reads CSV. The actual NSE
``event-calendar`` API returns JSON, so when the source path ends in
``.json`` we normalize the JSON into a 3-column CSV (``symbol``, ``purpose``,
``date``) via :mod:`._event_json_adapter` and pass that through unchanged.

Symbols not present in ``dim_stock`` (e.g. REITs, InvITs like
``INDUSINVIT`` — non-EQ instruments) would otherwise trigger
``fact_corporate_event_symbol_fkey`` foreign-key violations and abort the
whole transaction. They are filtered out before insert and routed to a JSON
bad-records file via :mod:`._symbol_validator`.

Target table: ``fact_corporate_event``
"""
from __future__ import annotations

import logging
import tempfile
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

from ingestion.corporate_events_ingestor import CorporateEventsIngestor as _Ingestor
from ingestion.corporate_events_loader import CorporateEventsLoader as _Loader
from ingestion.framework.json_bad_records import JsonBadRecordsWriter
from ingestion.framework.loaders._event_json_adapter import json_to_temp_csv
from ingestion.framework.loaders._symbol_validator import (
    fetch_known_symbols, filter_unknown_symbols,
)
from ingestion.framework.loaders.base import BaseLoader

logger = logging.getLogger(__name__)


class EventCalendarLoader(BaseLoader):
    """Framework adapter for the event calendar scraper chain.

    The source file (JSON or CSV from NSE ``event-calendar`` API) is first
    classified by :class:`~ingestion.corporate_events_ingestor.CorporateEventsIngestor`,
    then upserted by :class:`~ingestion.corporate_events_loader.CorporateEventsLoader`.

    Args:
        ingestor: Optional pre-constructed ingestor (injected for testing).
        events_loader: Optional pre-constructed loader (injected for testing).
        engine: Optional SQLAlchemy engine used to look up valid symbols
            from ``dim_stock``. Defaults to the project engine. Pass
            ``None`` only in tests where you also pass *known_symbols*.
        bad_records_writer: Where to dump original JSON records for symbols
            not present in ``dim_stock``. Disabled (``None``) by default —
            in production it is wired in by :mod:`run_pipeline`.
        known_symbols: Pre-fetched set of valid symbols. When given, the
            engine is not consulted (intended for tests / batch reuse).
    """

    def __init__(
        self,
        ingestor: Optional[_Ingestor] = None,
        events_loader: Optional[_Loader] = None,
        *,
        engine=None,
        bad_records_writer: Optional[JsonBadRecordsWriter] = None,
        known_symbols: Optional[set[str]] = None,
    ) -> None:
        self._ingestor = ingestor or _Ingestor()
        self._loader = events_loader or _Loader()
        self._engine = engine
        self._bad_records = bad_records_writer
        self._known_symbols = known_symbols

    def load(self, path: Path, trade_date: date) -> int:
        """Classify, drop unknown-symbol rows, and upsert event calendar records.

        Args:
            path: Path to the downloaded event calendar JSON/CSV.
            trade_date: The date to use as ``calc_date`` for event classification.

        Returns:
            Number of rows upserted into ``fact_corporate_event``.
        """
        df = self._ingest(path, trade_date)
        df = self._filter_unknown_symbols(df, json_source_path=path)
        rows = self._loader.load(df)
        logger.info(
            "EventCalendarLoader: %d rows for %s", rows, trade_date
        )
        return rows

    def _ingest(self, path: Path, trade_date: date) -> "pd.DataFrame":
        """Run the legacy ingestor, transparently converting JSON to CSV first."""
        if path.suffix.lower() == ".json":
            with tempfile.TemporaryDirectory(prefix="event_calendar_") as td:
                csv_path = json_to_temp_csv(path, kind="event_calendar", dest_dir=Path(td))
                logger.debug(
                    "EventCalendarLoader: normalized %s → %s for ingestor",
                    path.name, csv_path.name,
                )
                return self._ingestor.ingest(csv_path, calc_date=trade_date)
        return self._ingestor.ingest(path, calc_date=trade_date)

    def _filter_unknown_symbols(
        self, df: "pd.DataFrame", *, json_source_path: Path
    ) -> "pd.DataFrame":
        """Strip rows whose symbol is missing from ``dim_stock``."""
        if df is None or df.empty:
            return df
        known = self._known_symbols
        if known is None:
            if self._engine is None:
                # Lazily resolve the project engine — this branch is normal in
                # production. Tests pass either ``engine`` or ``known_symbols``
                # explicitly to avoid touching the real DB.
                from config.database import get_engine
                self._engine = get_engine()
            known = fetch_known_symbols(self._engine)
        return filter_unknown_symbols(
            df,
            known_symbols=known,
            json_source_path=json_source_path,
            bad_records_writer=self._bad_records,
        )
