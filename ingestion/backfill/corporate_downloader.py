#!/usr/bin/env python3
"""Corporate actions/events backfill downloader.

Downloads corporate actions and events data from NSE for a specified date range.

IMPORTANT: NSE does NOT provide historical date-specific CSV archives for
corporate actions/events like they do for bhavcopy. The data must be scraped
from their website (https://www.nseindia.com/market-data/corporate-actions).

This script uses the NSEScraper to fetch current data. For true historical
backfill, you would need to have run this script periodically to capture data
over time.

Usage:
    # Download current corporate data from NSE
    python -m ingestion.backfill.corporate_downloader --days 365

    # Download specific date range
    python -m ingestion.backfill.corporate_downloader --start 2025-04-19 --end 2026-04-19

    # Download to a custom directory
    python -m ingestion.backfill.corporate_downloader --days 365 --output data/corporate

    # Dry run - show what would be done
    python -m ingestion.backfill.corporate_downloader --days 365 --dry-run

    # Show missing files
    python -m ingestion.backfill.corporate_downloader --days 365 --missing
"""

import argparse
import logging
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Rate limiting
MIN_REQUEST_INTERVAL = 2.0  # seconds between requests
MAX_DAILY_REQUESTS = 500    # NSE daily limit approximation
CIRCUIT_BREAKER_THRESHOLD = 5  # consecutive failures before pause


