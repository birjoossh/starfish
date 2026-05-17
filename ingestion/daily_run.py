"""Daily ingestion entry point.

Runs the full ingestion pipeline:
1. Download bhavcopy from NSE (or read from local source)
2. Parse with header validation and series filter
3. Load into fact_eod_price with idempotent upsert
4. Log the ingestion run
5. Optional: corporate actions / events CSVs (Phase E), then optional signal recompute

Usage:
    python -m ingestion.daily_run                          # Today's data
    python -m ingestion.daily_run --date 2024-01-15        # Specific date
    python -m ingestion.daily_run --backfill 252           # Last 252 trading days
    python -m ingestion.daily_run --local /path/to/csvs    # Local file source
    python -m ingestion.daily_run --date 2024-01-17 --corporate-actions data/ca.csv \\
        --corporate-events data/ann.csv --compute-signals
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
from ingestion.download_validator import validate_bhavcopy_size, DownloadValidationError
from ingestion.local_source import LocalSource
from ingestion.nse_client import CircuitBreakerOpen, NSEClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _ingest_index_price(trade_date: date) -> int:
    """Download + load the Nifty 50 close for ``trade_date``.

    Returns the number of rows inserted (1 on success, 0 on miss/holiday).
    Reuses ``BackfillOrchestrator`` cache + download + upsert plumbing so the
    daily path stays in sync with the bulk-backfill path without duplicating
    code (TODO-106 daily wiring).
    """
    from archives.backfill.orchestrator import BackfillOrchestrator
    from ingestion.nse_client import CircuitBreakerOpen

    orch = BackfillOrchestrator()
    path = orch._get_index_cache_path(trade_date)
    if not path.exists():
        try:
            path = orch.download_index_csv(trade_date)
        except CircuitBreakerOpen as e:
            logger.error(f"Index download — circuit breaker open: {e}")
            return 0
        except Exception as e:
            if orch._is_holiday(e):
                logger.info(f"Index — holiday/no data on {trade_date}")
                orch.client.reset_circuit()
            else:
                logger.warning(f"Index download failed for {trade_date}: {e}")
            return 0
    if not path.exists():
        return 0
    return orch.parse_and_load_index_csv(path, trade_date)


def _ingest_mto(trade_date: date, local_dir: Path | None) -> dict | None:
    """Run the MTO T+1 delivery update for ``trade_date``.

    Returns ``None`` if no MTO file is available locally and the NSE
    download fails (treated as soft-fail — bhavcopy still loaded fine).
    """
    from ingestion.mto_parser import MTOParser, MTOParseError
    from ingestion.mto_loader import MTOLoader

    mto_path: Path | None = None
    if local_dir is not None:
        candidate = Path(local_dir) / f"MTO_{trade_date.strftime('%d%m%Y')}.DAT"
        if candidate.exists():
            mto_path = candidate

    if mto_path is None:
        try:
            client = NSEClient()
            mto_path = client.download_mto(trade_date)
        except (CircuitBreakerOpen, Exception) as e:
            logger.warning(f"MTO unavailable for {trade_date}: {e}")
            return None

    try:
        df = MTOParser().parse(mto_path, trade_date=trade_date)
    except MTOParseError as e:
        logger.warning(f"MTO parse failed for {trade_date}: {e}")
        return None

    return MTOLoader().load(df, source_file=mto_path.name)


def ingest_single_date(
    trade_date: date,
    local_dir: Path | None = None,
    corporate_actions_csv: Path | None = None,
    corporate_events_csv: Path | None = None,
    compute_signals_flag: bool = False,
    skip_index: bool = False,
    skip_mto: bool = False,
) -> dict:
    """Ingest bhavcopy + Nifty 50 index + MTO delivery for a single date.

    Tries NSE download first, falls back to local source if circuit breaker trips.
    Index ingestion (TODO-106) runs after bhavcopy unless ``skip_index=True``.
    MTO delivery update (TODO-103) runs after bhavcopy unless ``skip_mto=True``;
    safe to skip when running same-day before NSE publishes the MTO file.

    Returns:
        Dict with ingestion stats. Adds ``index_rows`` and ``mto_loaded``
        keys for the optional steps.
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

    # Validate file size and row count (TODO-105)
    try:
        validate_bhavcopy_size(csv_path)
    except DownloadValidationError as e:
        logger.error(f"Download validation failed: {e}")
        return {"status": "failed", "error": f"Corrupted download: {e}"}

    # Parse
    try:
        df = parser.parse(csv_path, trade_date=trade_date, source_file=source_file)
    except BhavcopyParseError as e:
        logger.error(f"Parse failed: {e}")
        return {"status": "failed", "error": str(e)}

    # Load
    stats = loader.load(df, source_file=source_file)
    stats["date"] = str(trade_date)

    # Nifty 50 index close — feeds RS-vs-Nifty across mart_stock_signals + §03.
    if skip_index:
        stats["index_rows"] = None
    else:
        try:
            stats["index_rows"] = _ingest_index_price(trade_date)
        except Exception as e:
            logger.warning(f"Index ingestion failed for {trade_date}: {e}")
            stats["index_rows"] = 0

    # MTO delivery update — T+1 patch for bhavcopy delivery_qty/delivery_pct.
    if skip_mto:
        stats["mto_loaded"] = None
    else:
        try:
            mto_result = _ingest_mto(trade_date, local_dir)
            stats["mto_loaded"] = mto_result
        except Exception as e:
            logger.warning(f"MTO ingestion failed for {trade_date}: {e}")
            stats["mto_loaded"] = None

    if corporate_actions_csv is not None and corporate_actions_csv.exists():
        from ingestion.corporate_actions_parser import CorporateActionsParser
        from ingestion.corporate_actions_loader import CorporateActionsLoader

        ca_df = CorporateActionsParser().parse(corporate_actions_csv, as_of=trade_date)
        stats["corporate_actions_loaded"] = CorporateActionsLoader().load(ca_df)
    else:
        stats["corporate_actions_loaded"] = None

    if corporate_events_csv is not None and corporate_events_csv.exists():
        from ingestion.corporate_events_ingestor import CorporateEventsIngestor
        from ingestion.corporate_events_loader import CorporateEventsLoader

        ev_df = CorporateEventsIngestor().ingest(corporate_events_csv, calc_date=trade_date)
        stats["corporate_events_loaded"] = CorporateEventsLoader().load(ev_df)
    else:
        stats["corporate_events_loaded"] = None

    if compute_signals_flag:
        from analytics.compute_signals import compute_signals as run_compute_signals

        stats["signals_rows"] = run_compute_signals(trade_date)
    else:
        stats["signals_rows"] = None

    return stats


