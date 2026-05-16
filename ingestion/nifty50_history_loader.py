"""Seed loader for ``nifty50_history.csv`` → ``dim_nifty50_constituent``.

Validates the CSV and bulk-inserts historical reconstitution rows.
Used by the backfill orchestrator to seed point-in-time membership data
before loading fact tables.

Usage:
    python -m ingestion.nifty50_history_loader
    python -m ingestion.nifty50_history_loader --csv data/raw/reconstitution/nifty50_history.csv
"""

from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from config.database import get_engine

logger = logging.getLogger(__name__)

_REQUIRED_COLS = ["symbol", "effective_from", "action"]
_VALID_ACTIONS = {"ADD", "DELETE"}


class HistoryCSVValidationError(Exception):
    """Raised when nifty50_history.csv fails validation."""


def validate_history_csv(path: Path) -> pd.DataFrame:
    """Validate nifty50_history.csv structure and return the parsed DataFrame.

    Checks:
        1. File exists and is readable
        2. Required columns present
        3. No empty symbols
        4. All effective_from dates parseable
        5. All actions are ADD or DELETE
        6. All symbols are uppercase, no whitespace
        7. No duplicate (symbol, effective_from) pairs
        8. No overlapping intervals per symbol

    Args:
        path: Path to the CSV file.

    Returns:
        Parsed and validated DataFrame.

    Raises:
        HistoryCSVValidationError: On any validation failure.
    """
    if not path.exists():
        raise HistoryCSVValidationError(f"File not found: {path}")

    try:
        df = pd.read_csv(path, dtype=str)
    except Exception as exc:
        raise HistoryCSVValidationError(f"Cannot read {path}: {exc}") from exc

    df.columns = df.columns.str.strip().str.lower()

    # Required columns
    missing = set(_REQUIRED_COLS) - set(df.columns)
    if missing:
        raise HistoryCSVValidationError(
            f"Missing required columns: {sorted(missing)}. Found: {sorted(df.columns)}"
        )

    # No empty symbols
    df["symbol"] = df["symbol"].str.strip().str.upper()
    empty_syms = df[df["symbol"].isna() | (df["symbol"] == "")]
    if not empty_syms.empty:
        raise HistoryCSVValidationError(f"Found {len(empty_syms)} row(s) with empty symbol")

    # Valid actions
    df["action"] = df["action"].str.strip().str.upper()
    invalid_actions = set(df["action"].unique()) - _VALID_ACTIONS
    if invalid_actions:
        raise HistoryCSVValidationError(
            f"Invalid action values: {invalid_actions}. Must be ADD or DELETE."
        )

    # Parseable dates
    try:
        df["effective_from"] = pd.to_datetime(df["effective_from"]).dt.date
    except Exception as exc:
        raise HistoryCSVValidationError(
            f"Unparseable effective_from date(s): {exc}"
        ) from exc

    if "effective_to" in df.columns:
        # Replace empty/whitespace/NULL with pd.NA, then convert to nullable date.
        # Arrow-backed string dtype rejects setting date objects directly — convert
        # to object first.
        df["effective_to"] = df["effective_to"].astype(object)
        df["effective_to"] = df["effective_to"].replace(
            {"": pd.NA, " ": pd.NA, "NULL": pd.NA, "None": pd.NA}
        )
        try:
            notna_mask = df["effective_to"].notna()
            if notna_mask.any():
                df.loc[notna_mask, "effective_to"] = pd.to_datetime(
                    df.loc[notna_mask, "effective_to"]
                ).dt.date
        except Exception as exc:
            raise HistoryCSVValidationError(
                f"Unparseable effective_to date(s): {exc}"
            ) from exc
    else:
        df["effective_to"] = None

    # No duplicate (symbol, effective_from)
    dups = df[df.duplicated(subset=["symbol", "effective_from"], keep=False)]
    if not dups.empty:
        dup_pairs = sorted(
            set(zip(dups["symbol"], dups["effective_from"].astype(str)))
        )
        raise HistoryCSVValidationError(
            f"Duplicate (symbol, effective_from) pairs: {dup_pairs[:20]}"
        )

    # No overlapping intervals per symbol
    df_sorted = df.sort_values(["symbol", "effective_from"]).reset_index(drop=True)
    for sym, grp in df_sorted.groupby("symbol"):
        grp = grp.reset_index(drop=True)
        for i in range(len(grp) - 1):
            curr_to = grp.iloc[i]["effective_to"]
            next_from = grp.iloc[i + 1]["effective_from"]
            if curr_to is not None and pd.notna(curr_to) and curr_to > next_from:
                raise HistoryCSVValidationError(
                    f"Overlapping interval for {sym}: row {i} effective_to={curr_to} "
                    f"overlaps row {i+1} effective_from={next_from}"
                )
            if curr_to is None or pd.isna(curr_to):
                if grp.iloc[i]["action"] == "ADD" and grp.iloc[i + 1]["action"] == "ADD":
                    raise HistoryCSVValidationError(
                        f"Symbol {sym} has two open-ended ADD rows "
                        f"(effective_from={grp.iloc[i]['effective_from']} and "
                        f"{grp.iloc[i+1]['effective_from']}). "
                        f"Add an effective_to on the first row or a DELETE row before the second ADD."
                    )

    logger.info(
        "History CSV validation passed: %d rows, %d symbols, %d ADD, %d DELETE",
        len(df),
        df["symbol"].nunique(),
        (df["action"] == "ADD").sum(),
        (df["action"] == "DELETE").sum(),
    )
    return df


