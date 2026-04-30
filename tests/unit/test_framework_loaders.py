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

    def test_parse_handles_space_and_underscore_header_variants(self, tmp_path):
        """Wk52Loader._parse() handles ``ADJUSTED 52_WEEK_HIGH`` (space variant).

        Regression for production failure on 2025-05-02:
        the file headers were ``ADJUSTED 52_WEEK_HIGH``, ``ADJUSTED 52_WEEK_LOW``
        (mixed space + underscore) instead of the all-underscore variant.
        Header normalization should collapse both forms identically.
        """
        csv = tmp_path / "CM_52_wk_High_low_02052025.csv"
        # Note: column headers use SPACES inside "ADJUSTED 52_WEEK_HIGH"
        csv.write_text(
            "SYMBOL,SERIES,ADJUSTED 52_WEEK_HIGH,HIGH_DATE,ADJUSTED 52_WEEK_LOW,LOW_DATE\n"
            "RELIANCE,EQ,3215.00,29-DEC-2024,2180.10,05-APR-2024\n"
            "HDFCBANK,EQ,1850.00,10-NOV-2024,1200.50,12-JAN-2024\n"
        )

        loader = Wk52Loader(engine=MagicMock())
        df = loader._parse(csv, trade_date=date(2025, 5, 2))

        assert set(df["symbol"]) == {"RELIANCE", "HDFCBANK"}
        rel = df[df["symbol"] == "RELIANCE"].iloc[0]
        assert float(rel["wk52_high"]) == 3215.00
        assert float(rel["wk52_low"]) == 2180.10
        assert rel["wk52_high_date"] == date(2024, 12, 29)

    def test_parse_handles_real_nse_format_with_banner_rows(self, tmp_path):
        """Wk52Loader._parse() handles the real NSE file with banner rows.

        NSE's actual ``CM_52_wk_High_low_DDMMYYYY.csv`` has:
          1. A disclaimer line.
          2. An "Effective for DD-Mon-YYYY" line.
          3. The real header: SYMBOL, SERIES, Adjusted_52_Week_High,
             52_Week_High_Date, Adjusted_52_Week_Low, 52_Week_Low_DT.
        Values may include leading whitespace and ``-`` for missing data.
        """
        csv = tmp_path / "CM_52_wk_High_low_27042026.csv"
        csv.write_text(
            '"Disclaimer - The Data provided in the adjusted 52 week high..."\n'
            '"Effective for 27-Apr-2026"\n'
            '"SYMBOL","SERIES","Adjusted_52_Week_High","52_Week_High_Date",'
            '"Adjusted_52_Week_Low","52_Week_Low_DT"\n'
            '"RELIANCE","EQ","   3215.00","29-DEC-2025","   2180.10","05-APR-2025"\n'
            '"HDFCBANK","EQ","   1850.00","10-NOV-2025","   1200.50","12-JAN-2025"\n'
            '"DELISTED$","EQ","-","-","-","-"\n'
        )

        loader = Wk52Loader(engine=MagicMock())
        df = loader._parse(csv, trade_date=date(2026, 4, 27))

        # Two valid rows; the "-" row is dropped
        assert set(df["symbol"]) == {"RELIANCE", "HDFCBANK"}
        rel = df[df["symbol"] == "RELIANCE"].iloc[0]
        assert float(rel["wk52_high"]) == 3215.00
        assert rel["wk52_high_date"] == date(2025, 12, 29)
        assert rel["wk52_low_date"] == date(2025, 4, 5)


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


from ingestion.framework.loaders.dim_stock_loader import (
    DimStockLoader, DimStockParseError,
)


