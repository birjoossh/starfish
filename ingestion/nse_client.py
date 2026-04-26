"""NSE download client with rate limiting, retry, and circuit breaker.

Downloads bhavcopy ZIP files from NSE archives.
Falls back to local file source after max_retries consecutive failures.

Usage:
    from ingestion.nse_client import NSEClient
    client = NSEClient()
    filepath = client.download_bhavcopy(date(2024, 1, 15))
"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import requests

from config.settings import settings

logger = logging.getLogger(__name__)

class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open (too many consecutive failures)."""
    pass


class NSEClient:
    """Rate-limited HTTP client for NSE archive downloads.

    Features:
    - Minimum delay between requests (configurable)
    - Exponential backoff on 429/503
    - Circuit breaker: trips after max_retries consecutive failures
    - Proper User-Agent and session management for NSE cookies
    """

    def __init__(
        self,
        base_url: str | None = None,
        delay: float | None = None,
        max_retries: int | None = None,
        backoff_factor: float | None = None,
    ):
        self.base_url = base_url or settings.nse_base_url
        self.delay = delay or settings.request_delay_seconds
        self.max_retries = max_retries or settings.max_retries
        self.backoff_factor = backoff_factor or settings.backoff_factor

        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": settings.nse_user_agent,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/",
        })

        self._consecutive_failures = 0
        self._last_request_time = 0.0

    @property
    def circuit_open(self) -> bool:
        """True if circuit breaker is tripped."""
        return self._consecutive_failures >= self.max_retries

    def reset_circuit(self) -> None:
        """Reset the circuit breaker after successful download."""
        self._consecutive_failures = 0

    def _rate_limit(self) -> None:
        """Enforce minimum delay between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay:
            sleep_time = self.delay - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.1f}s")
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def _request_with_retry(self, url: str) -> requests.Response:
        """Make a request with exponential backoff on 429/503."""
        if self.circuit_open:
            raise CircuitBreakerOpen(
                f"Circuit breaker open after {self.max_retries} consecutive failures. "
                "Use local file source instead."
            )

        self._rate_limit()

        last_error = None
        for attempt in range(self.max_retries):
            try:
                resp = self._session.get(url, timeout=30)

                if resp.status_code == 200:
                    self._consecutive_failures = 0
                    return resp

                if resp.status_code in (429, 503):
                    wait = self.delay * (self.backoff_factor ** attempt)
                    logger.warning(
                        f"NSE returned {resp.status_code} for {url}. "
                        f"Retry {attempt + 1}/{self.max_retries} in {wait:.1f}s"
                    )
                    last_error = f"{resp.status_code} Error"
                    time.sleep(wait)
                    self._rate_limit()
                    continue

                # Other errors: 403, 404, 500, etc.
                resp.raise_for_status()

            except requests.exceptions.RequestException as e:
                last_error = e
                wait = self.delay * (self.backoff_factor ** attempt)
                logger.warning(
                    f"Request failed: {e}. "
                    f"Retry {attempt + 1}/{self.max_retries} in {wait:.1f}s"
                )
                time.sleep(wait)
                self._rate_limit()

        self._consecutive_failures += 1
        raise requests.exceptions.RequestException(
            f"Failed to download {url} after {self.max_retries} attempts. "
            f"Consecutive failures: {self._consecutive_failures} | Last error: {last_error}"
        )

    def _bhavcopy_url(self, trade_date: date) -> str:
        """Construct NSE bhavcopy CSV URL for a given date.

        Format: https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_DDMMYYYY.csv
        """
        date_str = trade_date.strftime("%d%m%Y")
        return f"https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{date_str}.csv"

    def download_bhavcopy(self, trade_date: date, output_dir: Path | None = None) -> Path:
        """Download bhavcopy CSV for a given date.

        Args:
            trade_date: The trading date to download.
            output_dir: Directory to save CSV. Defaults to project data dir.

        Returns:
            Path to the saved CSV file.

        Raises:
            CircuitBreakerOpen: If circuit breaker is tripped.
            requests.exceptions.RequestException: If download fails after retries.
        """
        if output_dir is None:
            output_dir = settings.project_root / "data" / "bhavcopy"
        output_dir.mkdir(parents=True, exist_ok=True)

        url = self._bhavcopy_url(trade_date)
        logger.info(f"Downloading bhavcopy: {url}")

        resp = self._request_with_retry(url)

        # Save CSV directly (new NSE archives serve CSV, not ZIP)
        month_upper = trade_date.strftime("%b").upper()
        output_path = output_dir / f"cm{trade_date.strftime('%d')}{month_upper}{trade_date.year}bhav.csv"

        with open(output_path, "wb") as f:
            f.write(resp.content)

        logger.info(f"Saved: {output_path}")
        return output_path

    def download_bhavcopy_range(
        self,
        start_date: date,
        end_date: date,
        output_dir: Path | None = None,
    ) -> list[Path]:
        """Download bhavcopies for a date range (trading days only).

        Skips weekends. Market holidays will fail gracefully (logged, not raised).

        Returns:
            List of paths to successfully downloaded CSVs.
        """
        downloaded = []
        current = start_date

        while current <= end_date:
            # Skip weekends
            if current.weekday() < 5:  # Mon-Fri
                try:
                    path = self.download_bhavcopy(current, output_dir)
                    downloaded.append(path)
                except (CircuitBreakerOpen, requests.exceptions.RequestException) as e:
                    logger.warning(f"Skipping {current}: {e}")
                    if isinstance(e, CircuitBreakerOpen):
                        logger.error("Circuit breaker tripped. Stopping range download.")
                        break
            current += timedelta(days=1)

        return downloaded
