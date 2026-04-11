"""Corporate actions parser for NSE CA CSV files.

NSE publishes corporate actions in a CSV format with columns:
    Symbol, Company Name, Purpose, Ex-Date, Record Date, BC Start, BC End, ...

This parser normalises that into a clean DataFrame ready for loading
into `fact_corporate_action`.

Usage:
    from ingestion.corporate_actions_parser import CorporateActionsParser
    parser = CorporateActionsParser()
    df = parser.parse("data/corporate_actions_jan2024.csv", as_of=date(2024, 1, 17))
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from ingestion.purpose_parser import parse_purpose, event_significance

logger = logging.getLogger(__name__)

# NSE corporate action CSV columns we care about (case-insensitive match)
_CA_COLUMN_MAP = {
    "symbol":       "symbol",
    "company name": "company_name",
    "purpose":      "purpose",
    "ex-date":      "ex_date",
    "ex date":      "ex_date",
    "record date":  "record_date",
    "bc start date":"bc_start",
    "bc end date":  "bc_end",
}

NSE_DATE_FORMATS = ["%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d"]


class CorporateActionsParseError(Exception):
    pass


class CorporateActionsParser:
    """Parse NSE corporate action CSV files into clean DataFrames."""

    def parse(self, filepath: str | Path, as_of: Optional[date] = None) -> pd.DataFrame:
        """Parse a corporate actions CSV.

        Args:
            filepath: Path to the NSE corporate actions CSV.
            as_of: Reference date for filtering (only load actions with ex_date <= as_of + 30d).
                   If None, load all rows.

        Returns:
            DataFrame with columns: symbol, purpose, event_type, ex_date,
            record_date, significance, amount, ratio_num, ratio_den, raw_purpose.
        """
        path = Path(filepath)
        if not path.exists():
            raise CorporateActionsParseError(f"File not found: {path}")

        try:
            raw = pd.read_csv(path, dtype=str)
        except Exception as e:
            raise CorporateActionsParseError(f"Cannot read CSV: {e}") from e

        raw.columns = raw.columns.str.strip().str.lower()

        # Remap known columns
        col_map = {}
        for col in raw.columns:
            if col in _CA_COLUMN_MAP:
                col_map[col] = _CA_COLUMN_MAP[col]
        raw = raw.rename(columns=col_map)

        if "symbol" not in raw.columns or "purpose" not in raw.columns:
            raise CorporateActionsParseError(
                f"Missing required columns. Found: {list(raw.columns)}"
            )

        # Normalise symbol
        raw["symbol"] = raw["symbol"].str.strip().str.upper()

        # Parse ex_date
        if "ex_date" in raw.columns:
            raw["ex_date"] = raw["ex_date"].apply(self._parse_date)
        else:
            raw["ex_date"] = None

        if "record_date" in raw.columns:
            raw["record_date"] = raw["record_date"].apply(self._parse_date)
        else:
            raw["record_date"] = None

        # Filter to relevant date window
        if as_of is not None:
            cutoff = pd.Timestamp(as_of) + pd.Timedelta(days=30)
            lookback = pd.Timestamp(as_of) - pd.Timedelta(days=365)
            if "ex_date" in raw.columns:
                raw = raw[
                    raw["ex_date"].isna() |
                    ((raw["ex_date"] >= lookback) & (raw["ex_date"] <= cutoff))
                ]

        # Parse purpose strings
        parsed_rows = []
        for _, row in raw.iterrows():
            purpose_str = str(row.get("purpose", "")).strip()
            parsed = parse_purpose(purpose_str)
            sig = event_significance(parsed)
            parsed_rows.append({
                "symbol":       row["symbol"],
                "purpose":      purpose_str,
                "event_type":   parsed.event_type,
                "ex_date":      row.get("ex_date"),
                "record_date":  row.get("record_date"),
                "significance": sig,
                "amount":       parsed.amount,
                "ratio_num":    parsed.ratio_num,
                "ratio_den":    parsed.ratio_den,
                "raw_purpose":  parsed.raw_text,
            })

        df = pd.DataFrame(parsed_rows)
        logger.info("Parsed %d corporate action rows from %s", len(df), path.name)
        return df

    def _parse_date(self, val: str) -> Optional[pd.Timestamp]:
        if not val or str(val).strip() in ("", "nan", "NaN", "-", "N/A"):
            return None
        for fmt in NSE_DATE_FORMATS:
            try:
                return pd.Timestamp(datetime.strptime(str(val).strip(), fmt))
            except ValueError:
                continue
        logger.warning("Could not parse date: %r", val)
        return None
