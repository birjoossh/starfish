"""Nifty 50 constituents loader → ``dim_nifty50_constituent``.

Downloads/reads ``ind_nifty50list.csv`` from NSE Indices. This file always
contains the **current** 50 constituents (no historical date in the file).

Behaviour:
- Parses the CSV to get the current symbol list.
- For each symbol already in ``dim_stock``, inserts a row into
  ``dim_nifty50_constituent`` with ``effective_from = trade_date``,
  ``effective_to = NULL``, ``change_type = 'Addition'``,
  ``review_period = 'Auto'``. Uses ``ON CONFLICT DO NOTHING`` so running
  twice for the same date is safe.
- Symbols NOT in ``dim_stock`` are skipped with a WARNING (FK constraint
  would reject them anyway).

Target table: ``dim_nifty50_constituent``
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from config.database import get_engine
from ingestion.framework.loaders.base import BaseLoader

logger = logging.getLogger(__name__)


class ConstituentsParseError(Exception):
    """Raised when the constituents CSV cannot be parsed."""


class ConstituentsLoader(BaseLoader):
    """Load Nifty 50 constituents from NSE CSV into ``dim_nifty50_constituent``.

    Args:
        engine: Optional SQLAlchemy engine (injected for testing).
    """

    def __init__(self, engine=None) -> None:
        self._engine = engine or get_engine()

    def load(self, path: Path, trade_date: date) -> int:
        """Parse *path* and upsert constituent records.

        Args:
            path: Path to ``ind_nifty50list.csv``.
            trade_date: Effective date for new constituent rows.

        Returns:
            Number of rows inserted into ``dim_nifty50_constituent``.
        """
        df = self._parse(path)
        rows = self._upsert(df, trade_date)
        logger.info(
            "ConstituentsLoader: %d constituent rows inserted for %s",
            rows, trade_date
        )
        return rows

    def _parse(self, path: Path) -> pd.DataFrame:
        """Parse constituents CSV.

        Args:
            path: Path to the CSV file.

        Returns:
            DataFrame with columns: symbol, company_name, industry, isin.

        Raises:
            ConstituentsParseError: On missing columns or empty file.
        """
        try:
            raw = pd.read_csv(path, dtype=str)
        except Exception as exc:
            raise ConstituentsParseError(f"Cannot read {path}: {exc}") from exc

        raw.columns = raw.columns.str.strip().str.lower()

        # Find symbol column (NSE uses "Symbol" header)
        sym_col = next(
            (c for c in raw.columns if "symbol" in c and "company" not in c), None
        )
        if sym_col is None:
            raise ConstituentsParseError(
                f"No symbol column found in {path.name}. Columns: {list(raw.columns)}"
            )

        raw = raw[raw[sym_col].notna() & (raw[sym_col].str.strip() != "")]
        if raw.empty:
            raise ConstituentsParseError(f"Constituents file is empty: {path.name}")

        company_col = next((c for c in raw.columns if "company" in c), None)
        industry_col = next((c for c in raw.columns if "industry" in c), None)
        isin_col = next((c for c in raw.columns if "isin" in c), None)

        df = pd.DataFrame({
            "symbol": raw[sym_col].str.strip(),
            "company_name": raw[company_col].str.strip() if company_col else "",
            "industry": raw[industry_col].str.strip() if industry_col else "",
            "isin": raw[isin_col].str.strip() if isin_col else "",
        })
        return df.reset_index(drop=True)

    def _upsert(self, df: pd.DataFrame, trade_date: date) -> int:
        """Insert new constituent rows into ``dim_nifty50_constituent``."""
        # Only insert for symbols that exist in dim_stock (FK constraint)
        with self._engine.connect() as conn:
            valid_symbols = set(
                row[0] for row in conn.execute(text("SELECT symbol FROM dim_stock"))
            )

        skipped = set(df["symbol"]) - valid_symbols
        if skipped:
            logger.warning(
                "ConstituentsLoader: %d symbols not in dim_stock, skipping: %s",
                len(skipped), sorted(skipped)[:10]
            )

        df = df[df["symbol"].isin(valid_symbols)].copy()
        if df.empty:
            return 0

        insert_sql = text("""
            INSERT INTO dim_nifty50_constituent
                (symbol, effective_from, effective_to, index_weight_pct,
                 replaced_symbol, change_type, review_period)
            VALUES
                (:symbol, :effective_from, NULL, NULL, NULL, 'Addition', 'Auto')
            ON CONFLICT (symbol, effective_from) DO NOTHING
        """)

        records = [
            {"symbol": row["symbol"], "effective_from": trade_date}
            for _, row in df.iterrows()
        ]

        with self._engine.begin() as conn:
            result = conn.execute(insert_sql, records)
        return result.rowcount
