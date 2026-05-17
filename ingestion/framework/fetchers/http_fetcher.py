"""NSE HTTP fetcher — delegates to the existing :class:`NSEClient`.

Wraps all ``NSEClient`` and ``requests`` exceptions into :class:`FetchError`
so that :class:`HybridFetcher` has a single exception type to catch.
"""
from __future__ import annotations

import gzip
import logging
from datetime import date
from enum import Enum, auto
from pathlib import Path
from typing import Optional

import requests

from ingestion.framework.fetchers.base import BaseFetcher, FetchError
from ingestion.nse_client import CircuitBreakerOpen, NSEClient

logger = logging.getLogger(__name__)

# NSE 52-week archive URL template (date in DDMMYYYY format)
_WK52_URL_TEMPLATE = (
    "https://nsearchives.nseindia.com/content/"
    "CM_52_wk_High_low_{ddmmyyyy}.csv"
)
# Constituents file is always the current list — no date in URL
_CONSTITUENTS_URL = "https://archives.nseindia.com/content/indices/ind_nifty50list.csv"

_INDEX_PRICES_URL = "https://archives.nseindia.com/content/indices/ind_close_all_{ddmmyyyy}.csv"

# NSE security master (gzipped CSV; date in DDMMYYYY format)
_DIM_STOCK_URL_TEMPLATE = (
    "https://nsearchives.nseindia.com/content/cm/interop/"
    "NSE_CM_security_{ddmmyyyy}.csv.gz"
)
# Corporate actions, event calendar, announcements — JSON APIs handled by NSEScraper
_EVENT_CALENDAR_URL = "https://www.nseindia.com/api/event-calendar?index=equities"
_ANNOUNCEMENTS_URL = "https://www.nseindia.com/api/corporate-announcements?index=equities"


class SourceType(Enum):
    """Identifies which NSE data source a fetcher serves."""
    BHAVCOPY = auto()           # sec_bhavdata_full_DDMMYYYY.csv
    WK52 = auto()               # CM_52_wk_High_low_DDMMYYYY.csv
    CONSTITUENTS = auto()       # ind_nifty50list.csv
    DIM_STOCK = auto()          # NSE_CM_security_DDMMYYYY.csv.gz (security master)
    CORPORATE_ACTIONS = auto()  # per-symbol corporate actions API
    EVENT_CALENDAR = auto()     # event-calendar JSON API
    ANNOUNCEMENTS = auto()      # corporate-announcements JSON API
    INDEX = auto()              # index close prices


