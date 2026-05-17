"""Backfill validation report generator.

Usage:
    python -m ingestion.backfill.validator
    python -m ingestion.backfill.validator --year 2024
"""

from __future__ import annotations

import argparse
import logging
from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import text

from config.database import get_engine

logger = logging.getLogger(__name__)


def _query_df(engine, query: str, **params) -> pd.DataFrame:
    return pd.read_sql_query(text(query), engine, params=params)


def validate_year(engine, year: int) -> dict[str, Any]:
    """Validate backfill completeness for a single calendar year.

    Returns a dict with row counts, trading-day gaps, and quality flags.
    """
    start = date(year, 1, 1)
    end = date(year, 12, 31)

    result: dict[str, Any] = {"year": year, "start": str(start), "end": str(end)}

    # Row counts per table
    tables = [
        "fact_eod_price",
        "fact_52wk",
        "mart_stock_signals",
        "mart_volume_anomaly",
        "nifty50_index_prices",
        "fact_corporate_action",
        "fact_corporate_event",
    ]
    counts = {}
    for table in tables:
        try:
            row = _query_df(
                engine,
                f"SELECT COUNT(*) as cnt FROM {table} "
                "WHERE trade_date >= :start AND trade_date <= :end",
                start=start, end=end,
            )
            counts[table] = int(row["cnt"].iloc[0]) if not row.empty else 0
        except Exception:
            counts[table] = None  # table may not exist
    result["row_counts"] = counts

    # Symbol coverage in fact_eod_price per month
    try:
        monthly = _query_df(
            engine,
            """
            SELECT DATE_TRUNC('month', trade_date)::DATE AS month,
                   COUNT(DISTINCT symbol) AS symbol_count
            FROM fact_eod_price
            WHERE trade_date >= :start AND trade_date <= :end
            GROUP BY 1
            ORDER BY 1
            """,
            start=start, end=end,
        )
        result["monthly_symbol_coverage"] = (
            monthly.to_dict("records") if not monthly.empty else []
        )
    except Exception as exc:
        result["monthly_symbol_coverage"] = f"error: {exc}"

    # Gap detection — count weekdays with no fact_eod_price rows
    try:
        all_dates = pd.date_range(start, end, freq="B")  # business days
        existing_dates = _query_df(
            engine,
            "SELECT DISTINCT trade_date FROM fact_eod_price "
            "WHERE trade_date >= :start AND trade_date <= :end "
            "ORDER BY trade_date",
            start=start, end=end,
        )
        if not existing_dates.empty:
            existing_set = set(pd.Timestamp(d).date() for d in existing_dates["trade_date"])
        else:
            existing_set = set()
        missing = [d.date() for d in all_dates if d.date() not in existing_set]
        result["missing_trading_days"] = missing[:30]  # cap at 30
        result["gap_count"] = len(missing)
    except Exception as exc:
        result["missing_trading_days"] = f"error: {exc}"
        result["gap_count"] = None

    # Cross-check fact_52wk vs fact_eod_price: pct_from_high should be 0 for the date
    # that set the 52w high. We do a light check: count rows where
    # pct_from_high < 0 or > 1.
    try:
        bad_52wk = _query_df(
            engine,
            """
            SELECT COUNT(*) as cnt
            FROM fact_52wk
            WHERE trade_date >= :start AND trade_date <= :end
              AND (pct_from_high < -5 OR pct_from_high > 105)
            """,
            start=start, end=end,
        )
        result["bad_pct_from_high_count"] = int(bad_52wk["cnt"].iloc[0]) if not bad_52wk.empty else 0
    except Exception:
        result["bad_pct_from_high_count"] = None

    # Duplicate check
    try:
        dups = _query_df(
            engine,
            """
            SELECT COUNT(*) as cnt FROM (
                SELECT trade_date, symbol, COUNT(*) as n
                FROM fact_eod_price
                WHERE trade_date >= :start AND trade_date <= :end
                GROUP BY trade_date, symbol
                HAVING COUNT(*) > 1
            ) sub
            """,
            start=start, end=end,
        )
        result["duplicate_keys_fact_eod"] = int(dups["cnt"].iloc[0]) if not dups.empty else 0
    except Exception:
        result["duplicate_keys_fact_eod"] = None

    # Flags
    flags = []
    if counts.get("fact_eod_price", 0) == 0:
        flags.append("ZERO_EOD_PRICES")
    if result.get("gap_count", 0) and result["gap_count"] > 10:
        flags.append(f"HIGH_GAP_COUNT_{result['gap_count']}")
    if result.get("duplicate_keys_fact_eod", 0):
        flags.append("DUPLICATE_KEYS")
    if counts.get("mart_stock_signals", 0) == 0 and counts.get("fact_eod_price", 0) > 0:
        flags.append("SIGNALS_NOT_COMPUTED")
    if counts.get("nifty50_index_prices", 0) == 0:
        flags.append("NO_INDEX_PRICES")
    result["flags"] = flags

    return result


def generate_report(years: list[int] | None = None) -> list[dict[str, Any]]:
    """Generate a full backfill validation report.

    Args:
        years: List of calendar years to validate. Defaults to 2021–current.

    Returns:
        List of per-year validation dicts.
    """
    engine = get_engine()
    if years is None:
        current_year = date.today().year
        years = list(range(2021, current_year + 1))

    results = []
    for year in years:
        logger.info(f"Validating {year}...")
        result = validate_year(engine, year)
        results.append(result)

        # Print summary
        counts = result["row_counts"]
        flags = result["flags"]
        gap_count = result.get("gap_count", "?")
        status = "OK" if not flags else f"FLAGGED: {','.join(flags)}"
        logger.info(
            f"  {year}: eod={counts.get('fact_eod_price','?')} "
            f"signals={counts.get('mart_stock_signals','?')} "
            f"52wk={counts.get('fact_52wk','?')} "
            f"index={counts.get('nifty50_index_prices','?')} "
            f"gaps={gap_count} → {status}"
        )

    return results


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Backfill validation report")
    parser.add_argument("--year", type=int, help="Validate a single year")
    parser.add_argument("--all", action="store_true", help="Validate all years 2021–present")
    args = parser.parse_args()

    if args.year:
        engine = get_engine()
        result = validate_year(engine, args.year)
        import json
        print(json.dumps(result, indent=2, default=str))
    else:
        years = None if args.all else [date.today().year]
        results = generate_report(years)

        all_flags = []
        for r in results:
            all_flags.extend(r.get("flags", []))
        if all_flags:
            print(f"\n⚠ {len(all_flags)} flag(s) across {len(results)} years:")
            for r in results:
                if r["flags"]:
                    print(f"  {r['year']}: {', '.join(r['flags'])}")
        else:
            print(f"\n✓ All {len(results)} year(s) validated with no flags.")


if __name__ == "__main__":
    main()