class TestDimStockLoader:
    _SAMPLE_CSV = (
        "FinInstrmId,TckrSymb,SctySrs,FinInstrmNm,ISIN,ParVal,ListgDt\n"
        # Multiple series per symbol — only EQ should survive the filter
        "2885,RELIANCE,EQ,RELIANCE INDUSTRIES LTD,INE002A01018,1000,502070400\n"
        "11139,RELIANCE,AF,RELIANCE INDUSTRIES LTD,INE002A01018,1000,1248566400\n"
        "1333,HDFCBANK,EQ,HDFC BANK LTD,INE040A01034,100,500256000\n"
        # Test row — should be filtered (and even if it survived, missing ListgDt
        # would drop it)
        "14747,011NSETEST,EQ,011NSETEST,DUMMYSAN005,1000,0\n"
    )

    def test_parse_filters_to_eq_series_and_dedupes(self, tmp_path):
        """DimStockLoader._parse() keeps only one EQ row per symbol."""
        csv = tmp_path / "NSE_CM_security_27042026.csv"
        csv.write_text(self._SAMPLE_CSV)

        loader = DimStockLoader(engine=MagicMock())
        df = loader._parse(csv)

        # Two valid EQ symbols (011NSETEST dropped because ListgDt=0 → None)
        assert set(df["symbol"]) == {"RELIANCE", "HDFCBANK"}
        assert len(df) == 2

    def test_parse_extracts_listing_date_from_unix_timestamp(self, tmp_path):
        """DimStockLoader._parse() converts ListgDt (epoch seconds) to date."""
        csv = tmp_path / "NSE_CM_security_27042026.csv"
        csv.write_text(self._SAMPLE_CSV)

        loader = DimStockLoader(engine=MagicMock())
        df = loader._parse(csv)
        rel = df[df["symbol"] == "RELIANCE"].iloc[0]

        # 502070400 epoch seconds = 1985-11-29 (UTC)
        assert rel["listing_date"] == date(1985, 11, 29)
        assert rel["isin"] == "INE002A01018"
        assert rel["company_name"] == "RELIANCE INDUSTRIES LTD"
        assert float(rel["face_value"]) == 1000.0

    def test_parse_raises_on_missing_columns(self, tmp_path):
        """DimStockLoader._parse() raises on a CSV without required columns."""
        csv = tmp_path / "bad.csv"
        csv.write_text("FOO,BAR\n1,2\n")

        with pytest.raises(DimStockParseError, match="Missing columns"):
            DimStockLoader(engine=MagicMock())._parse(csv)

    def test_parse_raises_on_no_eq_rows(self, tmp_path):
        """DimStockLoader._parse() raises when the file has no EQ-series rows."""
        csv = tmp_path / "no_eq.csv"
        csv.write_text(
            "FinInstrmId,TckrSymb,SctySrs,FinInstrmNm,ISIN,ParVal,ListgDt\n"
            "1,FOO,BE,FOO LTD,INE000A00000,10,1000000000\n"
        )

        with pytest.raises(DimStockParseError, match="No EQ-series rows"):
            DimStockLoader(engine=MagicMock())._parse(csv)

    def test_parse_handles_normalized_header_variants(self, tmp_path):
        """Header normalization handles spaces, underscores, casing."""
        csv = tmp_path / "variant_headers.csv"
        csv.write_text(
            "tckr_symb,scty srs,FinInstrmNm,isin,parval,listgdt\n"
            "RELIANCE,EQ,RELIANCE INDUSTRIES LTD,INE002A01018,1000,502070400\n"
        )

        loader = DimStockLoader(engine=MagicMock())
        df = loader._parse(csv)
        assert list(df["symbol"]) == ["RELIANCE"]

    def test_listing_date_falls_back_to_filename_date(self, tmp_path):
        """Rows with missing/zero ListgDt fall back to the date in the filename."""
        # Filename encodes 02-01-2026 (DD-MM-YYYY)
        csv = tmp_path / "NSE_CM_security_02012026.csv"
        csv.write_text(
            "FinInstrmId,TckrSymb,SctySrs,FinInstrmNm,ISIN,ParVal,ListgDt\n"
            # Valid ListgDt → keeps its real listing date
            "1,RELIANCE,EQ,RELIANCE LTD,INE002A01018,1000,502070400\n"
            # ListgDt=0 → previously dropped, now uses filename date
            "2,NEWCO,EQ,NEW CO LTD,INE999A99999,10,0\n"
            # ListgDt missing entirely → also uses filename date
            "3,FRESHCO,EQ,FRESH CO LTD,INE888A88888,5,\n"
        )

        loader = DimStockLoader(engine=MagicMock())
        df = loader._parse(csv, source_filename=csv.name)

        assert set(df["symbol"]) == {"RELIANCE", "NEWCO", "FRESHCO"}
        assert df.set_index("symbol").loc["RELIANCE", "listing_date"] == date(1985, 11, 29)
        assert df.set_index("symbol").loc["NEWCO", "listing_date"] == date(2026, 1, 2)
        assert df.set_index("symbol").loc["FRESHCO", "listing_date"] == date(2026, 1, 2)

    def test_no_filename_fallback_when_filename_unparseable(self, tmp_path):
        """Rows with missing ListgDt are still dropped if filename has no date."""
        csv = tmp_path / "garbage_filename.csv"
        csv.write_text(
            "FinInstrmId,TckrSymb,SctySrs,FinInstrmNm,ISIN,ParVal,ListgDt\n"
            "1,RELIANCE,EQ,RELIANCE LTD,INE002A01018,1000,502070400\n"
            "2,NEWCO,EQ,NEW CO LTD,INE999A99999,10,0\n"
        )

        loader = DimStockLoader(engine=MagicMock())
        df = loader._parse(csv, source_filename=csv.name)

        # NEWCO dropped because ListgDt=0 and no filename fallback
        assert set(df["symbol"]) == {"RELIANCE"}

    def test_date_from_filename_helper(self):
        """_date_from_filename parses NSE_CM_security_DDMMYYYY.csv correctly."""
        from ingestion.framework.loaders.dim_stock_loader import _date_from_filename

        assert _date_from_filename("NSE_CM_security_02012026.csv") == date(2026, 1, 2)
        assert _date_from_filename("NSE_CM_security_31122099.csv") == date(2099, 12, 31)
        # case-insensitive
        assert _date_from_filename("nse_cm_security_15012099.csv") == date(2099, 1, 15)
        # Invalid date in filename
        assert _date_from_filename("NSE_CM_security_99999999.csv") is None
        # Non-matching filename
        assert _date_from_filename("ind_nifty50list.csv") is None
        assert _date_from_filename(None) is None
        assert _date_from_filename("") is None

    def test_dropped_rows_are_written_to_bad_records_writer(self, tmp_path):
        """DimStockLoader hands dropped rows to its BadRecordsWriter."""
        from ingestion.framework.bad_records import BadRecordsWriter

        csv = tmp_path / "NSE_CM_security_27042026.csv"
        csv.write_text(
            "FinInstrmId,TckrSymb,SctySrs,FinInstrmNm,ISIN,ParVal,ListgDt\n"
            # Valid
            "1,RELIANCE,EQ,RELIANCE LTD,INE002A01018,1000,502070400\n"
            # Missing ISIN → dropped (missing required field); filename fallback
            # cannot rescue an ISIN, only listing_date.
            "2,BADTICKER,EQ,BAD LTD,,100,502070400\n"
            # Duplicate of RELIANCE → dedupe drop
            "3,RELIANCE,EQ,RELIANCE LTD,INE002A01018,1000,502070400\n"
        )

        log_dir = tmp_path / "logs"
        writer = BadRecordsWriter(source="dim-stock", log_dir=log_dir)
        loader = DimStockLoader(engine=MagicMock(), bad_records_writer=writer)
        df = loader._parse(csv, source_filename=csv.name)

        assert list(df["symbol"]) == ["RELIANCE"]
        bad_file = log_dir / "NSE_CM_security_27042026.csv"
        assert bad_file.exists()
        content = bad_file.read_text()
        # Both the missing-field row and the duplicate row recorded
        assert "BADTICKER" in content
        assert "missing required field" in content
        assert "duplicate symbol" in content


