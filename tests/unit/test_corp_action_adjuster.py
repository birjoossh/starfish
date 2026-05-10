"""Tests for corporate-action price adjustment."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from analytics.corp_action_adjuster import (
    _bonus_factor,
    _parse_split_factor,
    adjust_prices,
)


class TestParseHelpers:
    def test_bonus_factor_4_to_1(self):
        assert _bonus_factor(4, 1) == 5.0

    def test_bonus_factor_1_to_1(self):
        assert _bonus_factor(1, 1) == 2.0

    def test_bonus_factor_3_to_2(self):
        assert _bonus_factor(3, 2) == 2.5

    def test_bonus_factor_invalid(self):
        assert _bonus_factor(None, 1) is None
        assert _bonus_factor(4, None) is None
        assert _bonus_factor(4, 0) is None
        assert _bonus_factor(-1, 1) is None

    def test_split_face_value_2_to_1(self):
        text = "Face Value Split (Sub-Division) - From Rs 2/- Per Share To Re 1/- Per Share"
        assert _parse_split_factor(text) == 2.0

    def test_split_face_value_5_to_1(self):
        text = "Face Value Split - From Rs 5/- Per Share to Re 1/- Per Share"
        assert _parse_split_factor(text) == 5.0

    def test_split_face_value_10_to_2(self):
        assert _parse_split_factor("From Rs 10 to Rs 2") == 5.0

    def test_split_unparseable(self):
        assert _parse_split_factor("Some random text") is None
        assert _parse_split_factor("") is None
        assert _parse_split_factor(None) is None
        assert _parse_split_factor("From Rs 2 to Rs 2") is None


def _prices(rows):
    return pd.DataFrame(rows)


class TestAdjustPrices:
    def test_no_actions_passthrough(self):
        prices = _prices([
            {"trade_date": date(2025, 1, 1), "symbol": "X", "close": 100.0, "prev_close": 99.0},
            {"trade_date": date(2025, 1, 2), "symbol": "X", "close": 101.0, "prev_close": 100.0},
        ])
        out = adjust_prices(prices, actions=pd.DataFrame(columns=["symbol", "ex_date", "factor"]))
        pd.testing.assert_frame_equal(
            out.reset_index(drop=True),
            prices.assign(trade_date=[date(2025, 1, 1), date(2025, 1, 2)]).reset_index(drop=True),
            check_dtype=False,
        )

    def test_split_only(self):
        prices = _prices([
            {"trade_date": date(2025, 1, 9),  "symbol": "X", "close": 1000.0, "prev_close": 1010.0},
            {"trade_date": date(2025, 1, 10), "symbol": "X", "close": 200.0,  "prev_close": 1000.0},
            {"trade_date": date(2025, 1, 11), "symbol": "X", "close": 205.0,  "prev_close": 200.0},
        ])
        actions = pd.DataFrame([{"symbol": "X", "ex_date": date(2025, 1, 10), "factor": 5.0}])
        out = adjust_prices(prices, actions=actions)
        # Pre-ex-date close adjusted
        assert out.iloc[0]["close"] == pytest.approx(200.0)
        # On-or-after-ex-date close NOT adjusted
        assert out.iloc[1]["close"] == 200.0
        assert out.iloc[2]["close"] == 205.0
        # prev_close on ex_date: previous day was pre-ex → adjusted
        assert out.iloc[1]["prev_close"] == pytest.approx(200.0)
        # prev_close after ex_date: previous day was on ex_date → not adjusted
        assert out.iloc[2]["prev_close"] == 200.0
        # prev_close on day before ex_date: previous day was pre-ex → adjusted
        assert out.iloc[0]["prev_close"] == pytest.approx(202.0)

    def test_bonus_only(self):
        prices = _prices([
            {"trade_date": date(2025, 8, 7), "symbol": "Y", "close": 2000.0, "prev_close": 2010.0},
            {"trade_date": date(2025, 8, 8), "symbol": "Y", "close": 1000.0, "prev_close": 2000.0},
            {"trade_date": date(2025, 8, 9), "symbol": "Y", "close": 1010.0, "prev_close": 1000.0},
        ])
        actions = pd.DataFrame([{"symbol": "Y", "ex_date": date(2025, 8, 8), "factor": 2.0}])
        out = adjust_prices(prices, actions=actions)
        assert out.iloc[0]["close"] == pytest.approx(1000.0)
        assert out.iloc[1]["close"] == 1000.0
        assert out.iloc[2]["close"] == 1010.0

    def test_bonus_plus_split_same_day(self):
        """BAJFINANCE-style: 4:1 bonus + 2:1 split on same ex_date → 10x adjustment."""
        prices = _prices([
            {"trade_date": date(2025, 6, 13), "symbol": "B", "close": 9331.0, "prev_close": 9368.5},
            {"trade_date": date(2025, 6, 16), "symbol": "B", "close": 938.0,  "prev_close": 9331.0},
            {"trade_date": date(2025, 6, 17), "symbol": "B", "close": 923.0,  "prev_close": 938.0},
        ])
        actions = pd.DataFrame([
            {"symbol": "B", "ex_date": date(2025, 6, 16), "factor": 5.0},  # bonus 4:1
            {"symbol": "B", "ex_date": date(2025, 6, 16), "factor": 2.0},  # split 2:1
        ])
        out = adjust_prices(prices, actions=actions)
        assert out.iloc[0]["close"] == pytest.approx(933.1, abs=0.01)
        assert out.iloc[0]["prev_close"] == pytest.approx(936.85, abs=0.01)
        assert out.iloc[1]["close"] == 938.0  # ex_date row: not adjusted
        assert out.iloc[1]["prev_close"] == pytest.approx(933.1, abs=0.01)
        assert out.iloc[2]["close"] == 923.0
        assert out.iloc[2]["prev_close"] == 938.0

    def test_multiple_actions_different_dates(self):
        """Two splits at different ex_dates: cumulative back-adjustment."""
        prices = _prices([
            {"trade_date": date(2025, 1, 1),  "symbol": "Z", "close": 1000.0, "prev_close": 1000.0},
            {"trade_date": date(2025, 6, 1),  "symbol": "Z", "close": 500.0,  "prev_close": 500.0},
            {"trade_date": date(2025, 12, 1), "symbol": "Z", "close": 250.0,  "prev_close": 250.0},
        ])
        actions = pd.DataFrame([
            {"symbol": "Z", "ex_date": date(2025, 5, 1),  "factor": 2.0},
            {"symbol": "Z", "ex_date": date(2025, 11, 1), "factor": 2.0},
        ])
        out = adjust_prices(prices, actions=actions)
        # Jan 1 row precedes both → divide by 4
        assert out.iloc[0]["close"] == pytest.approx(250.0)
        # Jun 1 row precedes only second action → divide by 2
        assert out.iloc[1]["close"] == pytest.approx(250.0)
        # Dec 1 row after both → unchanged
        assert out.iloc[2]["close"] == 250.0

    def test_other_symbol_unchanged(self):
        prices = _prices([
            {"trade_date": date(2025, 1, 9),  "symbol": "X", "close": 1000.0, "prev_close": 1010.0},
            {"trade_date": date(2025, 1, 10), "symbol": "X", "close": 200.0,  "prev_close": 1000.0},
            {"trade_date": date(2025, 1, 9),  "symbol": "OTHER", "close": 50.0, "prev_close": 51.0},
            {"trade_date": date(2025, 1, 10), "symbol": "OTHER", "close": 52.0, "prev_close": 50.0},
        ])
        actions = pd.DataFrame([{"symbol": "X", "ex_date": date(2025, 1, 10), "factor": 5.0}])
        out = adjust_prices(prices, actions=actions)
        other = out[out["symbol"] == "OTHER"].sort_values("trade_date").reset_index(drop=True)
        assert other.iloc[0]["close"] == 50.0
        assert other.iloc[1]["close"] == 52.0
        assert other.iloc[1]["prev_close"] == 50.0

    def test_ohlc_adjusted_together(self):
        prices = _prices([
            {"trade_date": date(2025, 1, 9),  "symbol": "X",
             "open": 1010.0, "high": 1020.0, "low": 990.0, "close": 1000.0, "prev_close": 1015.0},
            {"trade_date": date(2025, 1, 10), "symbol": "X",
             "open": 200.0,  "high": 210.0,  "low": 195.0, "close": 205.0, "prev_close": 1000.0},
        ])
        actions = pd.DataFrame([{"symbol": "X", "ex_date": date(2025, 1, 10), "factor": 5.0}])
        out = adjust_prices(prices, actions=actions)
        # Pre-ex row: all OHLC divided by 5
        assert out.iloc[0]["open"]  == pytest.approx(202.0)
        assert out.iloc[0]["high"]  == pytest.approx(204.0)
        assert out.iloc[0]["low"]   == pytest.approx(198.0)
        assert out.iloc[0]["close"] == pytest.approx(200.0)
        # Ex-date row: OHLC unchanged
        assert out.iloc[1]["open"]  == 200.0
        assert out.iloc[1]["close"] == 205.0

    def test_empty_input(self):
        empty = pd.DataFrame(columns=["trade_date", "symbol", "close", "prev_close"])
        out = adjust_prices(empty, actions=pd.DataFrame(columns=["symbol", "ex_date", "factor"]))
        assert len(out) == 0
