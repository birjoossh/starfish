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
