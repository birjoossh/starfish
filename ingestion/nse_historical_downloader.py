#!/usr/bin/env python3
"""NSE Historical Data Downloader.

Downloads 5+ years of NSE bhavcopy and index files for backfill.
Rate-limited to avoid NSE blocking.

Usage:
    # Download last 5 years
    python -m ingestion.nse_historical_downloader --years 5

    # Download specific date range
    python -m ingestion.nse_historical_downloader --start 2019-01-01 --end 2024-01-17

    # Resume interrupted download
    python -m ingestion.nse_historical_downloader --resume

    # Check what's missing
    python -m ingestion.nse_historical_downloader --missing
"""

import argparse
import logging
import time
from datetime import date, timedelta
from pathlib import Path

from config.settings import settings
from ingestion.nse_client import NSEClient, CircuitBreakerOpen

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# NSE archive URLs
# NSE archive base URL
NSE_ARCHIVE_URL = "https://archives.nseindia.com"
NSE_EQUITIES_PATH = "content/historical/EQUITIES"
NSE_INDEX_PATH = "content/indices"

MONTH_ABBR = {
    1: "JAN", 2: "FEB", 3: "MAR", 4: "APR",
    5: "MAY", 6: "JUN", 7: "JUL", 8: "AUG",
    9: "SEP", 10: "OCT", 11: "NOV", 12: "DEC",
}

# Rate limiting
MIN_REQUEST_INTERVAL = 2.0  # seconds between requests
MAX_DAILY_REQUESTS = 500    # NSE daily limit approximation
CIRCUIT_BREAKER_THRESHOLD = 10  # consecutive failures before pause


