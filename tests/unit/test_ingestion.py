"""Tests for ingestion loader and idempotency."""

from __future__ import annotations

from datetime import date, timedelta
import time

import pandas as pd
import pytest

from ingestion.bhavcopy_loader import BhavcopyLoader
from ingestion.bhavcopy_parser import BhavcopyParser
from config.database import get_engine
from sqlalchemy import text

# Use far-future dates to avoid conflicts with real data
_TEST_BASE_DATE = date(2099, 1, 1)


def _get_test_date(offset: int = 0) -> date:
    """Return a unique test date that won't collide with real data."""
    return _TEST_BASE_DATE + timedelta(days=offset)


def _cleanup_test_data(engine):
    """Remove test data from fact_eod_price."""
    with engine.connect() as conn:
        conn.execute(text(
            "DELETE FROM fact_eod_price WHERE trade_date >= :d"
        ), {"d": _TEST_BASE_DATE})
        conn.execute(text(
            "DELETE FROM ingestion_log WHERE source_file LIKE 'test_%'"
        ))
        conn.commit()


class TestBhavcopyLoader:
    @pytest.fixture(autouse=True)
    def _cleanup(self):
        engine = get_engine()
        _cleanup_test_data(engine)
        yield
        _cleanup_test_data(engine)

    def test_load_inserts_rows(self, tmp_path):
        csv = tmp_path / "test_bhav.csv"
        csv.write_text(
            "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,"
            "TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN\n"
            "RELIANCE,EQ,2850.00,2875.50,2840.00,2865.30,2865.00,2845.00,"
            "8500000,24386.00,01-JAN-2099,125000,INE002A01018"
        )

        parser = BhavcopyParser()
        test_date = _get_test_date(0)
        df = parser.parse(csv, trade_date=test_date)
        loader = BhavcopyLoader()
        stats = loader.load(df, source_file="test_load.csv")

        assert stats["status"] == "success"
        assert stats["rows_total"] == 1
        assert stats["rows_inserted"] == 1

    def test_idempotency(self, tmp_path):
        """Running load twice on same date should not create duplicates."""
        csv = tmp_path / "test_bhav_idem.csv"
        csv.write_text(
            "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,"
            "TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN\n"
            "RELIANCE,EQ,2850.00,2875.50,2840.00,2865.30,2865.00,2845.00,"
            "8500000,24386.00,02-JAN-2099,125000,INE002A01018\n"
            "HDFCBANK,EQ,1650.00,1665.00,1640.00,1658.75,1658.00,1645.50,"
            "6200000,10284.25,02-JAN-2099,95000,INE040A01034"
        )

        parser = BhavcopyParser()
        test_date = _get_test_date(1)
        df = parser.parse(csv, trade_date=test_date)
        loader = BhavcopyLoader()

        stats1 = loader.load(df, source_file="test_idem.csv")
        assert stats1["rows_inserted"] == 2

        stats2 = loader.load(df, source_file="test_idem.csv")
        assert stats2["rows_inserted"] == 0
        assert stats2["rows_failed"] == 2

    def test_empty_dataframe(self):
        loader = BhavcopyLoader()
        stats = loader.load(pd.DataFrame(), source_file="test.csv")

        assert stats["status"] == "success"
        assert stats["rows_total"] == 0
