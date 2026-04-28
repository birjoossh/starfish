"""Reconstitution table loader — local manual-drop only (Source D).

No HTTP fetch. The file ``nifty50_reconstitution_log.csv`` must be placed
manually in ``data/raw/reconstitution/`` within 24h of the official NSE
announcement (per spec Section 3-D).

Expected columns: symbol, company, isin, action (ADD/DELETE),
effective_date, review_period, reason_code.

Target table: ``dim_nifty50_constituent`` (adds or closes constituent rows)

TODO: Implement upsert logic once the reconstitution CSV format is confirmed
with an actual NSE announcement. Current implementation parses the file
and validates columns but does not write to DB until format is confirmed.
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

_REQUIRED_COLUMNS = {"symbol", "action", "effective_date", "review_period"}


class ReconstitutionLoader(BaseLoader):
    """Load reconstitution log CSV into ``dim_nifty50_constituent``.

    This is a LOCAL-ONLY source. There is no HTTP fetcher for this source.
    Place the CSV manually in ``data/raw/reconstitution/``.

    Args:
        engine: Optional SQLAlchemy engine (injected for testing).
    """

    def __init__(self, engine=None) -> None:
        self._engine = engine or get_engine()

    def load(self, path: Path, trade_date: date) -> int:
        """Parse reconstitution CSV and update ``dim_nifty50_constituent``.

        Args:
            path: Path to the manual-drop reconstitution CSV.
            trade_date: The effective date of the reconstitution.

        Returns:
            Number of rows inserted/updated.

        Raises:
            FileNotFoundError: If *path* does not exist.
            ValueError: If required columns are missing.
        """
        if not path.exists():
            raise FileNotFoundError(f"Reconstitution file not found: {path}")

        raw = pd.read_csv(path, dtype=str)
        raw.columns = raw.columns.str.strip().str.lower()

        missing = _REQUIRED_COLUMNS - set(raw.columns)
        if missing:
            raise ValueError(
                f"Reconstitution CSV missing required columns: {sorted(missing)}. "
                f"Found: {sorted(raw.columns)}"
            )

        rows_written = 0
        for _, row in raw.iterrows():
            action = str(row.get("action", "")).strip().upper()
            symbol = str(row.get("symbol", "")).strip().upper()
            effective = str(row.get("effective_date", "")).strip()
            review = str(row.get("review_period", "Auto")).strip()

            if action not in ("ADD", "DELETE"):
                logger.warning(
                    "Unknown reconstitution action '%s' for %s — skipped",
                    action, symbol,
                )
                continue

            change_type = "Addition" if action == "ADD" else "Deletion"

            try:
                eff_date = date.fromisoformat(effective) if effective else trade_date
            except ValueError:
                eff_date = trade_date

            with self._engine.begin() as conn:
                result = conn.execute(text("""
                    INSERT INTO dim_nifty50_constituent
                        (symbol, effective_from, effective_to, index_weight_pct,
                         replaced_symbol, change_type, review_period)
                    VALUES
                        (:symbol, :effective_from, NULL, NULL, NULL, :change_type, :review_period)
                    ON CONFLICT (symbol, effective_from) DO NOTHING
                """), {
                    "symbol": symbol,
                    "effective_from": eff_date,
                    "change_type": change_type,
                    "review_period": review,
                })
                rows_written += result.rowcount

        logger.info("ReconstitutionLoader: %d rows written", rows_written)
        return rows_written
