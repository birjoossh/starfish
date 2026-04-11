"""Daily ingestion entry point.

Runs the full ingestion pipeline:
1. Download bhavcopy from NSE (or read from local source)
2. Parse with header validation and series filter
3. Load into fact_eod_price with idempotent upsert
4. Log the ingestion run

Usage:
    python -m ingestion.daily_run                          # Today's data
    python -m ingestion.daily_run --date 2024-01-15        # Specific date
    python -m ingestion.daily_run --backfill 252           # Last 252 trading days
    python -m ingestion.daily_run --local /path/to/csvs    # Local file source
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

from config.settings import settings
from ingestion.bhavcopy_loader import BhavcopyLoader
from ingestion.bhavcopy_parser import BhavcopyParseError, BhavcopyParser
from ingestion.local_source import LocalSource
from ingestion.nse_client import CircuitBreakerOpen, NSEClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def ingest_single_date(
    trade_date: date,
    local_dir: Path | None = None,
) -> dict:
    """Ingest bhavcopy for a single date.

    Tries NSE download first, falls back to local source if circuit breaker trips.

    Returns:
        Dict with ingestion stats.
    """
    parser = BhavcopyParser()
    loader = BhavcopyLoader()

    csv_path = None
    source_file = ""

    # Try NSE download
    if local_dir is None:
        client = NSEClient()
        try:
            csv_path = client.download_bhavcopy(trade_date)
            source_file = csv_path.name
            logger.info(f"Downloaded from NSE: {csv_path}")
        except CircuitBreakerOpen as e:
            logger.error(f"Circuit breaker open: {e}")
            if settings.local_data_dir:
                local_dir = settings.local_data_dir
            else:
                return {"status": "failed", "error": str(e)}
        except Exception as e:
            logger.warning(f"NSE download failed: {e}")
            if settings.local_data_dir:
                local_dir = settings.local_data_dir
            else:
                return {"status": "failed", "error": str(e)}

    # Fall back to local source
    if csv_path is None and local_dir is not None:
        try:
            source = LocalSource(local_dir)
            csv_path = source.get_bhavcopy(trade_date)
            source_file = csv_path.name
            logger.info(f"Using local file: {csv_path}")
        except FileNotFoundError as e:
            logger.warning(str(e))
            return {"status": "failed", "error": str(e)}

    if csv_path is None:
        return {"status": "failed", "error": "No data source available"}

    # Parse
    try:
        df = parser.parse(csv_path, trade_date=trade_date, source_file=source_file)
    except BhavcopyParseError as e:
        logger.error(f"Parse failed: {e}")
        return {"status": "failed", "error": str(e)}

    # Load
    stats = loader.load(df, source_file=source_file)
    stats["date"] = str(trade_date)
    return stats


def backfill(start_date: date, end_date: date, local_dir: Path | None = None) -> list[dict]:
    """Backfill a date range.

    For NSE downloads, uses the client's range method for rate limiting.
    For local source, iterates dates and loads available files.
    """
    results = []
    current = start_date

    while current <= end_date:
        if current.weekday() < 5:  # Skip weekends
            stats = ingest_single_date(current, local_dir)
            results.append(stats)
            logger.info(f"[{current}] {stats['status']}: {stats.get('rows_inserted', 0)} rows")
        current += timedelta(days=1)

    success = sum(1 for r in results if r["status"] == "success")
    logger.info(f"Backfill complete: {success}/{len(results)} dates succeeded")
    return results


def main():
    parser = argparse.ArgumentParser(description="Nifty 50 bhavcopy ingestion")
    parser.add_argument("--date", type=str, help="Specific date (YYYY-MM-DD)")
    parser.add_argument("--backfill", type=int, help="Backfill N trading days from today")
    parser.add_argument("--start", type=str, help="Backfill start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="Backfill end date (YYYY-MM-DD)")
    parser.add_argument("--local", type=str, help="Local CSV directory (overrides NSE download)")

    args = parser.parse_args()
    local_dir = Path(args.local) if args.local else None

    if args.date:
        trade_date = date.fromisoformat(args.date)
        stats = ingest_single_date(trade_date, local_dir)
        print(f"Result: {stats}")

    elif args.backfill:
        end_date = date.today()
        start_date = end_date - timedelta(days=args.backfill)
        backfill(start_date, end_date, local_dir)

    elif args.start and args.end:
        start_date = date.fromisoformat(args.start)
        end_date = date.fromisoformat(args.end)
        backfill(start_date, end_date, local_dir)

    else:
        # Default: today
        stats = ingest_single_date(date.today(), local_dir)
        print(f"Result: {stats}")


if __name__ == "__main__":
    main()