from ingestion.framework.loaders.reconstitution_loader import ReconstitutionLoader
from ingestion.framework.loaders.intraday_loader import IntradayLoader
from ingestion.framework.loaders.corporate_actions_loader import CorporateActionsFrameworkLoader
from ingestion.framework.loaders.event_calendar_loader import EventCalendarLoader
from ingestion.framework.loaders.announcements_loader import AnnouncementsLoader


class TestPlaceholderLoaders:
    def test_intraday_loader_raises_not_implemented(self, tmp_path):
        """IntradayLoader.load() raises NotImplementedError."""
        loader = IntradayLoader()
        with pytest.raises(NotImplementedError, match="vendor"):
            loader.load(tmp_path / "fake.csv", date(2099, 1, 15))

    def test_reconstitution_loader_raises_fetch_error_on_missing_file(self, tmp_path):
        """ReconstitutionLoader.load() raises when file doesn't exist."""
        loader = ReconstitutionLoader(engine=MagicMock())
        with pytest.raises(FileNotFoundError):
            loader.load(tmp_path / "nonexistent.csv", date(2099, 1, 15))


class TestCorporateActionsWrapper:
    def test_delegates_to_existing_parser_and_loader(self, tmp_path):
        """CorporateActionsFrameworkLoader delegates to existing chain."""
        import pandas as pd
        mock_parser = MagicMock()
        mock_parser.parse.return_value = pd.DataFrame()
        mock_loader = MagicMock()
        mock_loader.load.return_value = 5

        loader = CorporateActionsFrameworkLoader(
            parser=mock_parser, ca_loader=mock_loader
        )
        result = loader.load(tmp_path / "ca.csv", date(2099, 1, 15))

        assert result == 5
        mock_parser.parse.assert_called_once()


