"""Shared fixtures for integration tests.

Strategy:
- Tests reuse the real dev DB but only touch rows with trade_date >= 2099-01-01
  (same pattern as tests/unit/test_ingestion.py).
- All teardown removes rows with these sentinel dates.
- ``seed_prices`` inserts directly into fact_eod_price via BhavcopyLoader.load().
- ``seed_corp_actions`` inserts directly into fact_corporate_action.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Generator

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from api.main import app
from config.database import get_engine
from ingestion.bhavcopy_loader import BhavcopyLoader
from ingestion.corporate_actions_loader import CorporateActionsLoader
from ingestion.corporate_actions_parser import CorporateActionsParser

logger = logging.getLogger(__name__)

# ─── Sentinel date bounds ────────────────────────────────────────────────────
_MIN_TEST_DATE = date(2099, 1, 1)

_TABLES_TO_CLEAN: list[tuple[str, str]] = [
    ("mart_stock_signals",   "calc_date"),
    ("mart_volume_anomaly",  "calc_date"),
    ("fact_52wk",            "trade_date"),
    ("fact_eod_price",       "trade_date"),
    ("fact_corporate_event", "event_date"),
    ("fact_corporate_action","ex_date"),
]


# ─── DB cleanup helpers ──────────────────────────────────────────────────────

def _purge_test_data() -> None:
    """Delete all rows written by integration tests (dates >= 2099-01-01)."""
    engine = get_engine()
    with engine.connect() as conn:
        for table, date_col in _TABLES_TO_CLEAN:
            try:
                conn.execute(
                    text(f"DELETE FROM {table} WHERE {date_col} >= :d"),
                    {"d": _MIN_TEST_DATE},
                )
            except Exception as exc:
                logger.warning("Could not clean %s: %s", table, exc)
        # Clean ingestion_log entries written by test pipelines
        conn.execute(
            text("DELETE FROM ingestion_log WHERE source_file LIKE 'intg_test_%'")
        )
        conn.commit()


# ─── Session-scoped client (one FastAPI app per session) ─────────────────────

@pytest.fixture(scope="session")
def api_client() -> TestClient:
    """Return a TestClient for the FastAPI app."""
    return TestClient(app)


# ─── Auto-use cleanup fixture ────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_test_data() -> Generator[None, None, None]:
    """Run before and after each test to ensure a clean slate."""
    _purge_test_data()
    yield
    _purge_test_data()


# ─── DB seeding helpers ──────────────────────────────────────────────────────

def seed_prices(df: pd.DataFrame, source_file: str = "intg_test_prices.csv") -> dict:
    """Insert price rows into fact_eod_price using the production loader.

    Args:
        df: DataFrame matching fact_eod_price schema (output of factories).
        source_file: Must start with 'intg_test_' to ensure cleanup.

    Returns:
        BhavcopyLoader.load() stats dict.
    """
    assert source_file.startswith("intg_test_"), (
        "source_file must start with 'intg_test_' for cleanup to work"
    )
    loader = BhavcopyLoader()
    return loader.load(df, source_file=source_file)


def seed_corp_actions(df: pd.DataFrame) -> int:
    """Insert corporate action rows into fact_corporate_action.

    Returns:
        Number of rows upserted.
    """
    loader = CorporateActionsLoader()
    return loader.load(df)


def seed_prices_raw(
    engine,
    symbol: str,
    trade_date: date,
    close: float = 1000.0,
    prev_close: float = 990.0,
    qty: int = 5_000_000,
) -> None:
    """Low-level helper — insert a single fact_eod_price row directly.

    Useful for storage-layer constraint tests that need to bypass the loader.
    """
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO fact_eod_price (
                    trade_date, symbol, open, high, low, close, prev_close,
                    total_traded_qty, total_traded_value_lakh, total_trades,
                    series, source_file
                ) VALUES (
                    :trade_date, :symbol, :open, :high, :low, :close, :prev_close,
                    :qty, :val, :trades, 'EQ', 'intg_test_raw.csv'
                )
                ON CONFLICT (trade_date, symbol) DO NOTHING
            """),
            {
                "trade_date": trade_date,
                "symbol": symbol,
                "open": close * 0.995,
                "high": close * 1.005,
                "low": close * 0.990,
                "close": close,
                "prev_close": prev_close,
                "qty": qty,
                "val": round(close * qty / 1e5, 2),
                "trades": qty // 50,
            },
        )
        conn.commit()


@pytest.fixture
def engine():
    """Yield the production SQLAlchemy engine."""
    return get_engine()
