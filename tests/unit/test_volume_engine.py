"""Tests for volume analysis engine."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from analytics.volume_engine import compute_volume


class TestVolumeEngine:
    def test_basic_volume(self, three_days_prices):
        result = compute_volume(three_days_prices)

        assert "vol_ratio_1d" in result.columns
        assert "vol_ratio_5d" in result.columns
        assert "vol_ratio_20d" in result.columns
        assert "avg_volume_20d" in result.columns
        assert "volume_trend_3m" in result.columns

        assert len(result) == 150

    def test_volume_ratio_is_positive(self, three_days_prices):
        result = compute_volume(three_days_prices)

        assert (result["vol_ratio_1d"] > 0).all()

    def test_volume_trend_values(self, three_days_prices):
        result = compute_volume(three_days_prices)

        valid_trends = {"Rising", "Falling", "Mixed"}
        assert set(result["volume_trend_3m"].unique()).issubset(valid_trends)

    def test_empty_input(self):
        empty_df = pd.DataFrame(columns=["trade_date", "symbol", "total_traded_qty"])
        result = compute_volume(empty_df)

        assert len(result) == 0