class TestEventCalendarWrapper:
    def test_delegates_to_existing_scraper_chain(self, tmp_path):
        """EventCalendarLoader delegates to existing ingestor+loader chain."""
        import pandas as pd
        # Real JSON file — wrapper now normalizes JSON before ingest.
        ec = tmp_path / "ec.json"
        ec.write_text("[]")
        mock_ingestor = MagicMock()
        mock_ingestor.ingest.return_value = pd.DataFrame()
        mock_loader = MagicMock()
        mock_loader.load.return_value = 3

        loader = EventCalendarLoader(ingestor=mock_ingestor, events_loader=mock_loader)
        result = loader.load(ec, date(2099, 1, 15))

        assert result == 3
        mock_ingestor.ingest.assert_called_once()
        # The normalized temp-CSV path is what the ingestor actually sees.
        passed = mock_ingestor.ingest.call_args[0][0]
        assert passed.suffix == ".csv"

    def test_csv_path_skips_json_normalization(self, tmp_path):
        """A .csv source path is passed straight through, no temp file."""
        import pandas as pd
        csv = tmp_path / "ec.csv"
        csv.write_text("symbol,purpose,date\nRELIANCE,DIVIDEND,15-JAN-2099\n")
        mock_ingestor = MagicMock()
        mock_ingestor.ingest.return_value = pd.DataFrame()
        mock_loader = MagicMock()
        mock_loader.load.return_value = 0

        loader = EventCalendarLoader(ingestor=mock_ingestor, events_loader=mock_loader)
        loader.load(csv, date(2099, 1, 15))

        passed = mock_ingestor.ingest.call_args[0][0]
        assert passed == csv

    def test_normalizes_real_nse_event_calendar_json(self, tmp_path):
        """Real NSE event-calendar JSON is classified end-to-end."""
        import json
        ec = tmp_path / "event_calendar_29042026.json"
        ec.write_text(json.dumps([
            {
                "symbol": "ADANIPOWER",
                "company": "Adani Power Limited",
                "purpose": "Financial Results",
                "bm_desc": "To consider and approve the financial results "
                           "for the period ended March 31, 2026",
                "date": "29-Apr-2026",
            },
            {
                "symbol": "BAJFINANCE",
                "company": "Bajaj Finance Limited",
                "purpose": "Financial Results/Dividend",
                "bm_desc": "To consider and approve the financial results "
                           "for the period ended March 31, 2026 and dividend",
                "date": "29-Apr-2026",
            },
        ]))

        mock_loader = MagicMock()
        mock_loader.load.side_effect = lambda df: len(df)

        # Use the REAL CorporateEventsIngestor — exercises the full
        # JSON-→-temp-CSV-→-column-detection-→-classification chain.
        # known_symbols= lets us skip the real dim_stock query.
        loader = EventCalendarLoader(
            events_loader=mock_loader,
            known_symbols={"ADANIPOWER", "BAJFINANCE"},
        )
        result = loader.load(ec, date(2026, 4, 27))

        assert result == 2
        df = mock_loader.load.call_args[0][0]
        assert set(df["symbol"]) == {"ADANIPOWER", "BAJFINANCE"}
        # Both rows classified as RESULTS-bearing events
        assert "RESULTS" in set(df["event_type"]) or "DIVIDEND" in set(df["event_type"])


