"""Integration tests for backfill pipeline."""

import pytest
from sqlalchemy import text
from config.database import get_engine

@pytest.mark.integration
def test_row_count_per_symbol():
    """Verify >= 252 rows per symbol in fact_eod_price."""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT symbol, COUNT(*) as cnt 
            FROM fact_eod_price 
            GROUP BY symbol
        """))
        for row in result:
            assert row.cnt >= 252, f"Symbol {row.symbol} has only {row.cnt} rows"

@pytest.mark.integration
def test_no_duplicate_keys():
    """Verify no duplicate (trade_date, symbol) in fact_eod_price."""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT trade_date, symbol, COUNT(*) as cnt
            FROM fact_eod_price
            GROUP BY trade_date, symbol
            HAVING COUNT(*) > 1
        """))
        dupes = result.fetchall()
        assert len(dupes) == 0, f"Found duplicates: {dupes}"

@pytest.mark.integration
def test_1y_returns_non_null():
    """Verify 1Y returns are non-NULL in mart_stock_signals for latest date."""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT symbol, return_1y 
            FROM mart_stock_signals 
            WHERE calc_date = (SELECT MAX(calc_date) FROM mart_stock_signals)
        """))
        rows = result.fetchall()
        assert len(rows) > 0, "No records in mart_stock_signals"
        for row in rows:
            assert row.return_1y is not None, f"return_1y is NULL for {row.symbol}"

@pytest.mark.integration
def test_index_prices_populated():
    """Verify nifty50_index_prices has >= 200 rows."""
    engine = get_engine()
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM nifty50_index_prices")).scalar()
        assert count >= 200, f"Only {count} dates in nifty50_index_prices"

@pytest.mark.integration
def test_52wk_populated():
    """Verify fact_52wk is populated for the latest date."""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT symbol, wk52_high, wk52_low 
            FROM fact_52wk 
            WHERE trade_date = (SELECT MAX(trade_date) FROM fact_52wk)
        """))
        rows = result.fetchall()
        assert len(rows) > 0, "No records in fact_52wk"
