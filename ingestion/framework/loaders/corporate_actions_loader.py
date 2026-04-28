"""Corporate actions loader — framework wrapper for existing chain (Source E).

Wraps the existing :class:`~ingestion.corporate_actions_parser.CorporateActionsParser`
and :class:`~ingestion.corporate_actions_loader.CorporateActionsLoader`
(note: the existing loader has the same class name — this wrapper uses a
disambiguating class name ``CorporateActionsFrameworkLoader``).

Target table: ``fact_corporate_action``
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

from ingestion.corporate_actions_loader import CorporateActionsLoader as _ExistingLoader
from ingestion.corporate_actions_parser import CorporateActionsParser as _ExistingParser
from ingestion.framework.loaders.base import BaseLoader

logger = logging.getLogger(__name__)


class CorporateActionsFrameworkLoader(BaseLoader):
    """Framework adapter for the existing corporate actions ingestion chain.

    Args:
        parser: Optional pre-constructed parser (injected for testing).
        ca_loader: Optional pre-constructed loader (injected for testing).
    """

    def __init__(
        self,
        parser: Optional[_ExistingParser] = None,
        ca_loader: Optional[_ExistingLoader] = None,
    ) -> None:
        self._parser = parser or _ExistingParser()
        self._loader = ca_loader or _ExistingLoader()

    def load(self, path: Path, trade_date: date) -> int:
        """Parse corporate actions CSV and upsert into ``fact_corporate_action``.

        Args:
            path: Path to the NSE corporate actions CSV.
            trade_date: Reference date for filtering future actions.

        Returns:
            Number of rows upserted.
        """
        df = self._parser.parse(path, as_of=trade_date)
        rows = self._loader.load(df)
        logger.info(
            "CorporateActionsFrameworkLoader: %d rows for %s", rows, trade_date
        )
        return rows