class TestAnnouncementsWrapper:
    def test_delegates_to_existing_scraper_chain(self, tmp_path):
        """AnnouncementsLoader delegates to existing ingestor+loader chain."""
        import pandas as pd
        ann = tmp_path / "ann.json"
        ann.write_text("[]")
        mock_ingestor = MagicMock()
        mock_ingestor.ingest.return_value = pd.DataFrame()
        mock_loader = MagicMock()
        mock_loader.load.return_value = 7

        loader = AnnouncementsLoader(ingestor=mock_ingestor, events_loader=mock_loader)
        result = loader.load(ann, date(2099, 1, 15))
        assert result == 7
        passed = mock_ingestor.ingest.call_args[0][0]
        assert passed.suffix == ".csv"

    def test_normalizes_real_nse_announcements_json(self, tmp_path):
        """Real NSE corporate-announcements JSON is classified end-to-end.

        Notably ``an_dt`` carries a trailing time component
        (``"28-Apr-2026 21:02:06"``) that the legacy ingestor's date parser
        cannot handle directly. The adapter must strip the time portion.
        """
        import json
        ann = tmp_path / "announcements_28042026.json"
        ann.write_text(json.dumps([
            {
                "symbol": "AWL",
                "desc": "Investor Presentation",
                "an_dt": "28-Apr-2026 21:02:06",
                "sort_date": "2026-04-28 21:02:06",
                "attchmntText": "AWL Agri Business Limited has informed "
                                "the Exchange about Investor Presentation",
            },
            {
                "symbol": "BAJFINANCE",
                "desc": "Dividend",
                "an_dt": "28-Apr-2026 21:01:42",
                "sort_date": "2026-04-28 21:01:42",
                "attchmntText": "Interim dividend of Rs 12.50 per share",
            },
        ]))

        mock_loader = MagicMock()
        mock_loader.load.side_effect = lambda df: len(df)

        loader = AnnouncementsLoader(
            events_loader=mock_loader,
            known_symbols={"AWL", "BAJFINANCE"},
        )
        result = loader.load(ann, date(2026, 4, 28))

        assert result == 2
        df = mock_loader.load.call_args[0][0]
        assert set(df["symbol"]) == {"AWL", "BAJFINANCE"}
        # The dividend announcement's date must have parsed (time stripped)
        bajaj = df[df["symbol"] == "BAJFINANCE"].iloc[0]
        assert bajaj["event_date"] is not None
        assert bajaj["event_type"] == "DIVIDEND"


class TestEventJsonAdapter:
    def test_event_calendar_json_to_rows_basic(self, tmp_path):
        """Adapter maps NSE event-calendar JSON fields to ingestor columns."""
        import json
        from ingestion.framework.loaders._event_json_adapter import (
            event_calendar_json_to_rows,
        )
        f = tmp_path / "ec.json"
        f.write_text(json.dumps([
            {"symbol": "RELIANCE", "purpose": "Dividend",
             "bm_desc": "Interim dividend", "date": "15-Jan-2099"},
        ]))
        rows = event_calendar_json_to_rows(f)
        assert rows == [{
            "symbol":  "RELIANCE",
            "purpose": "Dividend — Interim dividend",
            "date":    "15-Jan-2099",
        }]

    def test_announcements_json_strips_time_from_date(self, tmp_path):
        """``an_dt`` time component is stripped — only date survives."""
        import json
        from ingestion.framework.loaders._event_json_adapter import (
            announcements_json_to_rows,
        )
        f = tmp_path / "ann.json"
        f.write_text(json.dumps([
            {"symbol": "X", "desc": "Bonus 1:2",
             "an_dt": "15-Jan-2099 10:30:00",
             "attchmntText": "Bonus issue 1:2"},
        ]))
        rows = announcements_json_to_rows(f)
        assert rows[0]["date"] == "15-Jan-2099"
        assert rows[0]["symbol"] == "X"

    def test_skips_rows_without_symbol(self, tmp_path):
        """Records lacking a symbol are dropped — they cannot be classified."""
        import json
        from ingestion.framework.loaders._event_json_adapter import (
            event_calendar_json_to_rows,
        )
        f = tmp_path / "ec.json"
        f.write_text(json.dumps([
            {"symbol": "", "purpose": "x", "date": "1-Jan-2099"},
            {"purpose": "y", "date": "1-Jan-2099"},
            {"symbol": "OK", "purpose": "z", "date": "1-Jan-2099"},
        ]))
        rows = event_calendar_json_to_rows(f)
        assert [r["symbol"] for r in rows] == ["OK"]

    def test_handles_wrapped_data_envelope(self, tmp_path):
        """Tolerates ``{"data": [...]}`` envelope as well as bare arrays."""
        import json
        from ingestion.framework.loaders._event_json_adapter import (
            event_calendar_json_to_rows,
        )
        f = tmp_path / "ec.json"
        f.write_text(json.dumps({"data": [
            {"symbol": "FOO", "purpose": "X", "date": "1-Jan-2099"},
        ]}))
        rows = event_calendar_json_to_rows(f)
        assert len(rows) == 1 and rows[0]["symbol"] == "FOO"

    def test_json_to_temp_csv_writes_three_columns(self, tmp_path):
        """End-to-end conversion produces a CSV the ingestor can detect."""
        import json
        import pandas as pd
        from ingestion.framework.loaders._event_json_adapter import json_to_temp_csv
        f = tmp_path / "ec.json"
        f.write_text(json.dumps([
            {"symbol": "RELIANCE", "purpose": "Dividend", "date": "15-Jan-2099"},
        ]))
        out = json_to_temp_csv(f, kind="event_calendar", dest_dir=tmp_path / "out")
        assert out.exists() and out.suffix == ".csv"
        df = pd.read_csv(out)
        assert list(df.columns) == ["symbol", "purpose", "date"]
        assert df.iloc[0]["symbol"] == "RELIANCE"

    def test_unknown_kind_raises(self, tmp_path):
        """Adapter rejects unknown ``kind`` values explicitly."""
        from ingestion.framework.loaders._event_json_adapter import json_to_temp_csv
        f = tmp_path / "ec.json"
        f.write_text("[]")
        with pytest.raises(ValueError, match="Unknown kind"):
            json_to_temp_csv(f, kind="bogus", dest_dir=tmp_path / "out")


