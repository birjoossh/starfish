"""Corporate events loader: upsert classified events into fact_corporate_event.

Usage:
    from ingestion.corporate_events_loader import CorporateEventsLoader
    loader = CorporateEventsLoader()
    loader.load(df)

    # CLI:
    python -m ingestion.corporate_events_loader --file data/announcements_jan2024.csv --date 2024-01-17
"""

from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from config.database import get_engine
from ingestion.corporate_events_ingestor import CorporateEventsIngestor

logger = logging.getLogger(__name__)


class CorporateEventsLoader:
    """Upsert corporate events into fact_corporate_event."""

    # DB check constraint: Earnings | Leadership_Change | M&A | Large_Order |
    #                       Pledging_Change | Rating_Change | Regulatory | Other
    EVENT_TYPE_MAP = {
        "DIVIDEND":  "Earnings",   # Dividend announcements → Earnings context
        "RESULTS":   "Earnings",   # Quarterly results → Earnings
        "BONUS":     "Other",
        "SPLIT":     "Other",
        "RIGHTS":    "Other",
        "BUYBACK":   "Other",
        "AGM":       "Regulatory",
        "EGM":       "Regulatory",
        "OTHER":     "Other",
    }

    # DB constraint: Manual | Rule | NLP
    CATEGORIZATION_METHOD = "Rule"

    def load(self, df: pd.DataFrame) -> int:
        """Upsert a classified events DataFrame.

        Returns:
            Number of rows upserted.
        """
        if df.empty:
            logger.info("No corporate events to load.")
            return 0

        engine = get_engine()
        rows_upserted = 0

        upsert_sql = text("""
            INSERT INTO fact_corporate_event
                (symbol, event_date, event_type, significance_score,
                 event_summary, raw_announcement_text, categorization_method)
            VALUES
                (:symbol, :event_date, :event_type, :significance,
                 :event_summary, :raw_text, :method)
            ON CONFLICT (symbol, event_date, event_type) DO UPDATE SET
                significance_score     = EXCLUDED.significance_score,
                event_summary          = EXCLUDED.event_summary,
                raw_announcement_text    = EXCLUDED.raw_announcement_text,
                categorization_method    = EXCLUDED.categorization_method
        """)

        with engine.begin() as conn:
            for _, row in df.iterrows():
                if pd.isna(row.get("event_date")) or row.get("event_date") is None:
                    logger.debug("Skipping event with null date: %s / %s", row["symbol"], row.get("event_type"))
                    continue

                event_date = row["event_date"]
                if hasattr(event_date, "date"):
                    event_date = event_date.date()

                conn.execute(upsert_sql, {
                    "symbol":        row["symbol"],
                    "event_date":    event_date,
                    "event_type":    self.EVENT_TYPE_MAP.get(row["event_type"], "Other"),
                    "significance":  min(5, max(1, int(row["significance"]))),
                    "event_summary": str(row.get("description", ""))[:500],
                    "raw_text":      str(row.get("description", ""))[:2000],
                    "method":        self.CATEGORIZATION_METHOD,
                })
                rows_upserted += 1

        logger.info("Upserted %d corporate event rows", rows_upserted)
        return rows_upserted


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Load NSE corporate events CSV")
    parser.add_argument("--file", required=True, help="Path to announcements CSV")
    parser.add_argument("--date", help="Calc date (YYYY-MM-DD)", default=None)
    args = parser.parse_args()

    calc_date = date.fromisoformat(args.date) if args.date else None
    ingestor = CorporateEventsIngestor()
    df = ingestor.ingest(args.file, calc_date=calc_date)

    loader = CorporateEventsLoader()
    n = loader.load(df)
    print(f"Loaded {n} corporate event rows.")


if __name__ == "__main__":
    main()
