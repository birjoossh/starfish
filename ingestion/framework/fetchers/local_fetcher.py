"""Local filesystem fetcher — fallback when HTTP download is unavailable.

Scans a configured source directory for files matching known NSE naming
conventions. Raises :class:`FetchError` if no match is found.

Naming patterns supported (in priority order):
1. ``sec_bhavdata_full_DDMMYYYY.csv``  — new NSE archive format
2. ``CM_52_wk_High_low_DDMMYYYY.csv`` — 52-week file
3. ``cmDDMONYYYYbhav.csv``            — legacy bhavcopy
4. Any ``*DDMMYYYY*.csv`` pattern      — generic fallback
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from ingestion.framework.fetchers.base import BaseFetcher, FetchError

logger = logging.getLogger(__name__)


class LocalFetcher(BaseFetcher):
    """Fetch a trading-day file from a local directory.

    Useful when NSE HTTP downloads are unavailable or blocked, or during
    development when files are dropped manually into ``data/raw/<source>/``.

    Args:
        source_dir: Directory to search. Must exist at construction time.

    Raises:
        FetchError: At construction if ``source_dir`` does not exist.
    """

    def __init__(self, source_dir: Path) -> None:
        source_dir = Path(source_dir)
        if not source_dir.exists():
            raise FetchError(
                f"Local source directory does not exist: {source_dir}"
            )
        self.source_dir = source_dir

    def fetch(self, trade_date: date) -> Path:
        """Return the local file path for *trade_date*.

        Args:
            trade_date: The NSE trading date to look up.

        Returns:
            Path to the found file.

        Raises:
            FetchError: If no matching file is found in ``source_dir``.
        """
        dd = trade_date.strftime("%d")
        mm = trade_date.strftime("%m")
        yyyy = trade_date.strftime("%Y")
        mon_upper = trade_date.strftime("%b").upper()  # e.g. "JAN"
        ddmmyyyy = f"{dd}{mm}{yyyy}"

        patterns = [
            f"sec_bhavdata_full_{ddmmyyyy}.csv",
            f"CM_52_wk_High_low_{ddmmyyyy}.csv",
            f"cm{dd}{mon_upper}{yyyy}bhav.csv",
            f"ind_nifty50list.csv",
            f"*{ddmmyyyy}*.csv",
        ]

        for pattern in patterns:
            matches = list(self.source_dir.glob(pattern))
            if matches:
                logger.info(
                    "LocalFetcher: found %s for %s", matches[0].name, trade_date
                )
                return matches[0]

        raise FetchError(
            f"No file found for {trade_date} in {self.source_dir}. "
            f"Searched patterns: {patterns}"
        )