class TestJsonBadRecordsWriter:
    def test_writes_records_as_json_array(self, tmp_path):
        """Writes the records verbatim plus a ``_drop_reason`` stamp."""
        from ingestion.framework.json_bad_records import JsonBadRecordsWriter
        import json as _json

        writer = JsonBadRecordsWriter(source="event-calendar", log_dir=tmp_path)
        out = writer.write(
            [{"symbol": "INDUSINVIT", "purpose": "Dividend"}],
            original_filename="event_calendar_20260427.json",
            reason="symbol not in dim_stock",
        )

        assert out is not None and out.exists()
        payload = _json.loads(out.read_text())
        assert isinstance(payload, list) and len(payload) == 1
        assert payload[0]["symbol"] == "INDUSINVIT"
        assert payload[0]["_drop_reason"] == "symbol not in dim_stock"

    def test_returns_none_for_empty_input(self, tmp_path):
        """Empty input is a no-op — no file created."""
        from ingestion.framework.json_bad_records import JsonBadRecordsWriter
        writer = JsonBadRecordsWriter(source="x", log_dir=tmp_path)
        assert writer.write([], original_filename="f.json", reason="—") is None
        assert list(tmp_path.iterdir()) == []

    def test_appends_on_repeat_write(self, tmp_path):
        """Second write to the same filename appends to the existing JSON array."""
        from ingestion.framework.json_bad_records import JsonBadRecordsWriter
        import json as _json

        writer = JsonBadRecordsWriter(source="x", log_dir=tmp_path)
        writer.write([{"symbol": "A"}], original_filename="f.json", reason="r1")
        writer.write([{"symbol": "B"}], original_filename="f.json", reason="r2")

        payload = _json.loads((tmp_path / "f.json").read_text())
        assert [r["symbol"] for r in payload] == ["A", "B"]
        assert [r["_drop_reason"] for r in payload] == ["r1", "r2"]

    def test_forces_json_extension(self, tmp_path):
        """Output filename always ends in .json regardless of input ext."""
        from ingestion.framework.json_bad_records import JsonBadRecordsWriter
        writer = JsonBadRecordsWriter(source="x", log_dir=tmp_path)
        out = writer.write([{"a": 1}], original_filename="weird.csv", reason="r")
        assert out.name == "weird.json"

    def test_does_not_mutate_caller_records(self, tmp_path):
        """Caller's dicts are not mutated by the ``_drop_reason`` stamp."""
        from ingestion.framework.json_bad_records import JsonBadRecordsWriter
        writer = JsonBadRecordsWriter(source="x", log_dir=tmp_path)
        rec = {"symbol": "A"}
        writer.write([rec], original_filename="f.json", reason="r")
        assert rec == {"symbol": "A"}  # untouched