class NSEHistoricalDownloader:
    """Download historical NSE data for backfill."""

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or (settings.project_root / "data")
        self.bhavcopy_dir = self.data_dir / "bhavcopy"
        self.index_dir = self.data_dir / "index"

        self.bhavcopy_dir.mkdir(parents=True, exist_ok=True)
        self.index_dir.mkdir(parents=True, exist_ok=True)

        self.client = NSEClient()
        self.request_count = 0
        self.consecutive_failures = 0
        self.last_request_time = 0

    def _rate_limit(self):
        """Apply rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)
        self.last_request_time = time.time()

    def _bhavcopy_filename(self, trade_date: date) -> str:
        """Generate NSE bhavcopy filename (with .zip)."""
        month = trade_date.strftime("%b").upper()
        return f"cm{trade_date.strftime('%d')}{month}{trade_date.year}bhav.csv.zip"

    def _bhavcopy_csv_filename(self, trade_date: date) -> str:
        """Generate NSE bhavcopy CSV filename (without .zip, after extraction)."""
        month = trade_date.strftime("%b").upper()
        return f"cm{trade_date.strftime('%d')}{month}{trade_date.year}bhav.csv"

    def _index_filename(self, trade_date: date) -> str:
        """Generate NSE index filename."""
        return f"ind_close_all_{trade_date.strftime('%d%m%Y')}.csv"

    def _bhavcopy_url(self, trade_date: date) -> str:
        """Generate bhavcopy download URL."""
        year = trade_date.strftime("%Y")
        month = trade_date.strftime("%b").upper()
        day = trade_date.strftime("%d")
        # Format: cm02JAN2024bhav.csv.zip
        filename = f"cm{day}{month}{year}bhav.csv.zip"
        return f"{NSE_ARCHIVE_URL}/{NSE_EQUITIES_PATH}/{year}/{month}/{filename}"

    def _index_url(self, trade_date: date) -> str:
        """Generate index download URL."""
        return f"{NSE_ARCHIVE_URL}/{NSE_INDEX_PATH}/{self._index_filename(trade_date)}"

    def _bhavcopy_path(self, trade_date: date) -> Path:
        """Get local bhavcopy path (ZIP file)."""
        return self.bhavcopy_dir / self._bhavcopy_filename(trade_date)

    def _bhavcopy_csv_path(self, trade_date: date) -> Path:
        """Get local bhavcopy CSV path (after extraction)."""
        return self.bhavcopy_dir / self._bhavcopy_csv_filename(trade_date)

    def _index_path(self, trade_date: date) -> Path:
        """Get local index path."""
        return self.index_dir / self._index_filename(trade_date)

    def is_weekend(self, d: date) -> bool:
        """Check if date is weekend."""
        return d.weekday() >= 5

    def is_market_holiday(self, d: date) -> bool:
        """Check common Indian market holidays (simplified)."""
        # Common holidays - full list would need NSE calendar
        if d.month == 1 and d.day == 1:
            return True  # New Year
        if d.month == 1 and d.day == 26:
            return True  # Republic Day
        if d.month == 8 and d.day == 15:
            return True  # Independence Day
        if d.month == 10 and d.day in [2]:
            return True  # Gandhi Jayanti
        return False

    def download_bhavcopy(self, trade_date: date, force: bool = False) -> dict:
        """Download single bhavcopy file using existing NSEClient."""
        csv_path = self._bhavcopy_csv_path(trade_date)

        # Check if already downloaded
        if csv_path.exists() and not force:
            return {"status": "skipped", "reason": "exists", "path": csv_path}

        try:
            # Use existing NSEClient to download and extract
            path = self.client.download_bhavcopy(trade_date, output_dir=self.bhavcopy_dir)

            if path and path.exists():
                self.request_count += 1
                self.consecutive_failures = 0
                logger.info(f"Downloaded: {path.name}")
                return {"status": "success", "path": path}
            else:
                return {"status": "skipped", "reason": "no data", "date": trade_date}

        except Exception as e:
            self.consecutive_failures += 1
            error_msg = str(e)

            if "404" in error_msg or "Not Found" in error_msg:
                return {"status": "skipped", "reason": "no data", "date": trade_date}

            logger.warning(f"Failed to download {trade_date}: {e}")

            if self.consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
                logger.error("Circuit breaker triggered - too many failures")
                return {"status": "circuit_breaker", "failures": self.consecutive_failures}

            return {"status": "error", "reason": str(e)}

    def download_index(self, trade_date: date, force: bool = False) -> dict:
        """Download single index file."""
        output_path = self._index_path(trade_date)

        if output_path.exists() and not force:
            return {"status": "skipped", "reason": "exists", "path": output_path}

        self._rate_limit()

        try:
            url = self._index_url(trade_date)
            logger.debug(f"Downloading: {url}")

            resp = self.client._request_with_retry(url)

            with open(output_path, "wb") as f:
                f.write(resp.content)

            self.request_count += 1
            self.consecutive_failures = 0
            logger.info(f"Downloaded: {output_path.name}")

            return {"status": "success", "path": output_path}

        except Exception as e:
            if "404" in str(e):
                return {"status": "skipped", "reason": "no data", "date": trade_date}

            logger.warning(f"Failed to download index {trade_date}: {e}")
            return {"status": "error", "reason": str(e)}

    def get_date_range(self, start: date, end: date) -> list:
        """Generate list of trading dates in range."""
        dates = []
        current = start

        while current <= end:
            if not self.is_weekend(current) and not self.is_market_holiday(current):
                dates.append(current)
            current += timedelta(days=1)

        return dates

    def run(
        self,
        start_date: date,
        end_date: date,
        download_bhavcopy: bool = True,
        download_index: bool = True,
        force: bool = False,
    ) -> dict:
        """Run download for date range.

        Downloads from start_date to end_date (both inclusive).
        Downloads oldest first for resumability.
        """
        # Ensure start < end (download oldest first)
        if start_date > end_date:
            start_date, end_date = end_date, start_date

        dates = self.get_date_range(start_date, end_date)

        # Sort dates in descending order (newest first) to get recent data first
        # This works better with NSE archive which may have limited history
        dates = sorted(dates, reverse=True)
        total = len(dates)

        logger.info(f"Starting download: {start_date} to {end_date}")
        logger.info(f"Trading days: {total}")

        stats = {
            "total_dates": total,
            "bhavcopy_downloaded": 0,
            "bhavcopy_skipped": 0,
            "bhavcopy_failed": 0,
            "index_downloaded": 0,
            "index_skipped": 0,
            "index_failed": 0,
            "days_processed": 0,
        }

        for i, d in enumerate(dates):
            if self.request_count >= MAX_DAILY_REQUESTS:
                logger.warning(f"Daily request limit ({MAX_DAILY_REQUESTS}) reached")
                break

            if i % 50 == 0 and i > 0:
                logger.info(f"Progress: {i}/{total} days ({i*100//total}%)")

            # Download bhavcopy
            if download_bhavcopy:
                result = self.download_bhavcopy(d, force=force)
                if result["status"] == "success":
                    stats["bhavcopy_downloaded"] += 1
                elif result["status"] == "skipped":
                    stats["bhavcopy_skipped"] += 1
                else:
                    stats["bhavcopy_failed"] += 1

                if result.get("status") == "circuit_breaker":
                    logger.error("Stopping due to circuit breaker")
                    break

            # Download index
            if download_index:
                result = self.download_index(d, force=force)
                if result["status"] == "success":
                    stats["index_downloaded"] += 1
                elif result["status"] == "skipped":
                    stats["index_skipped"] += 1
                else:
                    stats["index_failed"] += 1

            stats["days_processed"] += 1

        logger.info(f"Download complete: {stats}")
        return stats

    def show_missing(self, start_date: date, end_date: date):
        """Show which files are missing."""
        dates = self.get_date_range(start_date, end_date)

        bhavcopy_missing = []
        index_missing = []

        for d in dates:
            if not self._bhavcopy_path(d).exists():
                bhavcopy_missing.append(d)
            if not self._index_path(d).exists():
                index_missing.append(d)

        print(f"\nDate range: {start_date} to {end_date}")
        print(f"Trading days: {len(dates)}")
        print(f"\nBhavcopy: {len(bhavcopy_missing)} missing out of {len(dates)}")
        if bhavcopy_missing[:5]:
            print(f"  First missing: {bhavcopy_missing[0]}")
            print(f"  Last missing: {bhavcopy_missing[-1]}")

        print(f"\nIndex: {len(index_missing)} missing out of {len(dates)}")
        if index_missing[:5]:
            print(f"  First missing: {index_missing[0]}")
            print(f"  Last missing: {index_missing[-1]}")


def main():
    parser = argparse.ArgumentParser(description="NSE Historical Data Downloader")
    parser.add_argument("--years", type=int, help="Number of years to download (from today)")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--skip-bhavcopy", action="store_true", help="Skip bhavcopy files")
    parser.add_argument("--skip-index", action="store_true", help="Skip index files")
    parser.add_argument("--force", action="store_true", help="Re-download existing files")
    parser.add_argument("--missing", action="store_true", help="Show missing files only")
    parser.add_argument("--resume", action="store_true", help="Resume from where left off")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Determine date range
    if args.years:
        # --years goes back from today
        end_date = date.today()
        start_date = end_date - timedelta(days=args.years * 365)
    elif args.start and args.end:
        start_date = date.fromisoformat(args.start)
        end_date = date.fromisoformat(args.end)
    elif args.resume:
        # Default to 5 years if resuming
        end_date = date.today()
        start_date = end_date - timedelta(days=5 * 365)
    else:
        # Default: 5 years of historical data
        end_date = date.today()
        start_date = end_date - timedelta(days=5 * 365)

    downloader = NSEHistoricalDownloader()

    if args.missing:
        downloader.show_missing(start_date, end_date)
        return

    # Run download
    stats = downloader.run(
        start_date=start_date,
        end_date=end_date,
        download_bhavcopy=not args.skip_bhavcopy,
        download_index=not args.skip_index,
        force=args.force,
    )

    print(f"\n=== Download Summary ===")
    print(f"Days processed: {stats['days_processed']}")
    print(f"Bhavcopy: {stats['bhavcopy_downloaded']} downloaded, {stats['bhavcopy_skipped']} skipped, {stats['bhavcopy_failed']} failed")
    print(f"Index: {stats['index_downloaded']} downloaded, {stats['index_skipped']} skipped, {stats['index_failed']} failed")
    print(f"\nFiles saved to: {downloader.data_dir}")


if __name__ == "__main__":
    main()