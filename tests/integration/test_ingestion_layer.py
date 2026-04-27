"""Integration tests — Layer 1: Ingestion Layer.

Tests the CSV parsing → database loading pipeline:
- CSV header validation raises on missing columns
- Valid CSV loads successfully into fact_eod_price
- Idempotency: re-loading same file writes no new rows
- Ingestion log is written for every load() call
- Corporate actions round-trip: parse → load → query
- Data type correctness: prices as NUMERIC, volume as BIGINT
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import text

from config.database import get_engine
from ingestion.bhavcopy_loader import BhavcopyLoader
from ingestion.bhavcopy_parser import BhavcopyParser, BhavcopyParseError
from ingestion.corporate_actions_loader import CorporateActionsLoader
from ingestion.corporate_actions_parser import CorporateActionsParser

from tests.integration.fixtures.factories import (
    INTG_TEST_DATE,
    INTG_TEST_DATE_2,
    NIFTY50_SYMBOLS,
    SYM_A,
    SYM_B,
    build_bhavcopy_csv,
    build_bhavcopy_csv_bad_headers,
    build_bhavcopy_csv_all_filtered,
    build_corp_actions_csv,
)


# ─── Layer 1a: CSV Header Validation ────────────────────────────────────────

class TestCSVHeaderValidation:
    """BhavcopyParser must fail fast when expected headers are missing (TODO-001)."""

    def test_valid_csv_parses_successfully(self, tmp_path: Path) -> None:
        """A correctly formatted bhavcopy CSV parses without error."""
        csv = build_bhavcopy_csv(tmp_path, symbols=[SYM_A], trade_date=INTG_TEST_DATE)
        parser = BhavcopyParser()
        df = parser.parse(csv, trade_date=INTG_TEST_DATE)
        assert not df.empty
        assert df.iloc[0]["symbol"] == SYM_A
        assert df.iloc[0]["close"] > 0

    def test_missing_required_column_raises(self, tmp_path: Path) -> None:
        """CSV with a missing required column (ISIN) must raise BhavcopyParseError."""
        csv = build_bhavcopy_csv_bad_headers(tmp_path)
        parser = BhavcopyParser()
        with pytest.raises(BhavcopyParseError, match="Missing expected columns"):
            parser.parse(csv, trade_date=INTG_TEST_DATE)

    def test_all_rows_filtered_raises(self, tmp_path: Path) -> None:
        """CSV where all rows fail the series filter (e.g. MF series) raises an error."""
        csv = build_bhavcopy_csv_all_filtered(tmp_path)
        parser = BhavcopyParser()
        with pytest.raises(BhavcopyParseError, match="Series filter removed ALL rows"):
            parser.parse(csv, trade_date=INTG_TEST_DATE)

    def test_nonexistent_file_raises(self, tmp_path: Path) -> None:
        """Parsing a non-existent file raises BhavcopyParseError."""
        parser = BhavcopyParser()
        with pytest.raises(BhavcopyParseError, match="File not found"):
            parser.parse(tmp_path / "ghost.csv", trade_date=INTG_TEST_DATE)

    def test_parsed_df_has_correct_columns(self, tmp_path: Path) -> None:
        """Parsed DataFrame has all expected output columns for fact_eod_price."""
        csv = build_bhavcopy_csv(tmp_path, symbols=NIFTY50_SYMBOLS[:3],
                                  trade_date=INTG_TEST_DATE)
        parser = BhavcopyParser()
        df = parser.parse(csv, trade_date=INTG_TEST_DATE)
        required_cols = {
            "trade_date", "symbol", "open", "high", "low", "close",
            "prev_close", "total_traded_qty", "total_traded_value_lakh",
            "total_trades", "series",
        }
        assert required_cols.issubset(set(df.columns))

    def test_series_filter_only_keeps_eq(self, tmp_path: Path) -> None:
        """Parser filters out non-EQ series rows from a mixed CSV."""
        # The sample_bhavcopy.csv fixture contains MF and IL rows at the bottom
        sample = (
            Path(__file__).parent.parent / "fixtures" / "sample_bhavcopy.csv"
        )
        parser = BhavcopyParser()
        df = parser.parse(sample, trade_date=date(2024, 1, 15))
        assert set(df["series"].unique()).issubset({"EQ", "BE", "BL", "SM", "ST"})


# ─── Layer 1b: Bhavcopy Loader Idempotency ────────────────────────────────

class TestBhavcopyLoaderPipeline:
    """End-to-end: parse → load → verify rows are in DB."""

    def test_load_inserts_rows(self, tmp_path: Path) -> None:
        """Rows are inserted into fact_eod_price after a successful load."""
        csv = build_bhavcopy_csv(
            tmp_path, symbols=[SYM_A, SYM_B], trade_date=INTG_TEST_DATE
        )
        parser = BhavcopyParser()
        df = parser.parse(csv, trade_date=INTG_TEST_DATE)
        loader = BhavcopyLoader()
        stats = loader.load(df, source_file="intg_test_load.csv")

        assert stats["status"] in ("success", "partial")
        assert stats["rows_total"] >= 1
        assert stats["rows_inserted"] >= 1

    def test_idempotency_no_duplicate_rows(self, tmp_path: Path) -> None:
        """Loading the same file twice must not create duplicate rows (TODO-003)."""
        csv = build_bhavcopy_csv(
            tmp_path, symbols=[SYM_A], trade_date=INTG_TEST_DATE_2
        )
        parser = BhavcopyParser()
        df = parser.parse(csv, trade_date=INTG_TEST_DATE_2)
        loader = BhavcopyLoader()

        stats1 = loader.load(df, source_file="intg_test_idem.csv")
        assert stats1["rows_inserted"] >= 1

        stats2 = loader.load(df, source_file="intg_test_idem.csv")
        assert stats2["rows_inserted"] == 0, (
            "Second load of the same data must not insert any new rows"
        )

    def test_ingestion_log_written(self, tmp_path: Path) -> None:
        """Every loader.load() call must append a row to ingestion_log."""
        csv = build_bhavcopy_csv(
            tmp_path, symbols=[SYM_A], trade_date=INTG_TEST_DATE
        )
        parser = BhavcopyParser()
        df = parser.parse(csv, trade_date=INTG_TEST_DATE)
        loader = BhavcopyLoader()
        loader.load(df, source_file="intg_test_log.csv")

        engine = get_engine()
        with engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM ingestion_log WHERE source_file = 'intg_test_log.csv'")
            ).scalar()
        assert count >= 1

    def test_empty_dataframe_does_not_error(self) -> None:
        """Passing an empty DataFrame to load() returns success with 0 rows."""
        loader = BhavcopyLoader()
        stats = loader.load(pd.DataFrame(), source_file="intg_test_empty.csv")
        assert stats["status"] == "success"
        assert stats["rows_total"] == 0
        assert stats["rows_inserted"] == 0


# ─── Layer 1c: Data Type Correctness ────────────────────────────────────────

class TestDataTypeCorrectness:
    """Verify spec data type constraints: NUMERIC(12,2) for prices, BIGINT for volume."""

    def test_price_columns_are_numeric(self, tmp_path: Path) -> None:
        """Parsed price columns are numeric (float/Decimal), not strings."""
        csv = build_bhavcopy_csv(tmp_path, symbols=[SYM_A], trade_date=INTG_TEST_DATE)
        parser = BhavcopyParser()
        df = parser.parse(csv, trade_date=INTG_TEST_DATE)
        for col in ["open", "high", "low", "close", "prev_close"]:
            assert pd.api.types.is_numeric_dtype(df[col]), (
                f"Column {col} should be numeric, got {df[col].dtype}"
            )

    def test_volume_column_is_integer(self, tmp_path: Path) -> None:
        """total_traded_qty must be stored as integer (BIGINT), not float."""
        csv = build_bhavcopy_csv(tmp_path, symbols=[SYM_A], trade_date=INTG_TEST_DATE)
        parser = BhavcopyParser()
        df = parser.parse(csv, trade_date=INTG_TEST_DATE)
        assert pd.api.types.is_integer_dtype(df["total_traded_qty"]), (
            f"total_traded_qty should be integer, got {df['total_traded_qty'].dtype}"
        )

    def test_trade_date_is_date_type(self, tmp_path: Path) -> None:
        """trade_date column must be Python date / datetime.date, not a string."""
        csv = build_bhavcopy_csv(tmp_path, symbols=[SYM_A], trade_date=INTG_TEST_DATE)
        parser = BhavcopyParser()
        df = parser.parse(csv, trade_date=INTG_TEST_DATE)
        first_date = df.iloc[0]["trade_date"]
        assert isinstance(first_date, date), (
            f"trade_date should be date, got {type(first_date)}"
        )

    def test_prices_rounded_to_two_decimals_in_db(self, tmp_path: Path) -> None:
        """Prices stored in DB must survive a read-back as NUMERIC(12,2)."""
        engine = get_engine()
        csv = build_bhavcopy_csv(
            tmp_path, symbols=[SYM_A], trade_date=INTG_TEST_DATE,
            rows={SYM_A: {"close": 2865.12345}}   # extra decimals rounded by DB
        )
        parser = BhavcopyParser()
        df = parser.parse(csv, trade_date=INTG_TEST_DATE)
        loader = BhavcopyLoader()
        loader.load(df, source_file="intg_test_dtype.csv")

        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT close FROM fact_eod_price WHERE trade_date = :d AND symbol = :s"),
                {"d": INTG_TEST_DATE, "s": SYM_A},
            ).fetchone()

        assert row is not None
        # NUMERIC(12,2) stores 2 decimal places; value may differ from Python float
        assert abs(float(row[0]) - 2865.12) < 0.01


# ─── Layer 1d: Corporate Actions Pipeline ────────────────────────────────────

class TestCorporateActionsIngestion:
    """Parse → load corporate actions into fact_corporate_action."""

    def test_parse_and_load_corp_actions(self, tmp_path: Path) -> None:
        """Corporate actions CSV parses and loads into fact_corporate_action."""
        csv = build_corp_actions_csv(tmp_path)
        parser = CorporateActionsParser()
        df = parser.parse(csv)
        assert not df.empty

        loader = CorporateActionsLoader()
        n = loader.load(df)
        assert n >= 1

    def test_corp_actions_idempotency(self, tmp_path: Path) -> None:
        """Loading the same corporate actions twice does not create duplicates."""
        csv = build_corp_actions_csv(tmp_path)
        parser = CorporateActionsParser()
        df = parser.parse(csv)
        loader = CorporateActionsLoader()

        n1 = loader.load(df)
        n2 = loader.load(df)   # ON CONFLICT DO UPDATE → same rows upserted
        # Row count stays the same (upserts are idempotent)
        engine = get_engine()
        with engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM fact_corporate_action WHERE ex_date >= :d"),
                {"d": date(2099, 1, 1)},
            ).scalar()
        assert count == n1   # exactly n1 rows, not 2×n1

    def test_corp_actions_row_has_required_fields(self, tmp_path: Path) -> None:
        """Loaded corporate action rows have symbol, action_type, ex_date, purpose_text."""
        csv = build_corp_actions_csv(tmp_path)
        parser = CorporateActionsParser()
        df = parser.parse(csv)
        loader = CorporateActionsLoader()
        loader.load(df)

        engine = get_engine()
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT symbol, action_type, ex_date, purpose_text
                    FROM fact_corporate_action
                    WHERE ex_date >= :d
                    ORDER BY ex_date
                """),
                {"d": date(2099, 1, 1)},
            ).fetchall()

        assert len(rows) >= 1
        for row in rows:
            assert row[0] is not None    # symbol
            assert row[1] is not None    # action_type
            assert row[2] is not None    # ex_date
            assert row[3] is not None    # purpose_text