class TestSymbolValidator:
    """Cover the pre-load FK-resilience plumbing directly."""

    def test_filter_drops_unknown_and_writes_originals(self, tmp_path):
        """Unknown-symbol rows are dropped and original JSON records written."""
        import json as _json
        import pandas as pd
        from ingestion.framework.json_bad_records import JsonBadRecordsWriter
        from ingestion.framework.loaders._symbol_validator import (
            filter_unknown_symbols,
        )

        # The ORIGINAL NSE JSON file (pre-classification)
        src = tmp_path / "event_calendar_20260427.json"
        src.write_text(_json.dumps([
            {"symbol": "RELIANCE", "purpose": "Results", "date": "29-Apr-2026"},
            {"symbol": "INDUSINVIT", "purpose": "Distribution", "date": "29-Apr-2026"},
            {"symbol": "EMBASSY", "purpose": "Distribution", "date": "29-Apr-2026"},
        ]))

        # The classified DataFrame (what the legacy ingestor produces)
        df = pd.DataFrame([
            {"symbol": "RELIANCE", "event_type": "RESULTS"},
            {"symbol": "INDUSINVIT", "event_type": "OTHER"},
            {"symbol": "EMBASSY", "event_type": "OTHER"},
        ])

        writer = JsonBadRecordsWriter(source="event-calendar", log_dir=tmp_path / "logs")
        out = filter_unknown_symbols(
            df,
            known_symbols={"RELIANCE"},
            json_source_path=src,
            bad_records_writer=writer,
        )

        # Only RELIANCE survives
        assert list(out["symbol"]) == ["RELIANCE"]

        # Bad records file contains the ORIGINAL JSON shape (purpose, date)
        bad_file = tmp_path / "logs" / "event_calendar_20260427.json"
        payload = _json.loads(bad_file.read_text())
        bad_symbols = {r["symbol"] for r in payload}
        assert bad_symbols == {"INDUSINVIT", "EMBASSY"}
        # Each record retains its original NSE fields (not the classified ones)
        first = next(r for r in payload if r["symbol"] == "INDUSINVIT")
        assert first["purpose"] == "Distribution"
        assert first["date"] == "29-Apr-2026"
        assert "_drop_reason" in first

    def test_filter_no_op_when_all_symbols_known(self, tmp_path):
        """No bad-records file when every row's symbol is in dim_stock."""
        import pandas as pd
        from ingestion.framework.json_bad_records import JsonBadRecordsWriter
        from ingestion.framework.loaders._symbol_validator import (
            filter_unknown_symbols,
        )

        df = pd.DataFrame([{"symbol": "RELIANCE"}, {"symbol": "HDFCBANK"}])
        writer = JsonBadRecordsWriter(source="x", log_dir=tmp_path / "logs")
        out = filter_unknown_symbols(
            df, known_symbols={"RELIANCE", "HDFCBANK"},
            json_source_path=None, bad_records_writer=writer,
        )
        assert list(out["symbol"]) == ["RELIANCE", "HDFCBANK"]
        # No log dir created (no writes happened)
        assert not (tmp_path / "logs").exists() or \
               list((tmp_path / "logs").iterdir()) == []

    def test_filter_handles_missing_writer(self, tmp_path):
        """Without a writer, rows still drop silently — no crash."""
        import pandas as pd
        from ingestion.framework.loaders._symbol_validator import (
            filter_unknown_symbols,
        )
        df = pd.DataFrame([{"symbol": "GOOD"}, {"symbol": "BAD"}])
        out = filter_unknown_symbols(
            df, known_symbols={"GOOD"},
            json_source_path=None, bad_records_writer=None,
        )
        assert list(out["symbol"]) == ["GOOD"]

    def test_filter_passes_through_when_no_symbol_column(self, tmp_path):
        """A DataFrame without ``symbol`` is left untouched."""
        import pandas as pd
        from ingestion.framework.loaders._symbol_validator import (
            filter_unknown_symbols,
        )
        df = pd.DataFrame([{"x": 1}, {"x": 2}])
        out = filter_unknown_symbols(
            df, known_symbols=set(),
            json_source_path=None, bad_records_writer=None,
        )
        assert len(out) == 2

    def test_fetch_known_symbols_uppercases_and_strips(self):
        """``fetch_known_symbols`` normalizes symbols (upper, stripped)."""
        from ingestion.framework.loaders._symbol_validator import fetch_known_symbols

        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        # SQLAlchemy result rows behave like tuples — index 0 is the symbol col
        mock_conn.execute.return_value = iter([
            ("reliance",), (" hdfcbank ",), ("INFY",),
        ])

        result = fetch_known_symbols(mock_engine)
        assert result == {"RELIANCE", "HDFCBANK", "INFY"}


