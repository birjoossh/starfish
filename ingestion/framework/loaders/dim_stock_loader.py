"""NSE security master loader → ``dim_stock``.

Parses the daily NSE security master file
(``NSE_CM_security_DDMMYYYY.csv`` — published as ``.csv.gz``,
decompressed by :class:`NseHttpFetcher`) and upserts equity rows into
``dim_stock``.

Source columns of interest (NSE-FIX-style headers):
    - ``TckrSymb``     → ``dim_stock.symbol``
    - ``SctySrs``      → filter to ``EQ`` only (one row per equity)
    - ``FinInstrmNm``  → ``dim_stock.company_name``
    - ``ISIN``         → ``dim_stock.isin``
    - ``ParVal``       → ``dim_stock.face_value``
    - ``ListgDt``      → ``dim_stock.listing_date`` (Unix timestamp, seconds)

The NSE security file does **not** carry sector/industry data.
Behaviour:

- For NEW symbols: insert with ``sector = 'Unknown'``, ``industry = NULL``,
  ``nifty50_member = FALSE`` (overridden later by ConstituentsLoader for
  Nifty 50 members).
- For EXISTING symbols: update only the fields the file authoritatively
  provides (company_name, isin, face_value, listing_date, last_updated).
  Sector / industry / nifty50_member are preserved — those are owned by
  ``seed_stocks.py`` and ``ConstituentsLoader``.

Target table: ``dim_stock``
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import text

from config.database import get_engine
from ingestion.framework.bad_records import BadRecordsWriter
from ingestion.framework.loaders.base import BaseLoader

logger = logging.getLogger(__name__)


class DimStockParseError(Exception):
    """Raised when the NSE security master CSV cannot be parsed."""


# NSE-FIX column → internal name (case-insensitive matching applied)
_REQUIRED_COLUMNS = {
    "TCKRSYMB": "symbol",
    "SCTYSRS": "series",
    "FININSTRMNM": "company_name",
    "ISIN": "isin",
    "PARVAL": "face_value",
    "LISTGDT": "listing_date",
}

# Filename pattern: NSE_CM_security_DDMMYYYY.csv (the .csv.gz is decompressed
# by the fetcher before this loader sees it).
_FILENAME_DATE_RE = re.compile(r"NSE_CM_security_(\d{8})", re.IGNORECASE)


class DimStockLoader(BaseLoader):
    """Load NSE security master into ``dim_stock``.

    Args:
        engine: Optional SQLAlchemy engine (injected for testing).
        bad_records_writer: Optional :class:`BadRecordsWriter` to capture
            rows dropped during parsing (missing required fields, dedupe).
    """

    def __init__(
        self,
        engine=None,
        bad_records_writer: Optional[BadRecordsWriter] = None,
    ) -> None:
        self._engine = engine or get_engine()
        self._bad_records = bad_records_writer

    def load(self, path: Path, trade_date: date) -> int:
        """Parse *path* and upsert equity rows into ``dim_stock``.

        Args:
            path: Path to decompressed ``NSE_CM_security_DDMMYYYY.csv``.
            trade_date: Trade date the file represents (used for logging).

        Returns:
            Number of rows inserted or updated in ``dim_stock``.
        """
        df = self._parse(path, source_filename=path.name)
        rows = self._upsert(df)
        logger.info(
            "DimStockLoader: upserted %d equity rows for %s (file: %s)",
            rows, trade_date, path.name,
        )
        return rows

    def _parse(self, path: Path, source_filename: Optional[str] = None) -> pd.DataFrame:
        """Parse the NSE security master CSV.

        Args:
            path: Path to the (decompressed) CSV file.

        Returns:
            DataFrame with columns: symbol, company_name, isin, face_value,
            listing_date — already filtered to ``SctySrs == 'EQ'``.

        Raises:
            DimStockParseError: On missing columns or empty file after filter.
        """
        try:
            raw = pd.read_csv(path, dtype=str, na_values=["", "-"])
        except Exception as exc:
            raise DimStockParseError(f"Cannot read {path}: {exc}") from exc

        # Normalize header names: strip + uppercase + drop spaces/underscores
        # so that "Tckr Symb", "TckrSymb", "TCKR_SYMB" all map identically.
        normalized = {
            col: col.strip().upper().replace("_", "").replace(" ", "")
            for col in raw.columns
        }
        raw.rename(columns=normalized, inplace=True)

        missing = [k for k in _REQUIRED_COLUMNS if k not in raw.columns]
        if missing:
            raise DimStockParseError(
                f"Missing columns {missing} in {path.name}. "
                f"Found: {sorted(raw.columns)[:20]}..."
            )

        # Filter to EQ series only (one row per equity)
        raw["SCTYSRS"] = raw["SCTYSRS"].fillna("").str.strip()
        eq = raw[raw["SCTYSRS"] == "EQ"].copy()
        if eq.empty:
            raise DimStockParseError(
                f"No EQ-series rows in {path.name} after filtering"
            )

        df = pd.DataFrame({
            "symbol":       eq["TCKRSYMB"].str.strip(),
            "company_name": eq["FININSTRMNM"].str.strip(),
            "isin":         eq["ISIN"].str.strip(),
            "face_value":   pd.to_numeric(eq["PARVAL"], errors="coerce"),
            "listing_date": eq["LISTGDT"].map(_parse_listg_dt),
        })

        # Fall back to the date encoded in the filename when ListgDt is
        # missing/zero/invalid. NSE occasionally publishes ``ListgDt = 0``
        # for newly-listed instruments where the official listing date
        # hasn't propagated through their backend yet — using the file's
        # publication date is a reasonable proxy that lets us keep the
        # row instead of dropping it for an arguably-fixable nullable.
        fallback_date = _date_from_filename(source_filename)
        if fallback_date is not None:
            missing_listing = df["listing_date"].isna()
            n_filled = int(missing_listing.sum())
            if n_filled:
                df.loc[missing_listing, "listing_date"] = fallback_date
                logger.info(
                    "DimStockLoader: filled listing_date from filename for "
                    "%d rows (fallback=%s, file=%s)",
                    n_filled, fallback_date, source_filename,
                )
        elif source_filename is not None:
            logger.debug(
                "DimStockLoader: filename %s does not match "
                "NSE_CM_security_DDMMYYYY pattern — no listing_date fallback",
                source_filename,
            )

        # Drop rows missing any NOT NULL field; logged for visibility and
        # — if a BadRecordsWriter is configured — written to disk for
        # post-mortem analysis.
        required = ["symbol", "company_name", "isin", "face_value", "listing_date"]
        missing_mask = df[required].isna().any(axis=1)
        bad_missing = df[missing_mask]
        df = df[~missing_mask]
        if not bad_missing.empty:
            logger.warning(
                "DimStockLoader: dropped %d rows missing required fields",
                len(bad_missing),
            )
            if self._bad_records is not None and source_filename is not None:
                self._bad_records.write(
                    bad_missing,
                    original_filename=source_filename,
                    reason="missing required field",
                )

        # De-duplicate on symbol (NSE may publish same symbol twice for
        # corporate-action / merger lookups). Keep first occurrence.
        dup_mask = df.duplicated(subset=["symbol"], keep="first")
        bad_dupes = df[dup_mask]
        df = df[~dup_mask]
        if not bad_dupes.empty:
            logger.info(
                "DimStockLoader: dropped %d duplicate-symbol rows", len(bad_dupes)
            )
            if self._bad_records is not None and source_filename is not None:
                self._bad_records.write(
                    bad_dupes,
                    original_filename=source_filename,
                    reason="duplicate symbol (kept first)",
                )

        return df.reset_index(drop=True)

    def _upsert(self, df: pd.DataFrame) -> int:
        """Upsert rows into ``dim_stock``.

        Newly inserted rows get ``sector = 'Unknown'``, ``industry = NULL``,
        ``nifty50_member = FALSE``. On conflict, only file-sourced columns
        are updated — sector/industry/nifty50_member are preserved so that
        ``seed_stocks.py`` and ``ConstituentsLoader`` retain authority over
        those fields.
        """
        if df.empty:
            return 0

        upsert_sql = text("""
            INSERT INTO dim_stock (
                symbol, company_name, sector, industry, nifty50_member,
                listing_date, face_value, isin, last_updated
            ) VALUES (
                :symbol, :company_name, 'Unknown', NULL, FALSE,
                :listing_date, :face_value, :isin, NOW()
            )
            ON CONFLICT (symbol) DO UPDATE SET
                company_name = EXCLUDED.company_name,
                listing_date = EXCLUDED.listing_date,
                face_value   = EXCLUDED.face_value,
                isin         = EXCLUDED.isin,
                last_updated = NOW()
        """)

        records = df.to_dict("records")
        for rec in records:
            for k, v in rec.items():
                if pd.isna(v):
                    rec[k] = None

        with self._engine.begin() as conn:
            result = conn.execute(upsert_sql, records)
        return result.rowcount


def _parse_listg_dt(value) -> Optional[date]:
    """Parse NSE ``ListgDt`` field (Unix timestamp in seconds) into a date.

    Returns ``None`` if the value is missing, non-numeric, or ``0``.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        ts = int(float(str(value).strip()))
    except (ValueError, TypeError):
        return None
    if ts <= 0:
        return None
    try:
        return datetime.utcfromtimestamp(ts).date()
    except (OverflowError, OSError, ValueError):
        return None


def _date_from_filename(filename: Optional[str]) -> Optional[date]:
    """Extract the trade date from an NSE security-master filename.

    Recognises ``NSE_CM_security_DDMMYYYY.csv`` (and the .csv.gz variant
    before decompression). Returns ``None`` if the filename does not match
    or the embedded digits are not a valid calendar date.

    Examples:
        >>> _date_from_filename("NSE_CM_security_02012026.csv")
        datetime.date(2026, 1, 2)
        >>> _date_from_filename("garbage.csv") is None
        True
    """
    if not filename:
        return None
    match = _FILENAME_DATE_RE.search(filename)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%d%m%Y").date()
    except ValueError:
        return None
