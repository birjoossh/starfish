"""Bhavcopy CSV parser with header validation and series filter.

Parses NSE bhavcopy CSV files into DataFrames ready for database loading.
Addresses the critical gaps identified in the eng review:
1. CSV header validation (silent empty pipeline if headers change)
2. Series filter (silent wrong data if filter is wrong)

Usage:
    from ingestion.bhavcopy_parser import BhavcopyParser
    parser = BhavcopyParser()
    df = parser.parse("cm15JAN2024bhav.csv")
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from config.thresholds import get_series_filter

logger = logging.getLogger(__name__)

# Expected columns in NSE bhavcopy CSV
# Old format (2023-2024): SYMBOL, SERIES, OPEN, HIGH, LOW, CLOSE, etc.
# New format (2025+): SYMBOL, SERIES, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, CLOSE_PRICE, etc.
EXPECTED_COLUMNS = {
    "SYMBOL", "SERIES", "OPEN", "HIGH", "LOW", "CLOSE",
    "PREVCLOSE", "TOTTRDQTY", "TOTTRDVAL", "TIMESTAMP",
    "TOTALTRADES", "ISIN",
}

# Alternative column names for new format
COLUMN_ALIASES = {
    "OPEN_PRICE": "OPEN",
    "HIGH_PRICE": "HIGH",
    "LOW_PRICE": "LOW",
    "CLOSE_PRICE": "CLOSE",
    "PREV_CLOSE": "PREVCLOSE",
    "TTL_TRD_QNTY": "TOTTRDQTY",
    "TURNOVER_LACS": "TOTTRDVAL",
    "NO_OF_TRADES": "TOTALTRADES",
    "DATE1": "TIMESTAMP",
}

# NSE date format in TIMESTAMP column: DD-MMM-YYYY
NSE_DATE_FORMAT = "%d-%b-%Y"


class BhavcopyParseError(Exception):
    """Raised when bhavcopy CSV cannot be parsed."""
    pass


class BhavcopyParser:
    """Parse NSE bhavcopy CSV files into clean DataFrames.

    Handles:
    - Column header validation (raises clear error if columns changed)
    - Series filter (only EQ/BE/BL/SM/ST rows)
    - Date parsing from TIMESTAMP column
    - Null handling and type conversion
    - prev_close column (directly from CSV, no computation needed)
    """

    def __init__(self, series_filter: list[str] | None = None):
        self.series_filter = set(series_filter or get_series_filter())

    def parse(
        self,
        file_path: str | Path,
        trade_date: date | None = None,
        source_file: str | None = None,
    ) -> pd.DataFrame:
        """Parse a bhavcopy CSV file into a clean DataFrame.

        Args:
            file_path: Path to the CSV file.
            trade_date: Trading date. If None, extracted from TIMESTAMP column.
            source_file: Source filename for audit trail.

        Returns:
            DataFrame with columns matching fact_eod_price schema.

        Raises:
            BhavcopyParseError: If headers are invalid, file is empty, or parsing fails.
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise BhavcopyParseError(f"File not found: {file_path}")

        if source_file is None:
            source_file = file_path.name

        # Read CSV
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            raise BhavcopyParseError(f"Failed to read CSV {file_path}: {e}")

        if df.empty:
            raise BhavcopyParseError(f"CSV is empty: {file_path}")

        # CRITICAL: Validate column headers before parsing
        self._validate_headers(df, file_path)

        # Apply column aliases for new NSE format (2025+) early, before date parsing
        df = self._apply_column_aliases(df)

        # Parse trade date from TIMESTAMP column
        if trade_date is None:
            trade_date = self._parse_trade_date(df, file_path)

        # Strip whitespace from series values (NSE CSVs sometimes have " EQ", " GS", etc.)
        df["SERIES"] = df["SERIES"].astype(str).str.strip()

        # Filter by series
        original_count = len(df)
        df = df[df["SERIES"].isin(self.series_filter)].copy()
        filtered_count = len(df)

        if filtered_count == 0:
            logger.warning(
                f"All {original_count} rows filtered out by series filter "
                f"{self.series_filter} in {file_path}. "
                f"Series found: {df['SERIES'].unique().tolist() if not df.empty else 'none'}"
            )
            raise BhavcopyParseError(
                f"Series filter removed ALL rows from {file_path}. "
                f"Expected series {self.series_filter}. "
                f"Check if NSE changed the SERIES column values."
            )

        if filtered_count < original_count * 0.5:
            logger.warning(
                f"Series filter removed {original_count - filtered_count} of {original_count} rows "
                f"({100 * (1 - filtered_count / original_count):.0f}%) from {file_path}"
            )

        # Map and clean columns
        df = self._map_columns(df, trade_date, source_file)

        logger.info(
            f"Parsed {file_path.name}: {filtered_count} rows "
            f"(filtered from {original_count}), date={trade_date}"
        )

        return df

    def _validate_headers(self, df: pd.DataFrame, file_path: Path) -> None:
        """Validate that expected columns exist in the CSV.

        CRITICAL: This prevents the silent empty pipeline failure identified
        in the eng review. If NSE renames columns, we catch it here.
        Also handles new format (2025+) with column aliases.
        """
        # Strip whitespace first
        df.columns = df.columns.str.strip()

        # Check for columns with aliases applied
        actual_columns = set(df.columns) | set(COLUMN_ALIASES.keys())

        # Check if aliases can help
        available_columns = set(df.columns)
        for new_col in COLUMN_ALIASES:
            if new_col in available_columns:
                actual_columns.add(COLUMN_ALIASES[new_col])

        # ISIN is optional in new format - make it optional
        required_columns = EXPECTED_COLUMNS - {"ISIN"}
        missing = required_columns - actual_columns

        if missing:
            raise BhavcopyParseError(
                f"CSV header validation FAILED for {file_path.name}. "
                f"Missing expected columns: {sorted(missing)}. "
                f"Found columns: {sorted(actual_columns)}. "
                f"NSE may have changed the bhavcopy format."
            )

    def _parse_trade_date(self, df: pd.DataFrame, file_path: Path) -> date:
        """Extract trade date from the TIMESTAMP column."""
        if "TIMESTAMP" not in df.columns:
            raise BhavcopyParseError(f"No TIMESTAMP column in {file_path}")

        date_str = str(df["TIMESTAMP"].iloc[0]).strip()
        try:
            return datetime.strptime(date_str, NSE_DATE_FORMAT).date()
        except ValueError:
            # Try alternate formats
            for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y"):
                try:
                    return datetime.strptime(str(date_str), fmt).date()
                except ValueError:
                    continue
            raise BhavcopyParseError(
                f"Cannot parse date '{date_str}' from TIMESTAMP column in {file_path}"
            )

    def _apply_column_aliases(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply column name aliases for new NSE format (2025+).

        New format uses: OPEN_PRICE, HIGH_PRICE, LOW_PRICE, CLOSE_PRICE, etc.
        Old format uses: OPEN, HIGH, LOW, CLOSE, etc.
        """
        # Clean column names (remove leading/trailing whitespace)
        df.columns = df.columns.str.strip()

        # Build rename mapping for new format columns that exist
        # Only rename if the old format column doesn't exist
        rename_map = {}
        for new_name, old_name in COLUMN_ALIASES.items():
            if new_name in df.columns:
                # Rename new format column to old format
                if old_name not in df.columns:
                    rename_map[new_name] = old_name
                else:
                    # Both exist - drop the new format column (use old)
                    rename_map[new_name] = None  # Mark for removal

        # Apply renames
        cols_to_drop = []
        for old, new in [(v, k) for k, v in rename_map.items() if v is None]:
            cols_to_drop.append(old)

        df = df.drop(columns=[c for c in cols_to_drop if c in df.columns], errors='ignore')

        if rename_map:
            actual_renames = {k: v for k, v in rename_map.items() if v is not None and v is not None}
            if actual_renames:
                logger.debug(f"Renaming columns: {actual_renames}")
                df = df.rename(columns=actual_renames)

        return df

    def _map_columns(
        self, df: pd.DataFrame, trade_date: date, source_file: str
    ) -> pd.DataFrame:
        """Map NSE bhavcopy columns to fact_eod_price schema."""
        # First apply column aliases for new format (2025+)
        df = self._apply_column_aliases(df)

        result = pd.DataFrame({
            "trade_date": trade_date,
            "symbol": df["SYMBOL"].str.strip(),
            "open": pd.to_numeric(df["OPEN"], errors="coerce"),
            "high": pd.to_numeric(df["HIGH"], errors="coerce"),
            "low": pd.to_numeric(df["LOW"], errors="coerce"),
            "close": pd.to_numeric(df["CLOSE"], errors="coerce"),
            "prev_close": pd.to_numeric(df["PREVCLOSE"], errors="coerce"),
            "total_traded_qty": pd.to_numeric(df["TOTTRDQTY"], errors="coerce").astype("Int64"),
            "total_traded_value_lakh": pd.to_numeric(df["TOTTRDVAL"], errors="coerce"),
            "total_trades": pd.to_numeric(df["TOTALTRADES"], errors="coerce").astype("Int64"),
            "series": df["SERIES"].str.strip(),
            "delivery_qty": pd.NA,
            "delivery_pct": pd.NA,
            "source_file": source_file,
        })

        # Drop rows where critical columns are null
        critical_cols = ["symbol", "open", "high", "low", "close", "prev_close"]
        before = len(result)
        result = result.dropna(subset=critical_cols)
        dropped = before - len(result)
        if dropped > 0:
            logger.warning(f"Dropped {dropped} rows with null critical columns")

        # Drop rows where price is zero (likely bad data)
        result = result[result["close"] > 0]

        return result.reset_index(drop=True)