class TestEventCalendarLoaderFkResilience:
    """End-to-end: unknown symbols are dropped before reaching the legacy loader."""

    def test_indusinvit_dropped_and_recorded(self, tmp_path):
        """Real INDUSINVIT-style scenario — non-EQ symbol is filtered out."""
        import json as _json
        from ingestion.framework.json_bad_records import JsonBadRecordsWriter

        src = tmp_path / "event_calendar_29042026.json"
        src.write_text(_json.dumps([
            {"symbol": "RELIANCE", "company": "Reliance Industries Limited",
             "purpose": "Financial Results", "bm_desc": "To consider results",
             "date": "29-Apr-2026"},
            {"symbol": "INDUSINVIT", "company": "India Grid Trust InvIT",
             "purpose": "Distribution", "bm_desc": "InvIT distribution",
             "date": "29-Apr-2026"},
        ]))

        captured = {}
        def _capture(df):
            captured["df"] = df.copy()
            return len(df)
        mock_loader = MagicMock()
        mock_loader.load.side_effect = _capture

        writer = JsonBadRecordsWriter(source="event-calendar", log_dir=tmp_path / "logs")
        loader = EventCalendarLoader(
            events_loader=mock_loader,
            bad_records_writer=writer,
            known_symbols={"RELIANCE"},  # InvIT not present
        )
        result = loader.load(src, date(2026, 4, 27))

        # Only RELIANCE made it to the DB-writing loader
        assert result == 1
        assert list(captured["df"]["symbol"]) == ["RELIANCE"]

        # INDUSINVIT shows up in the JSON bad-records file with its original shape
        bad = _json.loads((tmp_path / "logs" / "event_calendar_29042026.json").read_text())
        assert len(bad) == 1
        assert bad[0]["symbol"] == "INDUSINVIT"
        assert bad[0]["company"] == "India Grid Trust InvIT"  # original field preserved
        assert bad[0]["bm_desc"] == "InvIT distribution"
        assert "FK violation" in bad[0]["_drop_reason"] or \
               "dim_stock" in bad[0]["_drop_reason"]

    def test_no_filtering_when_all_symbols_known(self, tmp_path):
        """When every symbol is in dim_stock, no bad-records file is written."""
        import json as _json
        from ingestion.framework.json_bad_records import JsonBadRecordsWriter

        src = tmp_path / "event_calendar_29042026.json"
        src.write_text(_json.dumps([
            {"symbol": "RELIANCE", "purpose": "Results", "date": "29-Apr-2026"},
        ]))
        mock_loader = MagicMock()
        mock_loader.load.side_effect = lambda df: len(df)

        writer = JsonBadRecordsWriter(source="event-calendar", log_dir=tmp_path / "logs")
        loader = EventCalendarLoader(
            events_loader=mock_loader,
            bad_records_writer=writer,
            known_symbols={"RELIANCE"},
        )
        result = loader.load(src, date(2026, 4, 27))

        assert result == 1
        # No bad records file
        assert not (tmp_path / "logs" / "event_calendar_29042026.json").exists()


class TestAnnouncementsLoaderFkResilience:
    def test_unknown_symbol_dropped_and_recorded(self, tmp_path):
        """Same FK-resilience contract for the announcements loader."""
        import json as _json
        from ingestion.framework.json_bad_records import JsonBadRecordsWriter

        src = tmp_path / "announcements_28042026.json"
        src.write_text(_json.dumps([
            {"symbol": "BAJFINANCE", "desc": "Dividend",
             "an_dt": "28-Apr-2026 21:01:42",
             "attchmntText": "Interim dividend Rs 12.50"},
            {"symbol": "MIRAEMF", "desc": "Trustee Notice",
             "an_dt": "28-Apr-2026 20:00:00",
             "attchmntText": "MF house notice — not a listed equity"},
        ]))

        mock_loader = MagicMock()
        mock_loader.load.side_effect = lambda df: len(df)

        writer = JsonBadRecordsWriter(source="announcements", log_dir=tmp_path / "logs")
        loader = AnnouncementsLoader(
            events_loader=mock_loader,
            bad_records_writer=writer,
            known_symbols={"BAJFINANCE"},
        )
        result = loader.load(src, date(2026, 4, 28))

        assert result == 1
        bad = _json.loads((tmp_path / "logs" / "announcements_28042026.json").read_text())
        assert len(bad) == 1 and bad[0]["symbol"] == "MIRAEMF"
        # Original shape preserved (an_dt with time, attchmntText, etc.)
        assert bad[0]["an_dt"] == "28-Apr-2026 20:00:00"
        assert bad[0]["attchmntText"].startswith("MF house notice")
