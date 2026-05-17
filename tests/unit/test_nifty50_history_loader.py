"""Tests for nifty50_history.csv validation and loader."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from ingestion.nifty50_history_loader import (
    validate_history_csv,
    load_history_csv,
    HistoryCSVValidationError,
)


def _write_csv(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


class TestValidateHistoryCSV:
    def test_valid_add_csv(self, tmp_path):
        csv = tmp_path / "test.csv"
        _write_csv(csv, "symbol,effective_from,action\nRELIANCE,2021-01-01,ADD\nTCS,2021-01-01,ADD\n")
        df = validate_history_csv(csv)
        assert len(df) == 2
        assert list(df["symbol"]) == ["RELIANCE", "TCS"]
        assert list(df["action"]) == ["ADD", "ADD"]

    def test_file_not_found(self, tmp_path):
        with pytest.raises(HistoryCSVValidationError, match="File not found"):
            validate_history_csv(tmp_path / "nonexistent.csv")

    def test_missing_columns(self, tmp_path):
        csv = tmp_path / "test.csv"
        _write_csv(csv, "symbol,effective_from\nRELIANCE,2021-01-01\n")
        with pytest.raises(HistoryCSVValidationError, match="Missing required columns"):
            validate_history_csv(csv)

    def test_empty_symbol(self, tmp_path):
        csv = tmp_path / "test.csv"
        _write_csv(csv, "symbol,effective_from,action\n ,2021-01-01,ADD\n")
        with pytest.raises(HistoryCSVValidationError, match="empty symbol"):
            validate_history_csv(csv)

    def test_invalid_action(self, tmp_path):
        csv = tmp_path / "test.csv"
        _write_csv(csv, "symbol,effective_from,action\nRELIANCE,2021-01-01,UPDATE\n")
        with pytest.raises(HistoryCSVValidationError, match="Invalid action"):
            validate_history_csv(csv)

    def test_unparseable_date(self, tmp_path):
        csv = tmp_path / "test.csv"
        _write_csv(csv, "symbol,effective_from,action\nRELIANCE,not-a-date,ADD\n")
        with pytest.raises(HistoryCSVValidationError, match="Unparseable"):
            validate_history_csv(csv)

    def test_duplicate_symbol_date(self, tmp_path):
        csv = tmp_path / "test.csv"
        _write_csv(csv, "symbol,effective_from,action\nRELIANCE,2021-01-01,ADD\nRELIANCE,2021-01-01,ADD\n")
        with pytest.raises(HistoryCSVValidationError, match="Duplicate"):
            validate_history_csv(csv)

    def test_overlapping_open_add(self, tmp_path):
        csv = tmp_path / "test.csv"
        _write_csv(
            csv,
            "symbol,effective_from,effective_to,action\n"
            "RELIANCE,2021-01-01,,ADD\n"
            "RELIANCE,2021-06-01,,ADD\n",
        )
        with pytest.raises(HistoryCSVValidationError, match="two open-ended"):
            validate_history_csv(csv)

    def test_delete_then_add_no_overlap(self, tmp_path):
        csv = tmp_path / "test.csv"
        _write_csv(
            csv,
            "symbol,effective_from,effective_to,action\n"
            "INFRATEL,2021-01-01,2021-09-30,DELETE\n"
            "BHARTIARTL,2021-01-01,,ADD\n",
        )
        df = validate_history_csv(csv)
        assert len(df) == 2

    def test_uppercase_normalisation(self, tmp_path):
        csv = tmp_path / "test.csv"
        _write_csv(csv, "symbol,effective_from,action\nreliance,2021-01-01,add\n")
        df = validate_history_csv(csv)
        assert df["symbol"].iloc[0] == "RELIANCE"
        assert df["action"].iloc[0] == "ADD"

    def test_valid_effective_to(self, tmp_path):
        csv = tmp_path / "test.csv"
        _write_csv(
            csv,
            "symbol,effective_from,effective_to,action\n"
            "OLDCO,2021-01-01,2023-06-30,DELETE\n",
        )
        df = validate_history_csv(csv)
        assert df["effective_to"].iloc[0] == date(2023, 6, 30)

    def test_overlapping_intervals(self, tmp_path):
        csv = tmp_path / "test.csv"
        _write_csv(
            csv,
            "symbol,effective_from,effective_to,action\n"
            "RELIANCE,2021-01-01,2022-06-01,DELETE\n"
            "RELIANCE,2022-01-01,,ADD\n",
        )
        with pytest.raises(HistoryCSVValidationError, match="Overlapping"):
            validate_history_csv(csv)

    def test_production_file_valid(self):
        """The checked-in nifty50_history.csv must pass validation."""
        path = Path("data/raw/reconstitution/nifty50_history.csv")
        if not path.exists():
            pytest.skip("nifty50_history.csv not found")
        df = validate_history_csv(path)
        assert len(df) == 50
        assert df["symbol"].nunique() == 50
        assert set(df["action"].unique()) == {"ADD"}