def load_history_csv(path: Path) -> int:
    """Validate and bulk-load nifty50_history.csv into dim_nifty50_constituent.

    Args:
        path: Path to nifty50_history.csv.

    Returns:
        Number of rows inserted.
    """
    df = validate_history_csv(path)

    engine = get_engine()

    # Verify symbols exist in dim_stock
    with engine.connect() as conn:
        valid = set(
            row[0] for row in conn.execute(text("SELECT symbol FROM dim_stock"))
        )
    unknown = set(df["symbol"].unique()) - valid
    if unknown:
        logger.warning(
            "History loader: %d symbol(s) not in dim_stock — will be skipped: %s",
            len(unknown), sorted(unknown)[:15],
        )

    rows_written = 0
    insert_sql = text("""
        INSERT INTO dim_nifty50_constituent
            (symbol, effective_from, effective_to, index_weight_pct,
             replaced_symbol, change_type, review_period)
        VALUES
            (:symbol, :effective_from, :effective_to, NULL, NULL, :change_type, :review_period)
        ON CONFLICT (symbol, effective_from) DO UPDATE SET
            effective_to = EXCLUDED.effective_to,
            change_type = EXCLUDED.change_type,
            review_period = EXCLUDED.review_period
    """)

    with engine.begin() as conn:
        for _, row in df.iterrows():
            sym = row["symbol"]
            if sym not in valid:
                continue
            change_type = "Addition" if row["action"] == "ADD" else "Deletion"
            review = row.get("review_period", "Auto")
            if pd.isna(review) or not review:
                review = "Auto"
            params = {
                "symbol": sym,
                "effective_from": row["effective_from"],
                "effective_to": row["effective_to"] if pd.notna(row["effective_to"]) else None,
                "change_type": change_type,
                "review_period": str(review),
            }
            conn.execute(insert_sql, params)
            rows_written += 1

    logger.info("History loader: %d rows written to dim_nifty50_constituent", rows_written)
    return rows_written


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Load nifty50_history.csv into dim_nifty50_constituent")
    parser.add_argument(
        "--csv",
        type=str,
        default="data/raw/reconstitution/nifty50_history.csv",
        help="Path to nifty50_history.csv",
    )
    parser.add_argument("--validate-only", action="store_true", help="Only validate, do not load")
    args = parser.parse_args()

    path = Path(args.csv)
    if args.validate_only:
        validate_history_csv(path)
        print("Validation passed.")
    else:
        count = load_history_csv(path)
        print(f"Loaded {count} rows into dim_nifty50_constituent.")


if __name__ == "__main__":
    main()
