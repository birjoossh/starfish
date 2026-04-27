"""Hybrid fetcher: HTTP-first with local-folder fallback.

On each :meth:`fetch` call:
1. Attempts HTTP download via the injected ``http`` fetcher.
2. If that raises :class:`FetchError` (network down, circuit-breaker open,
   NSE returns non-200), logs a warning and tries the ``local`` fetcher.
3. If both fail, the local fetcher's :class:`FetchError` propagates to the caller.

Non-:class:`FetchError` exceptions from the HTTP fetcher (e.g. programmer
errors, unexpected runtime failures) are **not** caught — they propagate
immediately so they are not silently hidden by the fallback path.
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from ingestion.framework.fetchers.base import BaseFetcher, FetchError

logger = logging.getLogger(__name__)


class HybridFetcher(BaseFetcher):
    """Compose an HTTP fetcher and a local fetcher with automatic fallback.

    Args:
        http: A :class:`BaseFetcher` that attempts HTTP download.
        local: A :class:`BaseFetcher` that reads from the local drop folder.
    """

    def __init__(self, http: BaseFetcher, local: BaseFetcher) -> None:
        self.http = http
        self.local = local

    def fetch(self, trade_date: date) -> Path:
        """Fetch file for *trade_date*, trying HTTP first, then local.

        Args:
            trade_date: The NSE trading date needed.

        Returns:
            Path to a local file ready for parsing.

        Raises:
            FetchError: If both HTTP and local sources fail.
        """
        try:
            path = self.http.fetch(trade_date)
            logger.debug("HybridFetcher: HTTP succeeded for %s", trade_date)
            return path
        except FetchError as exc:
            logger.warning(
                "HybridFetcher: HTTP failed for %s (%s). Trying local fallback.",
                trade_date,
                exc,
            )
        # Local raises FetchError naturally if not found — let it propagate
        return self.local.fetch(trade_date)
