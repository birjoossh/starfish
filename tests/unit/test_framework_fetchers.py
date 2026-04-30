"""Unit tests for ingestion framework fetchers."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ingestion.framework.fetchers.base import BaseFetcher, FetchError
from ingestion.framework.fetchers.local_fetcher import (
    FixedFileFetcher, LocalFetcher,
)


class TestBaseFetcherABC:
    def test_cannot_instantiate_base_fetcher(self):
        """BaseFetcher is abstract — direct instantiation must raise TypeError."""
        with pytest.raises(TypeError):
            BaseFetcher()  # type: ignore

    def test_concrete_subclass_must_implement_fetch(self):
        """A subclass that skips fetch() raises TypeError on instantiation."""
        class Incomplete(BaseFetcher):
            pass  # missing fetch()

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore

    def test_concrete_subclass_works(self):
        """A complete subclass can be instantiated and called."""
        class AlwaysFails(BaseFetcher):
            def fetch(self, trade_date: date) -> Path:
                raise FetchError("intentional")

        fetcher = AlwaysFails()
        with pytest.raises(FetchError, match="intentional"):
            fetcher.fetch(date(2099, 1, 1))

    def test_fetch_error_is_exception(self):
        """FetchError must be a proper Exception subclass."""
        err = FetchError("something went wrong")
        assert isinstance(err, Exception)
        assert str(err) == "something went wrong"


class TestLocalFetcher:
    def test_finds_file_by_date_pattern(self, tmp_path):
        """LocalFetcher returns path when a matching file exists."""
        trade_date = date(2099, 1, 15)
        expected = tmp_path / "sec_bhavdata_full_15012099.csv"
        expected.write_text("SYMBOL,SERIES\n")

        fetcher = LocalFetcher(source_dir=tmp_path)
        result = fetcher.fetch(trade_date)
        assert result == expected

    def test_raises_fetch_error_when_missing(self, tmp_path):
        """LocalFetcher raises FetchError when no file matches the date."""
        fetcher = LocalFetcher(source_dir=tmp_path)
        with pytest.raises(FetchError, match="No file found for 2099-01-15"):
            fetcher.fetch(date(2099, 1, 15))

    def test_raises_fetch_error_for_missing_directory(self, tmp_path):
        """LocalFetcher raises FetchError if the source_dir does not exist."""
        non_existent = tmp_path / "does_not_exist"
        with pytest.raises(FetchError, match="does not exist"):
            LocalFetcher(source_dir=non_existent)

    def test_uses_only_supplied_patterns_when_given(self, tmp_path):
        """LocalFetcher with explicit patterns must NOT match other source files.

        Regression: previously a single broad pattern list was used for every
        source, so ``--source dim-stock`` would happily pick up a stray
        bhavcopy file. Source-specific patterns prevent that cross-match.
        """
        # Drop a bhavcopy-named file in a dim_stock-style folder
        (tmp_path / "sec_bhavdata_full_15012099.csv").write_text("x")

        fetcher = LocalFetcher(
            source_dir=tmp_path,
            patterns=("NSE_CM_security_{ddmmyyyy}.csv",),
        )
        with pytest.raises(FetchError, match="No file found"):
            fetcher.fetch(date(2099, 1, 15))

    def test_substitutes_yyyymmdd_and_ddmonyyyy_placeholders(self, tmp_path):
        """LocalFetcher resolves all three date placeholders correctly."""
        (tmp_path / "report_20990115.json").write_text("x")
        f1 = LocalFetcher(tmp_path, patterns=("report_{yyyymmdd}.json",))
        assert f1.fetch(date(2099, 1, 15)).name == "report_20990115.json"

        (tmp_path / "cm15JAN2099bhav.csv").write_text("x")
        f2 = LocalFetcher(tmp_path, patterns=("cm{ddmonyyyy}bhav.csv",))
        assert f2.fetch(date(2099, 1, 15)).name == "cm15JAN2099bhav.csv"

    def test_finds_file_by_nse_bhavcopy_naming(self, tmp_path):
        """LocalFetcher also matches NSE legacy bhavcopy naming cmDDMONYYYYbhav.csv."""
        trade_date = date(2099, 3, 5)
        expected = tmp_path / "cm05MAR2099bhav.csv"
        expected.write_text("SYMBOL,SERIES\n")

        fetcher = LocalFetcher(source_dir=tmp_path)
        result = fetcher.fetch(trade_date)
        assert result == expected


from ingestion.framework.fetchers.http_fetcher import NseHttpFetcher, SourceType


class TestFixedFileFetcher:
    def test_returns_supplied_path_regardless_of_date(self, tmp_path):
        """FixedFileFetcher returns the same path for any trade_date."""
        f = tmp_path / "user_supplied.csv"
        f.write_text("x")

        fetcher = FixedFileFetcher(f)
        assert fetcher.fetch(date(2099, 1, 15)) == f
        assert fetcher.fetch(date(1985, 11, 29)) == f

    def test_raises_fetch_error_on_missing_path(self, tmp_path):
        """FixedFileFetcher rejects a non-existent path at construction."""
        with pytest.raises(FetchError, match="does not exist"):
            FixedFileFetcher(tmp_path / "nope.csv")

    def test_raises_fetch_error_when_path_is_directory(self, tmp_path):
        """FixedFileFetcher rejects a directory (must be a regular file)."""
        with pytest.raises(FetchError, match="not a regular file"):
            FixedFileFetcher(tmp_path)


class TestNseHttpFetcher:
    def test_bhavcopy_delegates_to_nse_client(self, tmp_path):
        """NseHttpFetcher.fetch() for BHAVCOPY calls NSEClient.download_bhavcopy."""
        mock_client = MagicMock()
        mock_client.download_bhavcopy.return_value = tmp_path / "bhav.csv"
        (tmp_path / "bhav.csv").write_text("x")

        fetcher = NseHttpFetcher(source=SourceType.BHAVCOPY, client=mock_client)
        result = fetcher.fetch(date(2099, 1, 15))

        mock_client.download_bhavcopy.assert_called_once_with(
            date(2099, 1, 15), output_dir=None
        )
        assert result == tmp_path / "bhav.csv"

    def test_raises_fetch_error_on_circuit_breaker(self, tmp_path):
        """NseHttpFetcher wraps CircuitBreakerOpen as FetchError."""
        from ingestion.nse_client import CircuitBreakerOpen

        mock_client = MagicMock()
        mock_client.download_bhavcopy.side_effect = CircuitBreakerOpen("open")

        fetcher = NseHttpFetcher(source=SourceType.BHAVCOPY, client=mock_client)
        with pytest.raises(FetchError, match="Circuit breaker"):
            fetcher.fetch(date(2099, 1, 15))

    def test_raises_fetch_error_on_request_exception(self, tmp_path):
        """NseHttpFetcher wraps requests.RequestException as FetchError."""
        import requests

        mock_client = MagicMock()
        mock_client.download_bhavcopy.side_effect = requests.RequestException("timeout")

        fetcher = NseHttpFetcher(source=SourceType.BHAVCOPY, client=mock_client)
        with pytest.raises(FetchError, match="HTTP download failed"):
            fetcher.fetch(date(2099, 1, 15))

    def test_source_type_enum_has_all_sources(self):
        """SourceType must cover all automated sources (J, A, B, C, E, F, G)."""
        expected = {"DIM_STOCK", "BHAVCOPY", "WK52", "CONSTITUENTS",
                    "CORPORATE_ACTIONS", "EVENT_CALENDAR", "ANNOUNCEMENTS"}
        assert expected.issubset({s.name for s in SourceType})

    def test_dim_stock_downloads_and_decompresses_gzipped_csv(self, tmp_path):
        """NseHttpFetcher decompresses NSE_CM_security_DDMMYYYY.csv.gz on the fly."""
        import gzip

        csv_body = (
            b"FinInstrmId,TckrSymb,SctySrs,FinInstrmNm,ISIN,ParVal,ListgDt\n"
            b"2885,RELIANCE,EQ,RELIANCE INDUSTRIES LTD,INE002A01018,1000,502070400\n"
        )
        gz_body = gzip.compress(csv_body)

        mock_resp = MagicMock()
        mock_resp.content = gz_body
        mock_client = MagicMock()
        mock_client._request_with_retry.return_value = mock_resp

        fetcher = NseHttpFetcher(
            source=SourceType.DIM_STOCK,
            client=mock_client,
            output_dir=tmp_path,
        )
        out = fetcher.fetch(date(2026, 4, 27))

        assert out.exists()
        assert out.name == "NSE_CM_security_27042026.csv"
        # File on disk is the *decompressed* CSV
        assert out.read_bytes() == csv_body
        # Confirm we hit the right URL (DDMMYYYY format)
        called_url = mock_client._request_with_retry.call_args[0][0]
        assert "NSE_CM_security_27042026.csv.gz" in called_url

    def test_dim_stock_raises_fetch_error_on_bad_gzip(self, tmp_path):
        """NseHttpFetcher wraps OSError from gzip.decompress as FetchError."""
        mock_resp = MagicMock()
        mock_resp.content = b"this is not gzip"
        mock_client = MagicMock()
        mock_client._request_with_retry.return_value = mock_resp

        fetcher = NseHttpFetcher(
            source=SourceType.DIM_STOCK,
            client=mock_client,
            output_dir=tmp_path,
        )
        with pytest.raises(FetchError, match="decompress"):
            fetcher.fetch(date(2026, 4, 27))


from ingestion.framework.fetchers.hybrid_fetcher import HybridFetcher


class TestHybridFetcher:
    def test_uses_http_when_available(self, tmp_path):
        """HybridFetcher returns HTTP result when HTTP succeeds."""
        http_path = tmp_path / "http_result.csv"
        http_path.write_text("x")

        http_mock = MagicMock()
        http_mock.fetch.return_value = http_path
        local_mock = MagicMock()

        fetcher = HybridFetcher(http=http_mock, local=local_mock)
        result = fetcher.fetch(date(2099, 1, 15))

        assert result == http_path
        local_mock.fetch.assert_not_called()

    def test_falls_back_to_local_on_http_failure(self, tmp_path):
        """HybridFetcher uses local fallback when HTTP raises FetchError."""
        local_path = tmp_path / "local_result.csv"
        local_path.write_text("y")

        http_mock = MagicMock()
        http_mock.fetch.side_effect = FetchError("HTTP down")
        local_mock = MagicMock()
        local_mock.fetch.return_value = local_path

        fetcher = HybridFetcher(http=http_mock, local=local_mock)
        result = fetcher.fetch(date(2099, 1, 15))

        assert result == local_path

    def test_raises_fetch_error_when_both_fail(self, tmp_path):
        """HybridFetcher raises FetchError when both HTTP and local fail."""
        http_mock = MagicMock()
        http_mock.fetch.side_effect = FetchError("HTTP down")
        local_mock = MagicMock()
        local_mock.fetch.side_effect = FetchError("No local file")

        fetcher = HybridFetcher(http=http_mock, local=local_mock)
        with pytest.raises(FetchError, match="No local file"):
            fetcher.fetch(date(2099, 1, 15))

    def test_http_non_fetch_error_propagates(self, tmp_path):
        """Unexpected exceptions from HTTP are not swallowed."""
        http_mock = MagicMock()
        http_mock.fetch.side_effect = RuntimeError("unexpected")

        fetcher = HybridFetcher(http=http_mock, local=MagicMock())
        with pytest.raises(RuntimeError, match="unexpected"):
            fetcher.fetch(date(2099, 1, 15))
