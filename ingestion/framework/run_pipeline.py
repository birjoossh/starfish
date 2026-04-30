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

    # Load a SPECIFIC local file (date-based lookup is bypassed)
    python -m ingestion.framework.run_pipeline --source dim-stock \\
        --date 2024-01-15 --local-file /tmp/some_security.csv

    # Backfill a date range (skips weekends)
    python -m ingestion.framework.run_pipeline --source bhavcopy \\
        --start 2024-01-01 --end 2024-01-31

After a successful load, the source file is moved to
``data/processed/<source>/`` so the raw drop folder only ever contains
files awaiting ingestion. Rows dropped during parsing are written to
``logs/<source>/bad_records/<original_filename>.csv``.

Available sources:
    dim-stock          — Source J → dim_stock (NSE security master)
    bhavcopy           — Source A → fact_eod_price
    wk52               — Source B → fact_52wk
    constituents       — Source C → dim_nifty50_constituent
    reconstitution     — Source D → dim_nifty50_constituent (local-only)
    corporate-actions  — Source E → fact_corporate_action
    event-calendar     — Source F → fact_corporate_event
    announcements      — Source G → fact_corporate_event
    intraday           — Source H → not implemented (raises)
    all                — All automated sources (J, A, B, C, E, F, G)
"""
from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

from config.settings import settings
from ingestion.framework.bad_records import BadRecordsWriter
from ingestion.framework.json_bad_records import JsonBadRecordsWriter
from ingestion.framework.fetchers.base import BaseFetcher, FetchError
from ingestion.framework.fetchers.hybrid_fetcher import HybridFetcher
from ingestion.framework.fetchers.http_fetcher import NseHttpFetcher, SourceType
from ingestion.framework.fetchers.local_fetcher import FixedFileFetcher, LocalFetcher
from ingestion.framework.loaders.announcements_loader import AnnouncementsLoader
from ingestion.framework.loaders.base import BaseLoader
from ingestion.framework.loaders.constituents_loader import ConstituentsLoader
from ingestion.framework.loaders.corporate_actions_loader import (
    CorporateActionsFrameworkLoader,
)
from ingestion.framework.loaders.dim_stock_loader import DimStockLoader
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
    """Wiring instructions for one data source.

    Attributes:
        name: CLI-facing name, e.g. ``"bhavcopy"``.
        table: Target DB table for ``ingestion_log``.
        drop_subdir: Subdirectory under ``data/raw/`` for the local-drop folder.
        loader_factory: Callable that returns a fresh :class:`BaseLoader`.
            Must accept ``**kwargs`` and forward (or ignore) any of:
            ``bad_records_writer``.
        http_source: Which :class:`SourceType` the HTTP fetcher serves.
            ``None`` for local-only sources (D).
        local_patterns: Glob templates the local fetcher uses to find files
            for a given trade date. Each may contain ``{ddmmyyyy}``,
            ``{yyyymmdd}``, ``{ddmonyyyy}`` placeholders.
        local_only: True for sources that have no HTTP endpoint (D).
        not_implemented: True for stub loaders (H) — pipeline is skipped.
        supports_bad_records: True for loaders that accept a CSV
            ``bad_records_writer`` kwarg (parsing-time drops).
        supports_json_bad_records: True for the corporate-event loaders
            that accept a :class:`JsonBadRecordsWriter` for FK-violation
            drops (symbols not in ``dim_stock``). Preserves the original
            NSE JSON record shape in the bad-records file.
    """

    name: str
    table: str
    drop_subdir: str
    loader_factory: Callable[..., BaseLoader]
    http_source: Optional[SourceType]
    local_patterns: tuple[str, ...] = field(default_factory=tuple)
    local_only: bool = False
    not_implemented: bool = False
    supports_bad_records: bool = False
    supports_json_bad_records: bool = False


# Single source-of-truth registry.
# Order matters for ``--source all``:
#   - dim-stock first: populates the master FK target for every other table.
#   - bhavcopy second: Wk52Loader enriches pct_from_high/low using fact_eod_price.close.
SOURCES: dict[str, SourceSpec] = {
    "dim-stock": SourceSpec(
        name="dim-stock",
        table="dim_stock",
        drop_subdir="dim_stock",
        loader_factory=DimStockLoader,
        http_source=SourceType.DIM_STOCK,
        local_patterns=("NSE_CM_security_{ddmmyyyy}.csv",),
        supports_bad_records=True,
    ),
    "bhavcopy": SourceSpec(
        name="bhavcopy",
        table="fact_eod_price",
        drop_subdir="bhavcopy",
        loader_factory=EodPriceLoader,
        http_source=SourceType.BHAVCOPY,
        local_patterns=(
            "sec_bhavdata_full_{ddmmyyyy}.csv",
            "cm{ddmonyyyy}bhav.csv",  # legacy NSE naming
        ),
    ),
    "wk52": SourceSpec(
        name="wk52",
        table="fact_52wk",
        drop_subdir="52wk",
        loader_factory=Wk52Loader,
        http_source=SourceType.WK52,
        local_patterns=("CM_52_wk_High_low_{ddmmyyyy}.csv",),
        supports_bad_records=True,
    ),
    "constituents": SourceSpec(
        name="constituents",
        table="dim_nifty50_constituent",
        drop_subdir="constituents",
        loader_factory=ConstituentsLoader,
        http_source=SourceType.CONSTITUENTS,
        # Constituents file has no date — always the latest snapshot.
        local_patterns=("ind_nifty50list.csv",),
    ),
    "reconstitution": SourceSpec(
        name="reconstitution",
        table="dim_nifty50_constituent",
        drop_subdir="reconstitution",
        loader_factory=ReconstitutionLoader,
        http_source=None,
        local_patterns=("*.csv",),
        local_only=True,
    ),
    "corporate-actions": SourceSpec(
        name="corporate-actions",
        table="fact_corporate_action",
        drop_subdir="corporate_actions",
        loader_factory=CorporateActionsFrameworkLoader,
        http_source=SourceType.CORPORATE_ACTIONS,
        local_patterns=(
            "corporate_actions_{ddmmyyyy}.csv",
            "*{ddmmyyyy}*.csv",
        ),
    ),
    "event-calendar": SourceSpec(
        name="event-calendar",
        table="fact_corporate_event",
        drop_subdir="event_calendar",
        loader_factory=EventCalendarLoader,
        http_source=SourceType.EVENT_CALENDAR,
        local_patterns=(
            "event_calendar_{yyyymmdd}.json",
            "event_calendar_{ddmmyyyy}.json",
        ),
        supports_json_bad_records=True,
    ),
    "announcements": SourceSpec(
        name="announcements",
        table="fact_corporate_event",
        drop_subdir="announcements",
        loader_factory=AnnouncementsLoader,
        http_source=SourceType.ANNOUNCEMENTS,
        local_patterns=(
            "announcements_{yyyymmdd}.json",
            "announcements_{ddmmyyyy}.json",
        ),
        supports_json_bad_records=True,
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
# dim-stock runs first so FK constraints in fact_* tables are satisfied.
# H is excluded because the loader raises NotImplementedError.
ALL_AUTOMATED = ["dim-stock", "bhavcopy", "wk52", "constituents",
                 "corporate-actions", "event-calendar", "announcements"]  # reconstitution, intraday


def _drop_dir(spec: SourceSpec) -> Path:
    """Resolve and create the manual-drop directory for *spec*."""
    path = settings.project_root / "data" / "raw" / spec.drop_subdir
    path.mkdir(parents=True, exist_ok=True)
    return path


def _processed_dir(spec: SourceSpec) -> Path:
    """Resolve and create the processed (post-ingest) directory for *spec*."""
    path = settings.project_root / "data" / "processed" / spec.drop_subdir
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_fetcher(
    spec: SourceSpec,
    local_only: bool = False,
    local_file: Optional[Path] = None,
) -> BaseFetcher:
    """Construct the fetcher for *spec*.

    Args:
        spec: Source wiring spec from :data:`SOURCES`.
        local_only: If True, skip HTTP and use only the local drop folder.
        local_file: If given, ignore directory scanning and use this exact
            file path (overrides both HTTP and the local drop folder).

    Returns:
        A :class:`BaseFetcher` ready for the pipeline.
    """
    if local_file is not None:
        return FixedFileFetcher(local_file)

    drop = _drop_dir(spec)
    patterns = spec.local_patterns or None

    if spec.local_only:
        return LocalFetcher(source_dir=drop, patterns=patterns)

    if local_only:
        return LocalFetcher(source_dir=drop, patterns=patterns)

    assert spec.http_source is not None  # not local_only → http_source set
    return HybridFetcher(
        http=NseHttpFetcher(source=spec.http_source),
        local=LocalFetcher(source_dir=drop, patterns=patterns),
    )


def _build_loader(spec: SourceSpec) -> BaseLoader:
    """Construct the loader, injecting bad-records writers if supported.

    Two writer flavours, picked from the spec:
    - CSV (:class:`BadRecordsWriter`) for parsing-time drops.
    - JSON (:class:`JsonBadRecordsWriter`) for FK-violation drops in the
      corporate-event loaders, where preserving the original NSE record
      shape matters for re-ingestion.
    """
    kwargs: dict[str, Any] = {}
    if spec.supports_bad_records:
        kwargs["bad_records_writer"] = BadRecordsWriter(source=spec.name)
    if spec.supports_json_bad_records:
        kwargs["bad_records_writer"] = JsonBadRecordsWriter(source=spec.name)
    return spec.loader_factory(**kwargs)


def run_one(
    spec: SourceSpec,
    trade_date: date,
    local_only: bool = False,
    local_file: Optional[Path] = None,
) -> int:
    """Build and run the pipeline for one source/date.

    Args:
        spec: Source wiring spec.
        trade_date: NSE trading date to ingest.
        local_only: If True, skip HTTP fetch and read from local drop only.
        local_file: If set, use this exact file (bypasses both HTTP and local
            drop folder lookup).

    Returns:
        Number of rows upserted.
    """
    if spec.not_implemented:
        logger.warning(
            "[%s] is a placeholder (vendor integration pending) — skipping",
            spec.name,
        )
        return 0

    fetcher = build_fetcher(spec, local_only=local_only, local_file=local_file)
    pipeline = Pipeline(
        fetcher=fetcher,
        loader=_build_loader(spec),
        source_name=spec.name,
        table_name=spec.table,
        processed_dir=_processed_dir(spec),
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
        "--local-file",
        type=Path,
        default=None,
        help=(
            "Load this exact file (bypasses HTTP and the data/raw/<source>/ "
            "lookup). Requires --source <one source> and --date. Cannot be "
            "combined with --start/--end or --source all."
        ),
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

    # --local-file constraints
    if args.local_file is not None:
        if args.source == "all":
            parser.error("--local-file cannot be combined with --source all")
        if range_mode:
            parser.error("--local-file cannot be combined with --start/--end")
        if not args.local_file.exists():
            parser.error(f"--local-file path does not exist: {args.local_file}")

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
                rows = run_one(
                    spec, single_date,
                    local_only=args.local_only,
                    local_file=args.local_file,
                )
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
