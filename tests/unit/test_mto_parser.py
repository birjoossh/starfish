"""Unit tests for ingestion.mto_parser."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ingestion.mto_parser import MTOParser, MTOParseError


HEADER = (
    "Record Type,Sr No,Name of Security,Type,Quantity Traded,"
    "Deliverable Quantity,% of Deliverable Quantity to Traded Quantity"
)


def _write_mto(tmp_path: Path, *, metadata: str, rows: list[str]) -> Path:
    """Write a synthetic MTO .DAT file and return its path."""
    p = tmp_path / "MTO_15012024.DAT"
    body = "\n".join([metadata, HEADER, *rows]) + "\n"
    p.write_text(body)
    return p


class TestMetadataLine:
    def test_parses_trade_date_from_metadata(self, tmp_path: Path):
        f = _write_mto(
            tmp_path,
            metadata="20240115,NSE,CASH,MTO",
            rows=["20,1,RELIANCE,EQ,1000,800,80.0"],
        )
        df = MTOParser(series_filter=["EQ"]).parse(f)
        assert df.loc[0, "trade_date"] == date(2024, 1, 15)

    def test_falls_back_to_filename_when_metadata_garbled(self, tmp_path: Path):
        f = _write_mto(
            tmp_path,
            metadata="GARBAGE_HEADER_LINE",
            rows=["20,1,TCS,EQ,500,400,80.0"],
        )
        df = MTOParser(series_filter=["EQ"]).parse(f)
        assert df.loc[0, "trade_date"] == date(2024, 1, 15)

    def test_caller_override_wins(self, tmp_path: Path):
        f = _write_mto(
            tmp_path,
            metadata="20240115,NSE,CASH,MTO",
            rows=["20,1,INFY,EQ,1200,900,75.0"],
        )
        df = MTOParser(series_filter=["EQ"]).parse(f, trade_date=date(2024, 2, 1))
        assert df.loc[0, "trade_date"] == date(2024, 2, 1)


class TestDataExtraction:
    def test_basic_row_mapping(self, tmp_path: Path):
        f = _write_mto(
            tmp_path,
            metadata="20240115,NSE,CASH,MTO",
            rows=[
                "20,1,RELIANCE,EQ,1000,800,80.0",
                "20,2,TCS,EQ,500,250,50.0",
            ],
        )
        df = MTOParser(series_filter=["EQ"]).parse(f)
        assert set(df.columns) == {"trade_date", "symbol", "delivery_qty", "delivery_pct"}
        assert df.loc[0, "symbol"] == "RELIANCE"
        assert int(df.loc[0, "delivery_qty"]) == 800
        assert float(df.loc[0, "delivery_pct"]) == pytest.approx(80.0)
        assert int(df.loc[1, "delivery_qty"]) == 250

    def test_strips_whitespace_in_symbol_and_series(self, tmp_path: Path):
        f = _write_mto(
            tmp_path,
            metadata="20240115,NSE,CASH,MTO",
            rows=["20,1,  HDFCBANK ,  EQ ,1000,900,90.0"],
        )
        df = MTOParser(series_filter=["EQ"]).parse(f)
        assert df.loc[0, "symbol"] == "HDFCBANK"


class TestSeriesFilter:
    def test_drops_non_matching_series(self, tmp_path: Path):
        f = _write_mto(
            tmp_path,
            metadata="20240115,NSE,CASH,MTO",
            rows=[
                "20,1,RELIANCE,EQ,1000,800,80.0",
                "20,2,SGB7YR,GB,500,500,100.0",   # bond, dropped
                "20,3,TCS,BE,200,200,100.0",      # BE kept
            ],
        )
        df = MTOParser(series_filter=["EQ", "BE"]).parse(f)
        assert set(df["symbol"]) == {"RELIANCE", "TCS"}

    def test_raises_when_filter_kills_all_rows(self, tmp_path: Path):
        f = _write_mto(
            tmp_path,
            metadata="20240115,NSE,CASH,MTO",
            rows=["20,1,SGB7YR,GB,500,500,100.0"],
        )
        with pytest.raises(MTOParseError, match="Series filter removed ALL"):
            MTOParser(series_filter=["EQ"]).parse(f)


class TestValidationFailures:
    def test_missing_file(self, tmp_path: Path):
        with pytest.raises(MTOParseError, match="not found"):
            MTOParser().parse(tmp_path / "does_not_exist.DAT")

    def test_truncated_file(self, tmp_path: Path):
        p = tmp_path / "MTO_15012024.DAT"
        p.write_text("")
        with pytest.raises(MTOParseError, match="truncated"):
            MTOParser().parse(p)

    def test_wrong_header(self, tmp_path: Path):
        p = tmp_path / "MTO_15012024.DAT"
        p.write_text(
            "20240115,NSE,CASH,MTO\n"
            "Record Type,Sr No,Symbol,Type,Volume,Delivery,Pct\n"   # renamed cols
            "20,1,RELIANCE,EQ,1000,800,80.0\n"
        )
        with pytest.raises(MTOParseError, match="header validation FAILED"):
            MTOParser().parse(p)
