"""Tests for returns computation engine."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from analytics.returns_engine import compute_returns


class TestReturnsEngine:
    def test_basic_returns(self, three_days_prices):
        result = compute_returns(three_days_prices)

        assert "return_1d" in result.columns
        assert "return_1m" in result.columns
        assert "return_3m" in result.columns
        assert "return_1y" in result.columns
        assert "symbol" in result.columns
        assert "trade_date" in result.columns

        # 50 symbols x 3 days = 150 rows
        assert len(result) == 150

    def test_1d_return_computed(self, three_days_prices):
        result = compute_returns(three_days_prices)

        # First day should have 1D return from prev_close
        day1 = result[result["trade_date"] == date(2024, 1, 15)]
        assert (day1["return_1d"].notna()).all()

    def test_longer_returns_nan_with_insufficient_data(self, three_days_prices):
        """With only 3 days, 1M/3M/1Y returns should be NaN."""
        result = compute_returns(three_days_prices)

        day1 = result[result["trade_date"] == date(2024, 1, 15)]
        assert day1["return_1m"].isna().all()  # Need 21 days
        assert day1["return_3m"].isna().all()  # Need 63 days
        assert day1["return_1y"].isna().all()  # Need 252 days

    def test_empty_input(self):
        empty_df = pd.DataFrame(columns=["trade_date", "symbol", "close", "prev_close"])
        result = compute_returns(empty_df)

        assert len(result) == 0
        assert "return_1d" in result.columns