class CorporateBackfillDownloader:
    """Download corporate actions/events data from NSE."""

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or (settings.project_root / "data" / "corporate")
        self.actions_dir = self.data_dir / "actions"
        self.events_dir = self.data_dir / "events"

        self.actions_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir.mkdir(parents=True, exist_ok=True)

        self.request_count = 0
        self.consecutive_failures = 0
        self.last_request_time = 0

    def _rate_limit(self):
        """Apply rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)
        self.last_request_time = time.time()

    def _ca_filename(self, trade_date: date) -> str:
        """Generate corporate actions filename."""
        return f"ca_{trade_date.strftime('%d%m%Y')}.csv"

    def _ce_filename(self, trade_date: date) -> str:
        """Generate corporate events filename."""
        return f"ce_{trade_date.strftime('%d%m%Y')}.csv"

    def download_corporate_actions(self, trade_date: date, force: bool = False) -> dict:
        """Download corporate actions data for a specific date.

        NSE doesn't provide date-specific CA files - we download the current
        data from their website via the NSEScraper which contains upcoming actions.

        The scraper fetches from https://www.nseindia.com/market-data/corporate-actions

        Returns:
            Dict with status and path info.
        """
        output_path = self.actions_dir / self._ca_filename(trade_date)

        if output_path.exists() and not force:
            return {"status": "skipped", "reason": "exists", "path": output_path}

        self._rate_limit()

        try:
            from ingestion.nse_scraper import NSEScraper
            import asyncio

            scraper = NSEScraper()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            events = loop.run_until_complete(scraper.scrape_corporate_actions())
            loop.close()

            if events:
                df = pd.DataFrame(events)
                output_path = self.actions_dir / f"ca_{trade_date.strftime('%d%m%Y')}.csv"
                df.to_csv(output_path, index=False)

                self.request_count += 1
                self.consecutive_failures = 0
                logger.info(f"Downloaded corporate actions: {output_path.name} ({len(events)} events)")
                return {"status": "success", "path": output_path, "events": len(events)}
            else:
                logger.warning(f"No corporate actions data found for {trade_date}")
                return {"status": "skipped", "reason": "no data", "date": trade_date}

        except Exception as e:
            self.consecutive_failures += 1
            logger.warning(f"Failed to download corporate actions for {trade_date}: {e}")

            if self.consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
                logger.error("Circuit breaker triggered - too many failures")
                return {"status": "circuit_breaker", "failures": self.consecutive_failures}

            return {"status": "failed", "error": str(e)}

    def download_corporate_events(self, trade_date: date, force: bool = False) -> dict:
        """Download corporate events/announcements data.

        Returns:
            Dict with status and path info.
        """
        output_path = self.events_dir / self._ce_filename(trade_date)

        if output_path.exists() and not force:
            return {"status": "skipped", "reason": "exists", "path": output_path}

        self._rate_limit()

        try:
            from ingestion.nse_scraper import NSEScraper
            import asyncio

            scraper = NSEScraper()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            events = loop.run_until_complete(scraper.scrape_corporate_actions())
            loop.close()

            if events:
                df = pd.DataFrame(events)
                output_path = self.events_dir / f"ce_{trade_date.strftime('%d%m%Y')}.csv"
                df.to_csv(output_path, index=False)

                self.request_count += 1
                self.consecutive_failures = 0
                logger.info(f"Downloaded corporate events: {output_path.name} ({len(events)} events)")
                return {"status": "success", "path": output_path, "events": len(events)}
            else:
                logger.warning(f"No corporate events data found for {trade_date}")
                return {"status": "skipped", "reason": "no data", "date": trade_date}

        except Exception as e:
            self.consecutive_failures += 1
            logger.warning(f"Failed to download corporate events for {trade_date}: {e}")

            if self.consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
                logger.error("Circuit breaker triggered - too many failures")
                return {"status": "circuit_breaker", "failures": self.consecutive_failures}

            return {"status": "failed", "error": str(e)}

    def run(self, start_date: date, end_date: date, force: bool = False) -> dict:
        """Run download for date range.

        Note: NSE provides current/upcoming corporate data, not historical archives.
        This script downloads the current files and saves them with date-stamped names.
        For true historical data, you would need to have run this script periodically.

        Returns:
            Dict with download statistics.
        """
        if start_date > end_date:
            start_date, end_date = end_date, start_date

        logger.info(f"Starting corporate data download: {start_date} to {end_date}")

        stats = {
            "total_dates": (end_date - start_date).days + 1,
            "actions_downloaded": 0,
            "actions_skipped": 0,
            "actions_failed": 0,
            "events_downloaded": 0,
            "events_skipped": 0,
            "events_failed": 0,
        }

        current = start_date
        while current <= end_date:
            if current.weekday() >= 5:  # Skip weekends
                current += timedelta(days=1)
                continue

            # Download corporate actions
            result = self.download_corporate_actions(current, force=force)
            if result["status"] == "success":
                stats["actions_downloaded"] += 1
            elif result["status"] == "skipped":
                stats["actions_skipped"] += 1
            else:
                stats["actions_failed"] += 1

            # Download corporate events
            result = self.download_corporate_events(current, force=force)
            if result["status"] == "success":
                stats["events_downloaded"] += 1
            elif result["status"] == "skipped":
                stats["events_skipped"] += 1
            else:
                stats["events_failed"] += 1

            current += timedelta(days=1)

            if self.request_count >= MAX_DAILY_REQUESTS:
                logger.warning(f"Daily request limit ({MAX_DAILY_REQUESTS}) reached")
                break

            if self.consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
                logger.error("Stopping due to circuit breaker")
                break

        logger.info(f"Download complete: {stats}")
        return stats

    def show_missing(self, start_date: date, end_date: date):
        """Show which files are missing."""
        dates = []
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:
                dates.append(current)
            current += timedelta(days=1)

        actions_missing = []
        events_missing = []

        for d in dates:
            if not (self.actions_dir / self._ca_filename(d)).exists():
                actions_missing.append(d)
            if not (self.events_dir / self._ce_filename(d)).exists():
                events_missing.append(d)

        print(f"\nDate range: {start_date} to {end_date}")
        print(f"Trading days: {len(dates)}")
        print(f"\nCorporate Actions: {len(actions_missing)} missing out of {len(dates)}")
        if actions_missing:
            print(f"  First missing: {actions_missing[0]}")
            print(f"  Last missing: {actions_missing[-1]}")

        print(f"\nCorporate Events: {len(events_missing)} missing out of {len(dates)}")
        if events_missing:
            print(f"  First missing: {events_missing[0]}")
            print(f"  Last missing: {events_missing[-1]}")


def main():
    parser = argparse.ArgumentParser(
        description="Download corporate actions/events data for backfill"
    )
    parser.add_argument(
        "--days",
        type=int,
        help="Number of days to download from today (default: 365 for 1 year)",
    )
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--output",
        type=str,
        help="Output directory for downloaded files",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download existing files",
    )
    parser.add_argument(
        "--missing",
        action="store_true",
        help="Show missing files only",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be downloaded without downloading",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Determine date range
    if args.days:
        end_date = date.today()
        start_date = end_date - timedelta(days=args.days)
    elif args.start and args.end:
        start_date = date.fromisoformat(args.start)
        end_date = date.fromisoformat(args.end)
    else:
        # Default: 1 year (365 days)
        end_date = date.today()
        start_date = end_date - timedelta(days=365)

    downloader = CorporateBackfillDownloader(
        data_dir=Path(args.output) if args.output else None
    )

    if args.missing:
        downloader.show_missing(start_date, end_date)
        return

    if args.dry_run:
        logger.info(f"[DRY RUN] Would process {start_date} to {end_date}")
        logger.info("  Note: NSE doesn't provide historical CA/CE CSV archives.")
        logger.info("  This will scrape current data from NSE website.")
        return

    # Run download
    stats = downloader.run(
        start_date=start_date,
        end_date=end_date,
        force=args.force,
    )

    print(f"\n=== Download Summary ===")
    print(f"Date range: {start_date} to {end_date}")
    print(f"Corporate Actions: {stats['actions_downloaded']} downloaded, "
          f"{stats['actions_skipped']} skipped, {stats['actions_failed']} failed")
    print(f"Corporate Events: {stats['events_downloaded']} downloaded, "
          f"{stats['events_skipped']} skipped, {stats['events_failed']} failed")
    print(f"\nFiles saved to: {downloader.data_dir}")


if __name__ == "__main__":
    main()
