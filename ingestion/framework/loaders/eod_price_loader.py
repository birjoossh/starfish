"""EOD price loader — framework adapter for the existing bhavcopy pipeline.

Delegates all parsing and DB work to the existing (unchanged)
:class:`~ingestion.bhavcopy_parser.BhavcopyParser` and
:class:`~ingestion.bhavcopy_loader.BhavcopyLoader`.

Target table: ``fact_eod_price``
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

from ingestion.bhavcopy_loader import BhavcopyLoader as _BhavcopyLoader
from ingestion.bhavcopy_parser import BhavcopyParser as _BhavcopyParser
from ingestion.framework.loaders.base import BaseLoader

logger = logging.getLogger(__name__)


class EodPriceLoader(BaseLoader):
    """Load NSE bhavcopy CSV into ``fact_eod_price``.

    Thin wrapper: delegates all logic to the existing
    :class:`~ingestion.bhavcopy_parser.BhavcopyParser` and
    :class:`~ingestion.bhavcopy_loader.BhavcopyLoader`.

    Args:
        parser: Optional pre-constructed parser (injected for testing).
        bhavcopy_loader: Optional pre-constructed loader (injected for testing).
    """

    def __init__(
        self,
        parser: Optional[_BhavcopyParser] = None,
        bhavcopy_loader: Optional[_BhavcopyLoader] = None,
    ) -> None:
        self._parser = parser or _BhavcopyParser()
        self._loader = bhavcopy_loader or _BhavcopyLoader()

    def load(self, path: Path, trade_date: date) -> int:
        """Parse bhavcopy CSV at *path* and upsert into ``fact_eod_price``.

        Args:
            path: Path to the bhavcopy CSV file.
            trade_date: The trading date this file represents.

        Returns:
            Number of rows inserted (duplicates are skipped).

        Raises:
            BhavcopyParseError: If the CSV cannot be parsed.
            Exception: On DB errors.
        """
        df = self._parser.parse(path, trade_date=trade_date, source_file=path.name)
        stats = self._loader.load(df, source_file=path.name)
        logger.info(
            "EodPriceLoader: %d/%d rows inserted for %s",
            stats["rows_inserted"],
            stats["rows_total"],
            trade_date,
        )
        return stats["rows_inserted"]
