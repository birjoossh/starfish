"""Corporate events ingestor — classify NSE announcements into typed events.

Reads an NSE announcements CSV and classifies each row using
:mod:`ingestion.event_classifier` into the spec's qualitative event taxonomy
(Earnings / Leadership_Change / M&A / Large_Order / Pledging_Change /
Rating_Change / Regulatory / Other) with a 1–5 significance score and a
negative-event flag.

Feeds ``fact_corporate_event``, which then powers:

* ISS Factor 5 (event proximity)
* EVT signal category classification
* View 6 — Corporate Events Tracker

Usage::

    from ingestion.corporate_events_ingestor import CorporateEventsIngestor
    df = CorporateEventsIngestor().ingest(
        "data/announcements_jan2024.csv", calc_date=date(2024, 1, 17),
    )

NSE announcement files are inconsistent in column naming; this module
auto-detects ``symbol``, ``event_date``, ``subject``, and ``description``
columns from common variants.
"""

from __future__ import annotations

import datetime as dt
import logging
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

from ingestion.event_classifier import classify_event

logger = logging.getLogger(__name__)

NSE_DATE_FORMATS = ["%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d %b %Y"]


SYMBOL_COL_CANDIDATES  = ["symbol", "scrip", "ticker"]
DATE_COL_CANDIDATES    = [
    "broadcast date", "announcement date", "event date", "submission date",
    "date", "ex-date", "ex date",
]
SUBJECT_COL_CANDIDATES = ["subject", "subject of announcement", "category"]
BODY_COL_CANDIDATES    = [
    "description", "details", "announcement", "purpose", "body_text",
    "body", "remarks",
]


class CorporateEventsIngestor:
    """Classify NSE announcements into structured ``fact_corporate_event`` rows."""

    def ingest(
        self,
        filepath: str | Path,
        calc_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """Read an announcements CSV and produce a classified events DataFrame.

        Resulting DataFrame columns:

            ``symbol`` — uppercased trading symbol.
            ``event_date`` — :class:`pandas.Timestamp` (may be NaT).
            ``event_type`` — one of the spec enum values.
            ``significance_score`` — 1–5.
            ``event_summary`` — first 500 chars of subject/body.
            ``raw_announcement_text`` — concatenation (≤ 2000 chars).
            ``categorization_method`` — always ``"Rule"``.
            ``is_negative`` — bool, per spec §M3.4.
            ``is_upcoming`` — bool, True if event_date is after ``calc_date``.
            ``source_file`` — filename.
        """
        path = Path(filepath)
        if not path.exists():
            logger.warning("Announcements file not found: %s — skipping", path)
            return pd.DataFrame()

        raw = pd.read_csv(path, dtype=str)
        raw.columns = raw.columns.str.strip().str.lower()

        symbol_col  = self._detect_col(raw, SYMBOL_COL_CANDIDATES)
        date_col    = self._detect_col(raw, DATE_COL_CANDIDATES)
        subject_col = self._detect_col(raw, SUBJECT_COL_CANDIDATES)
        body_col    = self._detect_col(raw, BODY_COL_CANDIDATES)

        if not symbol_col or (subject_col is None and body_col is None):
            logger.error(
                "Cannot find symbol + (subject|body) columns in %s. Columns: %s",
                path.name, list(raw.columns),
            )
            return pd.DataFrame()

        rows: list[dict] = []
        unmapped: list[str] = []
        for _, row in raw.iterrows():
            symbol = str(row.get(symbol_col, "")).strip().upper()
            if not symbol or symbol == "NAN":
                continue

            subject = str(row.get(subject_col, "")).strip() if subject_col else ""
            body    = str(row.get(body_col, "")).strip() if body_col else ""
            text    = f"{subject} {body}".strip()
            if not text:
                continue

            classified = classify_event(text)
            if classified.event_type == "Other":
                unmapped.append(text[:120])

            event_date = self._parse_date(str(row.get(date_col, "")).strip()) if date_col else None
            is_upcoming = False
            if calc_date and event_date is not None:
                event_d = event_date.date() if hasattr(event_date, "date") else event_date
                is_upcoming = event_d > calc_date

            rows.append({
                "symbol":                  symbol,
                "event_date":              event_date,
                "event_type":              classified.event_type,
                "significance_score":      classified.significance,
                "event_summary":           text[:500],
                "raw_announcement_text":   text[:2000],
                "categorization_method":   "Rule",
                "is_negative":             classified.is_negative,
                "is_upcoming":             is_upcoming,
                "source_file":             path.name,
            })

        if unmapped:
            logger.info(
                "Classified %d announcements; %d landed in 'Other' (sample: %s)",
                len(rows), len(unmapped), unmapped[:3],
            )
        else:
            logger.info("Classified %d announcements from %s", len(rows), path.name)
        return pd.DataFrame(rows)

    def _detect_col(self, df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
        for c in candidates:
            if c in df.columns:
                return c
        return None

    def _parse_date(self, val: str) -> Optional[pd.Timestamp]:
        if not val or val in ("", "nan", "NaN", "-", "N/A"):
            return None
        for fmt in NSE_DATE_FORMATS:
            try:
                return pd.Timestamp(dt.datetime.strptime(val, fmt))
            except ValueError:
                continue
        return None