def backfill(
    start_date: date,
    end_date: date,
    local_dir: Path | None = None,
    corporate_actions_csv: Path | None = None,
    corporate_events_csv: Path | None = None,
    compute_signals_flag: bool = False,
    skip_index: bool = False,
    skip_mto: bool = False,
) -> list[dict]:
    """Backfill a date range.

    For NSE downloads, uses the client's range method for rate limiting.
    For local source, iterates dates and loads available files.
    """
    results = []
    current = start_date

    while current <= end_date:
        if current.weekday() < 5:  # Skip weekends
            stats = ingest_single_date(
                current,
                local_dir,
                corporate_actions_csv=corporate_actions_csv,
                corporate_events_csv=corporate_events_csv,
                compute_signals_flag=compute_signals_flag,
                skip_index=skip_index,
                skip_mto=skip_mto,
            )
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
    parser.add_argument(
        "--corporate-actions",
        type=str,
        help="Path to NSE corporate actions CSV (loaded after bhavcopy for this date)",
    )
    parser.add_argument(
        "--corporate-events",
        type=str,
        help="Path to announcements CSV for fact_corporate_event (fixture-friendly)",
    )
    parser.add_argument(
        "--compute-signals",
        action="store_true",
        help="Run analytics.compute_signals for the trade date after ingestion",
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Skip the Nifty 50 index-price ingestion step (TODO-106)",
    )
    parser.add_argument(
        "--skip-mto",
        action="store_true",
        help="Skip the MTO delivery update (TODO-103). Safe for same‑day runs before NSE publishes MTO.",
    )

    args = parser.parse_args()
    local_dir = Path(args.local) if args.local else None
    corp_act = Path(args.corporate_actions) if args.corporate_actions else None
    corp_ev = Path(args.corporate_events) if args.corporate_events else None
    do_signals = bool(args.compute_signals)
    skip_index = bool(args.skip_index)
    skip_mto = bool(args.skip_mto)

    if args.date:
        trade_date = date.fromisoformat(args.date)
        stats = ingest_single_date(
            trade_date,
            local_dir,
            corporate_actions_csv=corp_act,
            corporate_events_csv=corp_ev,
            compute_signals_flag=do_signals,
            skip_index=skip_index,
            skip_mto=skip_mto,
        )
        print(f"Result: {stats}")

    elif args.backfill:
        end_date = date.today()
        start_date = end_date - timedelta(days=args.backfill)
        backfill(
            start_date,
            end_date,
            local_dir,
            corporate_actions_csv=corp_act,
            corporate_events_csv=corp_ev,
            compute_signals_flag=do_signals,
            skip_index=skip_index,
            skip_mto=skip_mto,
        )

    elif args.start and args.end:
        start_date = date.fromisoformat(args.start)
        end_date = date.fromisoformat(args.end)
        backfill(
            start_date,
            end_date,
            local_dir,
            corporate_actions_csv=corp_act,
            corporate_events_csv=corp_ev,
            compute_signals_flag=do_signals,
            skip_index=skip_index,
            skip_mto=skip_mto,
        )

    else:
        # Default: today
        stats = ingest_single_date(
            date.today(),
            local_dir,
            corporate_actions_csv=corp_act,
            corporate_events_csv=corp_ev,
            compute_signals_flag=do_signals,
            skip_index=skip_index,
            skip_mto=skip_mto,
        )
        print(f"Result: {stats}")


if __name__ == "__main__":
    main()
