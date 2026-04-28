"""CLI entry point — trigger the ingestion framework for any data source.

Wires up the correct ``Pipeline`` (fetcher + loader) for a given source and
runs it for the requested trade date. Use ``--source all`` to run every
automated source in one invocation.

Usage::

    # Single source for today
    python -m ingestion.framework.run_pipeline --source bhavcopy

    # Single source for a specific date
    python -m ingestion.framework.run_pipeline --source wk52 --date 2024-01-15

    # All automated sources for a date
    python -m ingestion.framework.run_pipeline --source all --date 2024-01-15

    # Local-only mode (skip HTTP, read directly from data/raw/<source>/)
    python -m ingestion.framework.run_pipeline --source bhavcopy --local-only

    # Backfill a date range (skips weekends)
    python -m ingestion.framework.run_pipeline --source bhavcopy \\
        --start 2024-01-01 --end 2024-01-31

Available sources:
    bhavcopy           — Source A → fact_eod_price
    wk52               — Source B → fact_52wk
    constituents       — Source C → dim_nifty50_constituent
    reconstitution     — Source D → dim_nifty50_constituent (local-only)
    corporate-actions  — Source E → fact_corporate_action
    event-calendar     — Source F → fact_corporate_event
    announcements      — Source G → fact_corporate_event
    intraday           — Source H → not implemented (raises)
    all                — All automated sources (A, B, C, E, F, G)
"""
from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

from config.settings import settings
from ingestion.framework.fetchers.base import BaseFetcher, FetchError
from ingestion.framework.fetchers.hybrid_fetcher import HybridFetcher
from ingestion.framework.fetchers.http_fetcher import NseHttpFetcher, SourceType
from ingestion.framework.fetchers.local_fetcher import LocalFetcher
from ingestion.framework.loaders.announcements_loader import AnnouncementsLoader
from ingestion.framework.loaders.base import BaseLoader
from ingestion.framework.loaders.constituents_loader import ConstituentsLoader
from ingestion.framework.loaders.corporate_actions_loader import (
    CorporateActionsFrameworkLoader,
)
from ingestion.framework.loaders.eod_price_loader import EodPriceLoader
from ingestion.framework.loaders.event_calendar_loader import EventCalendarLoader
from ingestion.framework.loaders.intraday_loader import IntradayLoader
from ingestion.framework.loaders.reconstitution_loader import ReconstitutionLoader
from ingestion.framework.loaders.wk52_loader import Wk52Loader
from ingestion.framework.pipeline import Pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ingestion.framework.run_pipeline")


@dataclass(frozen=True)
class SourceSpec:
    """Wiring instructions for one data source."""

    name: str                        # CLI name, e.g. "bhavcopy"
    table: str                       # Target DB table for ingestion_log
    drop_subdir: str                 # data/raw/<subdir>/
    loader_factory: Callable[[], BaseLoader]
    http_source: SourceType | None   # None for local-only sources (D)
    local_only: bool = False         # True for D — no HTTP fetcher
    not_implemented: bool = False    # True for H — stub


# Single source-of-truth registry.
# Order matters for ``--source all`` — bhavcopy first because Wk52Loader
# enriches pct_from_high/low using fact_eod_price.close.
SOURCES: dict[str, SourceSpec] = {
    "bhavcopy": SourceSpec(
        name="bhavcopy",
        table="fact_eod_price",
        drop_subdir="bhavcopy",
        loader_factory=EodPriceLoader,
        http_source=SourceType.BHAVCOPY,
    ),
    "wk52": SourceSpec(
        name="wk52",
        table="fact_52wk",
        drop_subdir="52wk",
        loader_factory=Wk52Loader,
        http_source=SourceType.WK52,
    ),
    "constituents": SourceSpec(
        name="constituents",
        table="dim_nifty50_constituent",
        drop_subdir="constituents",
        loader_factory=ConstituentsLoader,
        http_source=SourceType.CONSTITUENTS,
    ),
    "reconstitution": SourceSpec(
        name="reconstitution",
        table="dim_nifty50_constituent",
        drop_subdir="reconstitution",
        loader_factory=ReconstitutionLoader,
        http_source=None,
        local_only=True,
    ),
    "corporate-actions": SourceSpec(
        name="corporate-actions",
        table="fact_corporate_action",
        drop_subdir="corporate_actions",
        loader_factory=CorporateActionsFrameworkLoader,
        http_source=SourceType.CORPORATE_ACTIONS,
    ),
    "event-calendar": SourceSpec(
        name="event-calendar",
        table="fact_corporate_event",
        drop_subdir="event_calendar",
        loader_factory=EventCalendarLoader,
        http_source=SourceType.EVENT_CALENDAR,
    ),
    "announcements": SourceSpec(
        name="announcements",
        table="fact_corporate_event",
        drop_subdir="announcements",
        loader_factory=AnnouncementsLoader,
        http_source=SourceType.ANNOUNCEMENTS,
    ),
    "intraday": SourceSpec(
        name="intraday",
        table="fact_intraday",
        drop_subdir="intraday",
        loader_factory=IntradayLoader,
        http_source=None,
        not_implemented=True,
    ),
}

