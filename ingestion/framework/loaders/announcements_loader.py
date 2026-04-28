"""Corporate announcements loader — framework wrapper for NSE scraper chain (Source G).

Note: The spec defines ``fact_announcement`` but this table does not yet exist
in the schema. This loader targets the existing ``fact_corporate_event`` table.
The table will be added in a future schema phase.

Target table: ``fact_corporate_event``
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

from ingestion.corporate_events_ingestor import CorporateEventsIngestor as _Ingestor
from ingestion.corporate_events_loader import CorporateEventsLoader as _Loader
from ingestion.framework.loaders.base import BaseLoader

logger = logging.getLogger(__name__)


class AnnouncementsLoader(BaseLoader):
    """Framework adapter for the corporate announcements scraper chain.

    The source file (JSON from NSE ``corporate-announcements`` API) is
    classified by :class:`~ingestion.corporate_events_ingestor.CorporateEventsIngestor`,
    then upserted by :class:`~ingestion.corporate_events_loader.CorporateEventsLoader`.

    Args:
        ingestor: Optional pre-constructed ingestor (injected for testing).
        events_loader: Optional pre-constructed loader (injected for testing).
    """

    def __init__(
        self,
        ingestor: Optional[_Ingestor] = None,
        events_loader: Optional[_Loader] = None,
    ) -> None:
        self._ingestor = ingestor or _Ingestor()
        self._loader = events_loader or _Loader()

    def load(self, path: Path, trade_date: date) -> int:
        """Classify and upsert announcement records.

        Args:
            path: Path to the downloaded announcements JSON/CSV.
            trade_date: The date to use as ``calc_date`` for classification.

        Returns:
            Number of rows upserted into ``fact_corporate_event``.
        """
        df = self._ingestor.ingest(path, calc_date=trade_date)
        rows = self._loader.load(df)
        logger.info(
            "AnnouncementsLoader: %d rows for %s", rows, trade_date
        )
        return rows
