"""Unit tests for ingestion framework fetchers."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ingestion.framework.fetchers.base import BaseFetcher, FetchError


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
