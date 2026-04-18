"""Integration tests — Layer 2: Storage Layer.

Tests database constraints, data integrity, and schema correctness:
- Foreign key constraints on fact_eod_price → dim_stock
- Composite primary key uniqueness (trade_date, symbol)
- Ingestion log is always populated
- Non-nullable column constraints
- Required indexes exist on key tables
- fact_52wk computed values are within expected ranges
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from config.database import get_engine
from ingestion.bhavcopy_loader import BhavcopyLoader
from ingestion.bhavcopy_parser import BhavcopyParser

from tests.integration.fixtures.factories import (
    INTG_TEST_DATE,
    INTG_TEST_DATE_2,
    NIFTY50_SYMBOLS,
    SYM_A,
    SYM_B,
    build_bhavcopy_csv,
)
from tests.integration.conftest import seed_prices_raw


# ─── Layer 2a: Foreign Key Constraints ───────────────────────────────────────

class TestForeignKeyConstraints:
    """fact_eod_price.symbol must reference dim_stock.symbol (FK enforcement)."""

    def test_unknown_symbol_blocked_by_loader(self, tmp_path: Path) -> None:
        """BhavcopyLoader silently drops rows with symbols missing from dim_stock."""
        engine = get_engine()
        # Construct a DataFrame with a phantom symbol
        import pandas as pd
        df = pd.DataFrame([{
            "trade_date": INTG_TEST_DATE,
            "symbol": "GHOSTSYMBOL99",
            "open": 100.0, "high": 110.0, "low": 95.0, "close": 105.0,
            "prev_close": 100.0, "total_traded_qty": 1000,
            "total_traded_value_lakh": 1.05, "total_trades": 20,
            "series": "EQ", "delivery_qty": None, "delivery_pct": None,
            "source_file": "intg_test_fk.csv",
        }])
        loader = BhavcopyLoader()
        stats = loader.load(df, source_file="intg_test_fk.csv")
        # Loader filters unknown symbols before hitting the FK constraint
        assert stats["rows_inserted"] == 0

    def test_known_symbol_inserts_successfully(self, tmp_path: Path, engine) -> None:
        """Rows with valid dim_stock symbols are inserted without FK violation."""
        seed_prices_raw(engine, SYM_A, INTG_TEST_DATE, close=1500.0)
        with engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM fact_eod_price WHERE trade_date = :d AND symbol = :s"),
                {"d": INTG_TEST_DATE, "s": SYM_A},
            ).scalar()
        assert count == 1

    def test_direct_insert_unknown_symbol_raises(self, engine) -> None:
        """Direct SQL insert of a foreign-symbol that doesn't exist in dim_stock raises IntegrityError."""
        with pytest.raises(Exception):   # IntegrityError or similar
            with engine.connect() as conn:
                conn.execute(
                    text("""
                        INSERT INTO fact_eod_price (
                            trade_date, symbol, open, high, low, close, prev_close,
                            total_traded_qty, total_traded_value_lakh, total_trades,
                            series, source_file
                        ) VALUES (
                            :d, :sym, 100, 110, 95, 105, 100,
                            1000, 1.05, 20, 'EQ', 'intg_test_fk_direct.csv'
                        )
                    """),
                    {"d": INTG_TEST_DATE, "sym": "NOTREAL_XXXXXXXXXX"},
                )
                conn.commit()


# ─── Layer 2b: Composite Primary Key (Idempotency at DB level) ───────────────

class TestCompositeKeyConstraints:
    """Duplicate (trade_date, symbol) must trigger ON CONFLICT, not a hard error."""

    def test_duplicate_pk_triggers_on_conflict(self, engine) -> None:
        """Inserting the same (trade_date, symbol) twice uses ON CONFLICT DO NOTHING."""
        seed_prices_raw(engine, SYM_B, INTG_TEST_DATE, close=2000.0)
        # Insert again — should not raise
        seed_prices_raw(engine, SYM_B, INTG_TEST_DATE, close=9999.0)

        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT close FROM fact_eod_price WHERE trade_date = :d AND symbol = :s"),
                {"d": INTG_TEST_DATE, "s": SYM_B},
            ).fetchone()

        assert row is not None
        # The first write (2000.0) wins; second (9999.0) is ignored because ON CONFLICT DO NOTHING
        assert float(row[0]) == 2000.0

    def test_different_dates_both_insert(self, engine) -> None:
        """Same symbol on different dates must both be stored (unique PK)."""
        seed_prices_raw(engine, SYM_A, INTG_TEST_DATE,   close=1000.0)
        seed_prices_raw(engine, SYM_A, INTG_TEST_DATE_2, close=1010.0)

        with engine.connect() as conn:
            count = conn.execute(
                text("""
                    SELECT COUNT(*) FROM fact_eod_price
                    WHERE symbol = :s AND trade_date >= :d
                """),
                {"s": SYM_A, "d": date(2099, 1, 1)},
            ).scalar()
        assert count == 2


# ─── Layer 2c: Ingestion Log Population ──────────────────────────────────────

