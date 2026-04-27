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
