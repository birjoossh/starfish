"""Watchlist management — loads symbols from watchlist.yaml.

Usage:
    from dashboard.watchlist import load_watchlist
    symbols = load_watchlist()
    if "RELIANCE" in symbols:
        print("RELIANCE is on your watchlist")
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from config.settings import settings

logger = logging.getLogger(__name__)


def load_watchlist() -> set[str]:
    """Load watchlist symbols from watchlist.yaml.

    Returns empty set if file doesn't exist or is invalid.
    """
    path = settings.watchlist_path
    if not path.exists():
        logger.info("No watchlist.yaml found, watchlist disabled")
        return set()

    try:
        with open(path) as f:
            data = yaml.safe_load(f)

        if not data or "symbols" not in data:
            logger.warning("watchlist.yaml missing 'symbols' key")
            return set()

        symbols = set(data["symbols"])
        logger.info(f"Loaded watchlist: {len(symbols)} symbols")
        return symbols

    except Exception as e:
        logger.warning(f"Failed to load watchlist: {e}")
        return set()
