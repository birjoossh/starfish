"""Unit tests for ingestion framework loaders."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ingestion.framework.loaders.base import BaseLoader


class TestBaseLoaderABC:
    def test_cannot_instantiate_base_loader(self):
        """BaseLoader is abstract."""
        with pytest.raises(TypeError):
            BaseLoader()  # type: ignore

    def test_concrete_subclass_must_implement_load(self):
        """Subclass missing load() raises TypeError on instantiation."""
        class Incomplete(BaseLoader):
            pass

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore

    def test_concrete_subclass_works(self, tmp_path):
        """A complete subclass can be instantiated and called."""
        class AlwaysZero(BaseLoader):
            def load(self, path: Path, trade_date: date) -> int:
                return 0

        loader = AlwaysZero()
        assert loader.load(tmp_path / "f.csv", date(2099, 1, 1)) == 0


from unittest.mock import MagicMock
from ingestion.framework.loaders.eod_price_loader import EodPriceLoader


class TestEodPriceLoader:
    def test_load_delegates_to_bhavcopy_chain(self, tmp_path):
        """EodPriceLoader.load() calls BhavcopyParser then BhavcopyLoader."""
        csv = tmp_path / "sec_bhavdata_full_15012099.csv"
        csv.write_text(
            "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,"
            "TOTTRDQTY,TOTTRDVAL,TIMESTAMP,TOTALTRADES,ISIN\n"
            "RELIANCE,EQ,2850.00,2875.50,2840.00,2865.30,2865.00,2845.00,"
            "8500000,24386.00,15-JAN-2099,125000,INE002A01018\n"
        )

        import pandas as pd
        mock_parser = MagicMock()
        mock_parser.parse.return_value = pd.DataFrame({"symbol": ["RELIANCE"]})
        mock_bloader = MagicMock()
        mock_bloader.load.return_value = {"rows_inserted": 1, "rows_total": 1,
                                           "rows_failed": 0, "status": "success"}

        loader = EodPriceLoader(parser=mock_parser, bhavcopy_loader=mock_bloader)
        result = loader.load(csv, date(2099, 1, 15))

        assert result == 1
        mock_parser.parse.assert_called_once_with(
            csv, trade_date=date(2099, 1, 15), source_file=csv.name
        )

    def test_load_returns_rows_inserted(self, tmp_path):
        """EodPriceLoader returns rows_inserted from BhavcopyLoader."""
        import pandas as pd
        mock_parser = MagicMock()
        mock_parser.parse.return_value = pd.DataFrame()
        mock_bloader = MagicMock()
        mock_bloader.load.return_value = {"rows_inserted": 37, "rows_total": 37,
                                           "rows_failed": 0, "status": "success"}

        loader = EodPriceLoader(parser=mock_parser, bhavcopy_loader=mock_bloader)
        result = loader.load(Path("/fake.csv"), date(2099, 1, 15))
        assert result == 37


from ingestion.framework.loaders.wk52_loader import Wk52Loader, Wk52ParseError


class TestWk52Loader:
    _SAMPLE_CSV_CONTENT = (
        "SYMBOL,SERIES,HIGH,HIGH_DATE,LOW,LOW_DATE\n"
        "RELIANCE,EQ,3215.00,29-DEC-2098,2180.10,05-APR-2098\n"
        "HDFCBANK,EQ,1850.00,10-NOV-2098,1200.50,12-JAN-2098\n"
    )

    def test_parse_returns_dataframe_with_required_columns(self, tmp_path):
        """Wk52Loader._parse() returns DataFrame with all required columns."""
        csv = tmp_path / "CM_52_wk_High_low_15012099.csv"
        csv.write_text(self._SAMPLE_CSV_CONTENT)

        loader = Wk52Loader(engine=MagicMock())
        df = loader._parse(csv, trade_date=date(2099, 1, 15))

        required = {"symbol", "trade_date", "wk52_high", "wk52_low",
                    "wk52_high_date", "wk52_low_date"}
        assert required.issubset(set(df.columns))
        assert len(df) == 2

    def test_parse_extracts_correct_values(self, tmp_path):
        """Wk52Loader._parse() correctly parses prices and dates."""
        csv = tmp_path / "CM_52_wk_High_low_15012099.csv"
        csv.write_text(self._SAMPLE_CSV_CONTENT)

        loader = Wk52Loader(engine=MagicMock())
        df = loader._parse(csv, trade_date=date(2099, 1, 15))
        row = df[df["symbol"] == "RELIANCE"].iloc[0]

        assert float(row["wk52_high"]) == 3215.00
        assert float(row["wk52_low"]) == 2180.10
        assert row["wk52_high_date"] == date(2098, 12, 29)
        assert row["wk52_low_date"] == date(2098, 4, 5)
        assert row["trade_date"] == date(2099, 1, 15)

    def test_parse_raises_on_missing_columns(self, tmp_path):
        """Wk52Loader._parse() raises Wk52ParseError on missing columns."""
        csv = tmp_path / "bad.csv"
        csv.write_text("SYMBOL,SERIES\nRELIANCE,EQ\n")

        with pytest.raises(Wk52ParseError, match="Missing columns"):
            Wk52Loader(engine=MagicMock())._parse(csv, trade_date=date(2099, 1, 15))

    def test_parse_raises_on_empty_file(self, tmp_path):
        """Wk52Loader._parse() raises Wk52ParseError on empty CSV."""
        csv = tmp_path / "empty.csv"
        csv.write_text("SYMBOL,SERIES,HIGH,HIGH_DATE,LOW,LOW_DATE\n")

        with pytest.raises(Wk52ParseError, match="empty"):
            Wk52Loader(engine=MagicMock())._parse(csv, trade_date=date(2099, 1, 15))


from ingestion.framework.loaders.constituents_loader import (
    ConstituentsLoader, ConstituentsParseError
)


class TestConstituentsLoader:
    _SAMPLE_CSV = (
        "Company Name,Industry,Symbol,Series,ISIN Code\n"
        "Reliance Industries Limited,ENERGY,RELIANCE,EQ,INE002A01018\n"
        "HDFC Bank Limited,FINANCIAL SERVICES,HDFCBANK,EQ,INE040A01034\n"
    )

    def test_parse_returns_dataframe(self, tmp_path):
        """ConstituentsLoader._parse() returns a DataFrame with symbol column."""
        csv = tmp_path / "ind_nifty50list.csv"
        csv.write_text(self._SAMPLE_CSV)

        loader = ConstituentsLoader(engine=MagicMock())
        df = loader._parse(csv)

        assert "symbol" in df.columns
        assert set(df["symbol"]) == {"RELIANCE", "HDFCBANK"}

    def test_parse_raises_on_missing_symbol_column(self, tmp_path):
        """ConstituentsLoader._parse() raises on CSV without a symbol column."""
        csv = tmp_path / "bad.csv"
        csv.write_text("Company Name,Industry\nFoo,Bar\n")

        with pytest.raises(ConstituentsParseError, match="symbol"):
            ConstituentsLoader(engine=MagicMock())._parse(csv)

    def test_parse_raises_on_empty_file(self, tmp_path):
        """ConstituentsLoader._parse() raises on empty CSV."""
        csv = tmp_path / "empty.csv"
        csv.write_text("Company Name,Industry,Symbol,Series,ISIN Code\n")

        with pytest.raises(ConstituentsParseError, match="empty"):
            ConstituentsLoader(engine=MagicMock())._parse(csv)
