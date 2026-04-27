"""Corporate actions loader: upsert parsed rows into fact_corporate_action.

Usage:
    from ingestion.corporate_actions_loader import CorporateActionsLoader
    loader = CorporateActionsLoader()
    loader.load(df)

    # Or run as a CLI:
    python -m ingestion.corporate_actions_loader --file data/ca_jan2024.csv --date 2024-01-17
"""

from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from config.database import get_engine
from ingestion.corporate_actions_parser import CorporateActionsParser

logger = logging.getLogger(__name__)


class CorporateActionsLoader:
    """Upsert corporate actions into fact_corporate_action."""

    # DB check constraint expects title-case values
    ACTION_TYPE_MAP = {
        "DIVIDEND": "Dividend",
        "BONUS":    "Bonus",
        "SPLIT":    "Split",
        "RIGHTS":   "Rights",
        "BUYBACK":  "Buyback",
        "RESULTS":  "Dividend",   # map to closest — these go into fact_corporate_event, not here
        "AGM":      "Dividend",   # fallback; CA table is only for structural actions
        "EGM":      "Dividend",
        "OTHER":    "Dividend",
    }

    def load(self, df: pd.DataFrame) -> int:
        """Upsert a parsed corporate actions DataFrame.

        Returns:
            Number of rows upserted.
        """
        if df.empty:
            logger.info("No corporate actions to load.")
            return 0

        engine = get_engine()

        # Fetch allowed symbols from dim_stock to prevent FK violations
        with engine.connect() as conn:
            valid_symbols = set(row[0] for row in conn.execute(text("SELECT symbol FROM dim_stock")))

        original_count = len(df)
        df = df[df["symbol"].isin(valid_symbols)].copy()
        logger.info(
            "Filtered corporate actions to %d rows matching dim_stock (from %d total)",
            len(df), original_count
        )

        if df.empty:
            logger.warning("No corporate actions remaining after dim_stock filter. Nothing to load.")
            return 0

        rows_upserted = 0

        upsert_sql = text("""
            INSERT INTO fact_corporate_action
                (symbol, action_type, ex_date, record_date,
                 purpose_text, dividend_amount_per_share,
                 ratio_numerator, ratio_denominator, data_source)
            VALUES
                (:symbol, :action_type, :ex_date, :record_date,
                 :purpose_text, :dividend_amount,
                 :ratio_num, :ratio_den, :data_source)
            ON CONFLICT (symbol, ex_date, action_type)
            DO UPDATE SET
                purpose_text              = EXCLUDED.purpose_text,
                dividend_amount_per_share = EXCLUDED.dividend_amount_per_share,
                ratio_numerator           = EXCLUDED.ratio_numerator,
                ratio_denominator         = EXCLUDED.ratio_denominator
        """)

        with engine.begin() as conn:
            for _, row in df.iterrows():
                if pd.isna(row.get("ex_date")):
                    logger.debug("Skipping row with null ex_date: %s / %s", row["symbol"], row["purpose"])
                    continue
                conn.execute(upsert_sql, {
                    "symbol":          row["symbol"],
                    "action_type":     self.ACTION_TYPE_MAP.get(row["event_type"], "Dividend"),
                    "ex_date":         row["ex_date"].date() if hasattr(row["ex_date"], "date") else row["ex_date"],
                    "record_date":     row["record_date"].date() if pd.notna(row.get("record_date")) and hasattr(row.get("record_date"), "date") else None,
                    "purpose_text":    row.get("raw_purpose", "")[:500],
                    "dividend_amount": float(row["amount"]) if pd.notna(row.get("amount")) else None,
                    "ratio_num":       int(row["ratio_num"]) if pd.notna(row.get("ratio_num")) else None,
                    "ratio_den":       int(row["ratio_den"]) if pd.notna(row.get("ratio_den")) else None,
                    "data_source":     "fixture",
                })
                rows_upserted += 1

        logger.info("Upserted %d corporate action rows", rows_upserted)
        return rows_upserted


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Load NSE corporate actions CSV")
    parser.add_argument("--file", required=True, help="Path to corporate actions CSV")
    parser.add_argument("--date", help="As-of date (YYYY-MM-DD) for filtering", default=None)
    args = parser.parse_args()

    as_of = date.fromisoformat(args.date) if args.date else None
    ca_parser = CorporateActionsParser()
    df = ca_parser.parse(args.file, as_of=as_of)

    loader = CorporateActionsLoader()
    n = loader.load(df)
    print(f"Loaded {n} corporate action rows.")


if __name__ == "__main__":
    main()
