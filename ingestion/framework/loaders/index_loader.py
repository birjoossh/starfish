"""Index closing price loader
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

class IndexPriceLoader(BaseLoader):
    """Load daya close index prices

    Args:
        engine: Optional SQLAlchemy engine (injected for testing).
    """

    def __init__(self, engine=None) -> None:
        self._engine = engine or get_engine()

    def load(self, csv_path: Path, trade_date: date) -> int:
        """Parse index CSV and upsert Nifty 50 close price."""
        try:
            df = pd.read_csv(csv_path)
            rows_written = 0

            # Filter for Nifty 50
            if "Index Name" not in df.columns or "Closing Index Value" not in df.columns:
                logger.warning(f"Invalid index CSV shape in {csv_path}")
                return 0

            nifty_row = df[df["Index Name"].str.upper() == "NIFTY 50"]
            if nifty_row.empty:
                logger.warning(f"Nifty 50 not found in {csv_path}")
                return 0

            close_price = float(nifty_row.iloc[0]["Closing Index Value"])

            upsert_sql = text("""
                INSERT INTO nifty50_index_prices (trade_date, close)
                VALUES (:trade_date, :close)
                ON CONFLICT (trade_date) DO UPDATE SET
                    close = EXCLUDED.close
            """)

            with self._engine.connect() as conn:
                conn.execute(upsert_sql, {
                    "trade_date": trade_date,
                    "close": close_price
                })
                conn.commit()
            logger.info("Index price loaded for date: %s", trade_date)
            return 1

        except Exception as e:
            logger.error(f"Failed to load index data from {csv_path}: {e}")
            return 0
    
