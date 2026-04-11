"""Corporate events ingestor: classify NSE announcements into typed events.

Reads NSE bulk announcement data (CSV format) and classifies each row using
keyword matching into a structured event with a significance score.

This feeds fact_corporate_event, which then powers:
    - ISS Factor 5 (event proximity bonus)
    - EVT signal category classification
    - View 6: Corporate Events Tracker

Usage:
    from ingestion.corporate_events_ingestor import CorporateEventsIngestor
    ingestor = CorporateEventsIngestor()
    df = ingestor.ingest("data/announcements_jan2024.csv", calc_date=date(2024, 1, 17))
"""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

from ingestion.purpose_parser import (
    parse_purpose, event_significance,
    EVENT_DIVIDEND, EVENT_BONUS, EVENT_SPLIT, EVENT_RIGHTS,
    EVENT_BUYBACK, EVENT_AGM, EVENT_EGM, EVENT_RESULTS, EVENT_OTHER,
)

logger = logging.getLogger(__name__)

NSE_DATE_FORMATS = ["%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d"]


class CorporateEventsIngestor:
    """Classify NSE announcements feed into structured corporate events."""

    def ingest(
        self,
        filepath: str | Path,
        calc_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """Read an announcements CSV and produce a classified events DataFrame.

        Resulting DataFrame columns:
            symbol, event_date, event_type, significance, estimated_significance,
            is_upcoming, description, source_file

        Args:
            filepath: Path to the announcements CSV.
            calc_date: The pipeline calc date — used to flag upcoming events.
        """
        path = Path(filepath)
        if not path.exists():
            logger.warning("Announcements file not found: %s — skipping", path)
            return pd.DataFrame()

        raw = pd.read_csv(path, dtype=str)
        raw.columns = raw.columns.str.strip().str.lower()

        # Flexible column detection
        symbol_col   = self._detect_col(raw, ["symbol", "scrip", "ticker"])
        date_col     = self._detect_col(raw, ["date", "event date", "ex-date", "ex date", "announcement date"])
        purpose_col  = self._detect_col(raw, ["purpose", "description", "announcement", "subject", "details"])

        if not symbol_col or not purpose_col:
            logger.error("Cannot find symbol/purpose columns in %s. Columns: %s", path.name, list(raw.columns))
            return pd.DataFrame()

        rows = []
        for _, row in raw.iterrows():
            symbol = str(row.get(symbol_col, "")).strip().upper()
            if not symbol or symbol == "NAN":
                continue

            purpose_str = str(row.get(purpose_col, "")).strip()
            event_date_raw = str(row.get(date_col, "")).strip() if date_col else ""
            event_date = self._parse_date(event_date_raw)

            parsed = parse_purpose(purpose_str)
            sig = event_significance(parsed)

            is_upcoming = False
            if calc_date and event_date:
                is_upcoming = event_date.date() > calc_date if hasattr(event_date, "date") else event_date > calc_date

            rows.append({
                "symbol":               symbol,
                "event_date":           event_date,
                "event_type":           parsed.event_type,
                "significance":         sig,
                "estimated_significance": sig if is_upcoming else None,
                "is_upcoming":          is_upcoming,
                "description":          purpose_str[:500],  # truncate
                "source_file":          path.name,
            })

        df = pd.DataFrame(rows)
        logger.info("Classified %d events from %s", len(df), path.name)
        return df

    def _detect_col(self, df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
        for c in candidates:
            if c in df.columns:
                return c
        return None

    def _parse_date(self, val: str) -> Optional[pd.Timestamp]:
        import datetime as dt
        if not val or val in ("", "nan", "NaN", "-", "N/A"):
            return None
        for fmt in NSE_DATE_FORMATS:
            try:
                return pd.Timestamp(dt.datetime.strptime(val, fmt))
            except ValueError:
                continue
        return None