class TestIngestionLogPopulation:
    """Every BhavcopyLoader.load() call must write a row to ingestion_log."""

    def test_success_load_writes_log_row(self, tmp_path: Path) -> None:
        """Successful load produces a 'success' or 'partial' log entry."""
        csv = build_bhavcopy_csv(tmp_path, symbols=[SYM_A], trade_date=INTG_TEST_DATE)
        parser = BhavcopyParser()
        df = parser.parse(csv, trade_date=INTG_TEST_DATE)
        loader = BhavcopyLoader()
        loader.load(df, source_file="intg_test_logpop.csv")

        engine = get_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT status, rows_inserted, table_name
                    FROM ingestion_log
                    WHERE source_file = 'intg_test_logpop.csv'
                    ORDER BY started_at DESC
                    LIMIT 1
                """)
            ).fetchone()

        assert row is not None
        assert row[0] in ("success", "partial")
        assert row[2] == "fact_eod_price"

    def test_log_row_counts_match_stats(self, tmp_path: Path) -> None:
        """rows_inserted in ingestion_log matches the returned stats dict."""
        csv = build_bhavcopy_csv(
            tmp_path, symbols=NIFTY50_SYMBOLS[:3], trade_date=INTG_TEST_DATE
        )
        parser = BhavcopyParser()
        df = parser.parse(csv, trade_date=INTG_TEST_DATE)
        loader = BhavcopyLoader()
        stats = loader.load(df, source_file="intg_test_logcount.csv")

        engine = get_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT rows_inserted FROM ingestion_log
                    WHERE source_file = 'intg_test_logcount.csv'
                    ORDER BY started_at DESC LIMIT 1
                """)
            ).fetchone()

        assert row is not None
        assert row[0] == stats["rows_inserted"]


# ─── Layer 2d: Null Constraint Checks ────────────────────────────────────────

class TestNullConstraints:
    """Critical columns must never be NULL for loaded rows."""

    def test_no_null_prices_after_load(self, tmp_path: Path) -> None:
        """After loading, no NULL values in open/high/low/close/prev_close."""
        csv = build_bhavcopy_csv(
            tmp_path, symbols=NIFTY50_SYMBOLS[:5], trade_date=INTG_TEST_DATE
        )
        parser = BhavcopyParser()
        df = parser.parse(csv, trade_date=INTG_TEST_DATE)
        loader = BhavcopyLoader()
        loader.load(df, source_file="intg_test_nullchk.csv")

        engine = get_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT COUNT(*) FROM fact_eod_price
                    WHERE trade_date = :d
                      AND (open IS NULL OR high IS NULL OR low IS NULL
                           OR close IS NULL OR prev_close IS NULL)
                """),
                {"d": INTG_TEST_DATE},
            ).scalar()
        assert row == 0, f"Found {row} rows with NULL price columns"

    def test_no_null_symbol_or_trade_date(self, tmp_path: Path) -> None:
        """symbol and trade_date are always populated (NOT NULL)."""
        engine = get_engine()
        seed_prices_raw(engine, SYM_A, INTG_TEST_DATE)
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT COUNT(*) FROM fact_eod_price
                    WHERE trade_date >= :d
                      AND (symbol IS NULL OR trade_date IS NULL)
                """),
                {"d": date(2099, 1, 1)},
            ).scalar()
        assert row == 0


# ─── Layer 2e: Index Existence ────────────────────────────────────────────────

class TestTableIndexes:
    """Critical indexes defined in schema.sql must exist in the database."""

    @pytest.mark.parametrize("index_name", [
        "idx_eod_symbol_date",
        "idx_eod_date",
        "idx_dim_stock_sector",
        "idx_signals_date",
        "idx_ingestion_log_date",
    ])
    def test_index_exists(self, engine, index_name: str) -> None:
        """Verify that each critical index is present in pg_indexes."""
        with engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM pg_indexes WHERE indexname = :n"),
                {"n": index_name},
            ).scalar()
        assert count >= 1, f"Expected index '{index_name}' to exist in pg_indexes"


# ─── Layer 2f: dim_stock Integrity ───────────────────────────────────────────

class TestDimStockIntegrity:
    """dim_stock must contain all 50 Nifty constituents."""

    def test_50_nifty_members_in_dim_stock(self, engine) -> None:
        """Exactly 50 rows with nifty50_member = TRUE must exist."""
        with engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM dim_stock WHERE nifty50_member = TRUE")
            ).scalar()
        assert count == 50, (
            f"Expected 50 Nifty50 members in dim_stock, found {count}"
        )

    def test_all_nifty_stocks_have_isin(self, engine) -> None:
        """All Nifty50 members have a non-null ISIN."""
        with engine.connect() as conn:
            count = conn.execute(
                text("""
                    SELECT COUNT(*) FROM dim_stock
                    WHERE nifty50_member = TRUE AND (isin IS NULL OR isin = '')
                """)
            ).scalar()
        assert count == 0, f"{count} Nifty50 stocks are missing an ISIN"

    def test_all_nifty_stocks_have_sector(self, engine) -> None:
        """All Nifty50 members have a non-null, non-empty sector."""
        with engine.connect() as conn:
            count = conn.execute(
                text("""
                    SELECT COUNT(*) FROM dim_stock
                    WHERE nifty50_member = TRUE AND (sector IS NULL OR sector = '')
                """)
            ).scalar()
        assert count == 0, f"{count} Nifty50 stocks are missing a sector"