class NseHttpFetcher(BaseFetcher):
    """Download NSE source files via HTTP, delegating to :class:`NSEClient`.

    For BHAVCOPY, uses ``NSEClient.download_bhavcopy``.
    For WK52 and CONSTITUENTS, uses a direct GET via the NSEClient session.
    For API sources (EVENT_CALENDAR, ANNOUNCEMENTS), saves the JSON response.

    Args:
        source: Which data source to fetch.
        client: Optional pre-constructed ``NSEClient`` (injected for testing).
        output_dir: Override the default ``data/raw/<source>/`` save directory.
    """

    def __init__(
        self,
        source: SourceType,
        client: Optional[NSEClient] = None,
        output_dir: Optional[Path] = None,
    ) -> None:
        self.source = source
        self._client = client or NSEClient()
        self._output_dir = output_dir

    def fetch(self, trade_date: date) -> Path:
        """Download the source file for *trade_date*.

        Args:
            trade_date: The trading date to fetch data for.

        Returns:
            Local path to the downloaded file.

        Raises:
            FetchError: On circuit-breaker trip or HTTP failure.
        """
        try:
            return self._fetch_by_source(trade_date)
        except CircuitBreakerOpen as exc:
            raise FetchError(f"Circuit breaker open: {exc}") from exc
        except requests.RequestException as exc:
            raise FetchError(f"HTTP download failed: {exc}") from exc

    def _fetch_by_source(self, trade_date: date) -> Path:
        """Dispatch to the correct download method for the source type."""
        if self.source == SourceType.BHAVCOPY:
            return self._client.download_bhavcopy(
                trade_date, output_dir=self._output_dir
            )
        if self.source == SourceType.WK52:
            return self._download_csv(
                url=_WK52_URL_TEMPLATE.format(
                    ddmmyyyy=trade_date.strftime("%d%m%Y")
                ),
                filename=f"CM_52_wk_High_low_{trade_date.strftime('%d%m%Y')}.csv",
                subdir="52wk",
            )
        if self.source == SourceType.CONSTITUENTS:
            return self._download_csv(
                url=_CONSTITUENTS_URL,
                filename="ind_nifty50list.csv",
                subdir="constituents",
            )
        if self.source == SourceType.DIM_STOCK:
            return self._download_csv_gz(
                url=_DIM_STOCK_URL_TEMPLATE.format(
                    ddmmyyyy=trade_date.strftime("%d%m%Y")
                ),
                filename=f"NSE_CM_security_{trade_date.strftime('%d%m%Y')}.csv",
                subdir="dim_stock",
            )
        if self.source == SourceType.EVENT_CALENDAR:
            return self._download_json(
                url=_EVENT_CALENDAR_URL,
                filename=f"event_calendar_{trade_date.strftime('%Y%m%d')}.json",
                subdir="event_calendar",
            )
        if self.source == SourceType.ANNOUNCEMENTS:
            return self._download_json(
                url=_ANNOUNCEMENTS_URL,
                filename=f"announcements_{trade_date.strftime('%Y%m%d')}.json",
                subdir="announcements",
            )
        if self.source == SourceType.INDEX:
            return self._download_csv(
                url=_INDEX_PRICES_URL.format(
                    ddmmyyyy=trade_date.strftime("%d%m%Y")
                ),
                filename=f"ind_close_all_{trade_date.strftime('%Y%m%d')}.csv",
                subdir="index",
            )
        raise FetchError(
            f"HTTP fetch not supported for source {self.source}. "
            "Use the dedicated scraper instead."
        )

    def _save_dir(self, subdir: str) -> Path:
        """Resolve or create the output directory for *subdir*."""
        from config.settings import settings
        base = self._output_dir or (settings.project_root / "data" / "raw" / subdir)
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _download_csv(self, url: str, filename: str, subdir: str) -> Path:
        """Download a CSV from *url* and save as *filename* in ``data/raw/<subdir>/``."""
        resp = self._client._request_with_retry(url)
        out = self._save_dir(subdir) / filename
        out.write_bytes(resp.content)
        logger.info("Downloaded %s → %s", url, out)
        return out

    def _download_csv_gz(self, url: str, filename: str, subdir: str) -> Path:
        """Download a gzipped CSV, decompress on the fly, and save as *filename*.

        NSE security master is published as ``.csv.gz``. We decompress before
        writing to disk so downstream loaders can open the file with
        ``pd.read_csv`` without needing to know the wire format.

        Args:
            url: Full URL to the ``.csv.gz`` file.
            filename: Target filename for the *decompressed* CSV.
            subdir: Subdirectory under ``data/raw/`` to save into.

        Returns:
            Path to the decompressed CSV on disk.

        Raises:
            FetchError: If the gzip stream is invalid (caller wraps via
                :meth:`fetch`'s ``requests.RequestException`` handler is not
                enough — gzip errors are :class:`OSError`).
        """
        resp = self._client._request_with_retry(url)
        try:
            decompressed = gzip.decompress(resp.content)
        except OSError as exc:
            raise FetchError(
                f"Could not decompress gzip stream from {url}: {exc}"
            ) from exc
        out = self._save_dir(subdir) / filename
        out.write_bytes(decompressed)
        logger.info(
            "Downloaded + decompressed %s → %s (%d bytes)",
            url, out, len(decompressed),
        )
        return out

    def _download_json(self, url: str, filename: str, subdir: str) -> Path:
        """Download a JSON API response and save as *filename*."""
        resp = self._client._request_with_retry(url)
        out = self._save_dir(subdir) / filename
        out.write_bytes(resp.content)
        logger.info("Downloaded JSON %s → %s", url, out)
        return out
