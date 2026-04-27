"""Unit tests for ingestion framework fetchers."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ingestion.framework.fetchers.base import BaseFetcher, FetchError
from ingestion.framework.fetchers.local_fetcher import LocalFetcher


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

    def test_finds_file_by_nse_bhavcopy_naming(self, tmp_path):
        """LocalFetcher also matches NSE legacy bhavcopy naming cmDDMONYYYYbhav.csv."""
        trade_date = date(2099, 3, 5)
        expected = tmp_path / "cm05MAR2099bhav.csv"
        expected.write_text("SYMBOL,SERIES\n")

        fetcher = LocalFetcher(source_dir=tmp_path)
        result = fetcher.fetch(trade_date)
        assert result == expected
