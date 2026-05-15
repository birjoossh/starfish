"""Corporate events loader — upsert classified events into ``fact_corporate_event``.

Consumes a DataFrame produced by :class:`CorporateEventsIngestor` (spec
taxonomy: Earnings / Leadership_Change / M&A / Large_Order / Pledging_Change
/ Rating_Change / Regulatory / Other) and upserts it with the unique
``(symbol, event_date, event_type)`` deduplication key.

Usage::

    from ingestion.corporate_events_loader import CorporateEventsLoader
    rows = CorporateEventsLoader().load(df)

    # CLI:
    python -m ingestion.corporate_events_loader \
        --file data/announcements_jan2024.csv --date 2024-01-17
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


# Mirrors fact_corporate_event.event_type CHECK constraint.
VALID_EVENT_TYPES = {
    "Earnings", "Leadership_Change", "M&A", "Large_Order",
    "Pledging_Change", "Rating_Change", "Regulatory", "Other",
}


class CorporateEventsLoader:
    """Upsert classified corporate events into ``fact_corporate_event``."""

    def load(self, df: pd.DataFrame) -> int:
        """Upsert events. Rows with NULL event_date are skipped.

        Returns:
            Number of rows upserted.
        """
        if df.empty:
            logger.info("No corporate events to load.")
            return 0

        engine = get_engine()
        rows_upserted = 0

        upsert_sql = text("""
            INSERT INTO fact_corporate_event (
                symbol, event_date, event_type, significance_score,
                event_summary, raw_announcement_text, categorization_method,
                follow_up_required
            ) VALUES (
                :symbol, :event_date, :event_type, :significance,
                :event_summary, :raw_text, :method, :follow_up
            )
            ON CONFLICT (symbol, event_date, event_type) DO UPDATE SET
                significance_score    = EXCLUDED.significance_score,
                event_summary         = EXCLUDED.event_summary,
                raw_announcement_text = EXCLUDED.raw_announcement_text,
                categorization_method = EXCLUDED.categorization_method,
                follow_up_required    = EXCLUDED.follow_up_required
        """)

        with engine.begin() as conn:
            for _, row in df.iterrows():
                if pd.isna(row.get("event_date")) or row.get("event_date") is None:
                    logger.debug(
                        "Skipping event with null date: %s / %s",
                        row.get("symbol"), row.get("event_type"),
                    )
                    continue

                event_date = row["event_date"]
                if hasattr(event_date, "date"):
                    event_date = event_date.date()

                event_type = row.get("event_type", "Other")
                if event_type not in VALID_EVENT_TYPES:
                    logger.warning(
                        "Unknown event_type %r from classifier — coercing to Other",
                        event_type,
                    )
                    event_type = "Other"

                significance = int(row.get("significance_score") or 1)
                significance = max(1, min(5, significance))

                conn.execute(upsert_sql, {
                    "symbol":        row["symbol"],
                    "event_date":    event_date,
                    "event_type":    event_type,
                    "significance":  significance,
                    "event_summary": str(row.get("event_summary", ""))[:500],
                    "raw_text":      str(row.get("raw_announcement_text", ""))[:2000],
                    "method":        row.get("categorization_method", "Rule"),
                    "follow_up":     bool(row.get("is_negative", False)),
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