# Sources included when ``--source all`` is passed.
# H is excluded because the loader raises NotImplementedError.
ALL_AUTOMATED = ["bhavcopy", "wk52", "constituents",
                 "corporate-actions", "event-calendar", "announcements"]


def _drop_dir(spec: SourceSpec) -> Path:
    """Resolve and create the manual-drop directory for *spec*."""
    path = settings.project_root / "data" / "raw" / spec.drop_subdir
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_fetcher(spec: SourceSpec, local_only: bool = False) -> BaseFetcher:
    """Construct the fetcher for *spec*.

    Args:
        spec: Source wiring spec from :data:`SOURCES`.
        local_only: If True, skip HTTP and use only the local drop folder.

    Returns:
        A :class:`BaseFetcher` ready for the pipeline.

    Raises:
        ValueError: If ``local_only=False`` and the source is local-only by
            design (e.g. reconstitution) — caller should not request HTTP.
    """
    drop = _drop_dir(spec)

    if spec.local_only:
        return LocalFetcher(source_dir=drop)

    if local_only:
        return LocalFetcher(source_dir=drop)

    assert spec.http_source is not None  # not local_only → http_source set
    return HybridFetcher(
        http=NseHttpFetcher(source=spec.http_source),
        local=LocalFetcher(source_dir=drop),
    )


def run_one(spec: SourceSpec, trade_date: date, local_only: bool = False) -> int:
    """Build and run the pipeline for one source/date.

    Args:
        spec: Source wiring spec.
        trade_date: NSE trading date to ingest.
        local_only: If True, skip HTTP fetch and read from local drop only.

    Returns:
        Number of rows upserted.

    Raises:
        Exception: Any fetch/load failure (already written to ingestion_log
            by the :class:`Pipeline`).
    """
    if spec.not_implemented:
        logger.warning(
            "[%s] is a placeholder (vendor integration pending) — skipping",
            spec.name,
        )
        return 0

    fetcher = build_fetcher(spec, local_only=local_only)
    pipeline = Pipeline(
        fetcher=fetcher,
        loader=spec.loader_factory(),
        source_name=spec.name,
        table_name=spec.table,
    )
    return pipeline.run(trade_date)


def run_range(
    spec: SourceSpec,
    start: date,
    end: date,
    local_only: bool = False,
) -> dict[date, int | str]:
    """Run *spec* for every trading day in ``[start, end]`` (skips weekends).

    Args:
        spec: Source wiring spec.
        start: First date (inclusive).
        end: Last date (inclusive).
        local_only: If True, skip HTTP fetch.

    Returns:
        Dict mapping each trade date to the row count or error string.
    """
    results: dict[date, int | str] = {}
    cur = start
    while cur <= end:
        if cur.weekday() < 5:  # Mon–Fri only
            try:
                results[cur] = run_one(spec, cur, local_only=local_only)
            except Exception as exc:  # noqa: BLE001 — already logged
                results[cur] = f"FAILED: {exc}"
                logger.error("[%s] %s failed: %s", spec.name, cur, exc)
        cur += timedelta(days=1)
    return results


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Trigger ingestion framework pipeline for one or all data sources.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--source",
        required=True,
        choices=list(SOURCES.keys()) + ["all"],
        help="Data source to ingest (or 'all' for every automated source).",
    )

    date_group = parser.add_mutually_exclusive_group()
    date_group.add_argument(
        "--date",
        type=_parse_date,
        help="Trade date (YYYY-MM-DD). Defaults to today.",
    )
    date_group.add_argument(
        "--start",
        type=_parse_date,
        help="Start date for backfill (YYYY-MM-DD). Use with --end.",
    )
    parser.add_argument(
        "--end",
        type=_parse_date,
        help="End date for backfill (YYYY-MM-DD). Use with --start.",
    )

    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Skip HTTP fetch — read only from data/raw/<source>/.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="With --source all: continue to the next source if one fails.",
    )

    args = parser.parse_args()

    # Resolve date(s)
    if args.start and not args.end:
        parser.error("--start requires --end")
    if args.end and not args.start:
        parser.error("--end requires --start")

    range_mode = args.start is not None
    single_date = args.date or date.today()

    # Resolve sources to run
    source_names = ALL_AUTOMATED if args.source == "all" else [args.source]
    specs = [SOURCES[name] for name in source_names]

    # Execute
    overall_ok = True
    for spec in specs:
        try:
            if range_mode:
                results = run_range(spec, args.start, args.end, local_only=args.local_only)
                ok_count = sum(1 for v in results.values() if isinstance(v, int))
                logger.info(
                    "[%s] Backfill complete: %d/%d days succeeded",
                    spec.name, ok_count, len(results),
                )
                for d, v in results.items():
                    print(f"  {spec.name} {d}: {v}")
            else:
                rows = run_one(spec, single_date, local_only=args.local_only)
                logger.info("[%s] %s — %d rows", spec.name, single_date, rows)
                print(f"{spec.name} {single_date}: {rows} rows")
        except Exception as exc:  # noqa: BLE001
            overall_ok = False
            logger.error("[%s] FAILED — %s", spec.name, exc)
            print(f"{spec.name}: FAILED — {exc}", file=sys.stderr)
            if not args.continue_on_error:
                return 1

    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
