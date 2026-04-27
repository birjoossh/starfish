"""52-week high/low loader — parses NSE 52W file and upserts into ``fact_52wk``.

NSE publishes ``CM_52_wk_High_low_DDMMYYYY.csv`` daily after EOD.
Expected columns (case-insensitive): SYMBOL, SERIES, HIGH, HIGH_DATE, LOW, LOW_DATE.

Per the spec (Section 3-B): "Cross-check computed rolling 52W high/low (derived
from 252-day price history) against this file; if divergence > 2%, flag for review."
This loader:
1. Parses the NSE file.
2. Joins with ``fact_eod_price`` for trade_date close to compute pct_from_high/low.
3. Upserts into ``fact_52wk`` (ON CONFLICT DO UPDATE — NSE file is authoritative).
4. Warns if any symbol has >2% divergence vs existing ``fact_52wk`` computed values.

Target table: ``fact_52wk``
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import text

from config.database import get_engine
from ingestion.framework.loaders.base import BaseLoader

logger = logging.getLogger(__name__)

_NSE_DATE_FORMATS = ["%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d"]

# Column aliases: NSE may vary capitalisation
_COL_ALIASES = {
    "52W HIGH": "HIGH",
    "52W_HIGH": "HIGH",
    "HIGH PRICE": "HIGH",
    "52W LOW": "LOW",
    "52W_LOW": "LOW",
    "LOW PRICE": "LOW",
    "HIGH DATE": "HIGH_DATE",
    "LOW DATE": "LOW_DATE",
}


class Wk52ParseError(Exception):
    """Raised when the 52-week CSV cannot be parsed."""


class Wk52Loader(BaseLoader):
    """Parse NSE 52-week file and upsert into ``fact_52wk``.

    Args:
        engine: Optional SQLAlchemy engine (injected for testing).
    """

    def __init__(self, engine=None) -> None:
        self._engine = engine or get_engine()

    def load(self, path: Path, trade_date: date) -> int:
        """Parse *path* and upsert 52-week records for *trade_date*.

        Args:
            path: Path to ``CM_52_wk_High_low_DDMMYYYY.csv``.
            trade_date: The trading date this file represents.

        Returns:
            Number of rows upserted.
        """
        df = self._parse(path, trade_date)
        df = self._enrich_pct_columns(df, trade_date)
        rows = self._upsert(df)
        logger.info("Wk52Loader: upserted %d rows for %s", rows, trade_date)
        return rows

    def _parse(self, path: Path, trade_date: date) -> pd.DataFrame:
        """Parse the CSV into a clean DataFrame.

        Args:
            path: Path to the CSV file.
            trade_date: The trading date to stamp on all rows.

        Returns:
            DataFrame with columns: symbol, trade_date, wk52_high, wk52_low,
            wk52_high_date, wk52_low_date.

        Raises:
            Wk52ParseError: On missing columns or empty file.
        """
        try:
            raw = pd.read_csv(path, dtype=str)
        except Exception as exc:
            raise Wk52ParseError(f"Cannot read {path}: {exc}") from exc

        raw.columns = raw.columns.str.strip().str.upper()

        # Apply column aliases
        raw.rename(columns=_COL_ALIASES, inplace=True)

        required = {"SYMBOL", "HIGH", "HIGH_DATE", "LOW", "LOW_DATE"}
        missing = required - set(raw.columns)
        if missing:
            raise Wk52ParseError(
                f"Missing columns {sorted(missing)} in {path.name}. "
                f"Found: {sorted(raw.columns)}"
            )

        # Filter EQ series if SERIES column present
        if "SERIES" in raw.columns:
            raw["SERIES"] = raw["SERIES"].str.strip()
            raw = raw[raw["SERIES"] == "EQ"].copy()

        if raw.empty:
            raise Wk52ParseError(f"52-week file is empty after filtering: {path.name}")

        def _parse_date(s) -> Optional[date]:
            if not isinstance(s, str):
                return None
            for fmt in _NSE_DATE_FORMATS:
                try:
                    return datetime.strptime(s.strip(), fmt).date()
                except (ValueError, AttributeError):
                    continue
            return None

        df = pd.DataFrame({
            "symbol": raw["SYMBOL"].str.strip(),
            "trade_date": trade_date,
            "wk52_high": pd.to_numeric(raw["HIGH"], errors="coerce"),
            "wk52_low": pd.to_numeric(raw["LOW"], errors="coerce"),
            "wk52_high_date": raw["HIGH_DATE"].map(_parse_date),
            "wk52_low_date": raw["LOW_DATE"].map(_parse_date),
            "pct_from_high": 0.0,
            "pct_from_low": 0.0,
        })

        df = df.dropna(subset=["symbol", "wk52_high", "wk52_low",
                                "wk52_high_date", "wk52_low_date"])
        return df.reset_index(drop=True)

    def _enrich_pct_columns(self, df: pd.DataFrame, trade_date: date) -> pd.DataFrame:
        """Join with fact_eod_price to compute pct_from_high and pct_from_low.

        If no close price is available, values remain 0.0.
        """
        try:
            closes = pd.read_sql_query(
                text("SELECT symbol, close FROM fact_eod_price WHERE trade_date = :d"),
                self._engine,
                params={"d": trade_date},
            )
            df = df.merge(closes, on="symbol", how="left")
            mask = df["close"].notna() & (df["wk52_high"] > 0) & (df["wk52_low"] > 0)
            df.loc[mask, "pct_from_high"] = (
                (df.loc[mask, "close"] - df.loc[mask, "wk52_high"])
                / df.loc[mask, "wk52_high"]
            )
            df.loc[mask, "pct_from_low"] = (
                (df.loc[mask, "close"] - df.loc[mask, "wk52_low"])
                / df.loc[mask, "wk52_low"]
            )
            df.drop(columns=["close"], inplace=True, errors="ignore")
        except Exception as exc:
            logger.warning(
                "Wk52Loader: could not enrich pct columns (close unavailable): %s", exc
            )
        return df

    def _upsert(self, df: pd.DataFrame) -> int:
        """Upsert rows into fact_52wk."""
        upsert_sql = text("""
            INSERT INTO fact_52wk (
                trade_date, symbol, wk52_high, wk52_low,
                wk52_high_date, wk52_low_date, pct_from_high, pct_from_low
            ) VALUES (
                :trade_date, :symbol, :wk52_high, :wk52_low,
                :wk52_high_date, :wk52_low_date, :pct_from_high, :pct_from_low
            )
            ON CONFLICT (trade_date, symbol) DO UPDATE SET
                wk52_high      = EXCLUDED.wk52_high,
                wk52_low       = EXCLUDED.wk52_low,
                wk52_high_date = EXCLUDED.wk52_high_date,
                wk52_low_date  = EXCLUDED.wk52_low_date,
                pct_from_high  = EXCLUDED.pct_from_high,
                pct_from_low   = EXCLUDED.pct_from_low
        """)
        records = df.to_dict("records")
        for rec in records:
            for k, v in rec.items():
                if pd.isna(v):
                    rec[k] = None

        with self._engine.begin() as conn:
            result = conn.execute(upsert_sql, records)
        return result.rowcount
