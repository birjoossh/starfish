"""Tests for bhavcopy parser."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from ingestion.bhavcopy_parser import BhavcopyParseError, BhavcopyParser


class TestBhavcopyParser:
    def test_parse_valid_csv(self, sample_csv_path):
        parser = BhavcopyParser()
        df = parser.parse(sample_csv_path, trade_date=date(2024, 1, 15))

        assert len(df) == 50  # 50 EQ rows (MF, IL filtered out)
        assert list(df.columns) == [
            "trade_date", "symbol", "open", "high", "low", "close",
            "prev_close", "total_traded_qty", "total_traded_value_lakh",
            "total_trades", "series", "delivery_qty", "delivery_pct", "source_file"
        ]
        assert df["trade_date"].iloc[0] == date(2024, 1, 15)

    def test_series_filter(self, sample_csv_path):
        parser = BhavcopyParser(series_filter=["EQ"])
        df = parser.parse(sample_csv_path, trade_date=date(2024, 1, 15))

        assert (df["series"] == "EQ").all()
        assert len(df) == 50

    def test_header_validation(self, tmp_path):
        # Create CSV with missing columns
        bad_csv = tmp_path / "bad.csv"
        bad_csv.write_text("SYMBOL,OPEN,CLOSE\nRELIANCE,100,101")

        parser = BhavcopyParser()
        with pytest.raises(BhavcopyParseError, match="Missing expected columns"):
            parser.parse(bad_csv)

    def test_empty_file(self, tmp_path):
        empty_csv = tmp_path / "empty.csv"
        empty_csv.write_text("")

        parser = BhavcopyParser()
        with pytest.raises(BhavcopyParseError, match="Failed to read CSV|empty"):
            parser.parse(empty_csv)

    def test_header_only(self, tmp_path):
        header_csv = tmp_path / "header.csv"
        header_csv.write_text(
            "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,"
            "TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN"
        )

        parser = BhavcopyParser()
        with pytest.raises(BhavcopyParseError, match="empty"):
            parser.parse(header_csv)

    def test_all_rows_filtered_out(self, tmp_path):
        # CSV with only non-EQ series
        bad_csv = tmp_path / "all_filtered.csv"
        bad_csv.write_text(
            "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,"
            "TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN\n"
            "RELIANCE,MF,100,101,99,100,100,99,1000,100000,15-JAN-2024,100,INE002A01018"
        )

        parser = BhavcopyParser()
        with pytest.raises(BhavcopyParseError, match="filter removed ALL rows"):
            parser.parse(bad_csv)

    def test_date_extraction(self, sample_csv_path):
        parser = BhavcopyParser()
        df = parser.parse(sample_csv_path)  # No trade_date arg — extract from TIMESTAMP

        assert df["trade_date"].iloc[0] == date(2024, 1, 15)

    def test_null_critical_columns_dropped(self, sample_csv_path):
        """Verify rows with null close/open are dropped."""
        parser = BhavcopyParser()
        df = parser.parse(sample_csv_path, trade_date=date(2024, 1, 15))

        assert df["close"].notna().all()
        assert df["open"].notna().all()
        assert df["symbol"].notna().all()

    def test_source_file_recorded(self, sample_csv_path):
        parser = BhavcopyParser()
        df = parser.parse(sample_csv_path, trade_date=date(2024, 1, 15))

        assert df["source_file"].iloc[0] == "sample_bhavcopy.csv"
