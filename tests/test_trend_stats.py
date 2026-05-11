"""Unit tests for services.trend_stats."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from services.trend_stats import (
    avg_daily_volume,
    compute_drawdown_series,
    compute_period_stats,
    compute_returns,
    compute_sma,
    max_drawdown,
    pct_days_above_sma,
    period_to_lookback_days,
    realized_vol_annualized,
    sharpe_ratio,
    vol_expansion_days,
)


# ----------------------------- Atomic helpers ---------------------------- #


def test_compute_sma_short_window_returns_nan_until_warmup():
    s = pd.Series([10, 11, 12, 13, 14])
    sma = compute_sma(s, window=3)
    assert math.isnan(sma.iloc[0])
    assert math.isnan(sma.iloc[1])
    assert sma.iloc[2] == pytest.approx(11.0)
    assert sma.iloc[4] == pytest.approx(13.0)


def test_compute_sma_empty_input():
    s = pd.Series([], dtype=float)
    assert compute_sma(s, 5).empty


def test_compute_returns_first_is_nan():
    s = pd.Series([100.0, 110.0, 99.0])
    r = compute_returns(s)
    assert math.isnan(r.iloc[0])
    assert r.iloc[1] == pytest.approx(0.10)
    assert r.iloc[2] == pytest.approx(-0.10)


def test_compute_drawdown_series_basic():
    s = pd.Series([100.0, 120.0, 80.0, 130.0])
    dd = compute_drawdown_series(s)
    assert dd.iloc[0] == pytest.approx(0.0)
    assert dd.iloc[1] == pytest.approx(0.0)
    assert dd.iloc[2] == pytest.approx((80 - 120) / 120)
    assert dd.iloc[3] == pytest.approx(0.0)


def test_max_drawdown_empty():
    assert max_drawdown(pd.Series([], dtype=float)) == 0.0


def test_max_drawdown_flat():
    assert max_drawdown(pd.Series([10.0, 10.0, 10.0])) == pytest.approx(0.0)


def test_max_drawdown_sample():
    # Peak 120 then 80 then 60 then 150 — worst DD from 120 → 60 = -50%
    s = pd.Series([100.0, 120.0, 90.0, 60.0, 100.0, 150.0])
    assert max_drawdown(s) == pytest.approx((60 - 120) / 120)


def test_realized_vol_zero_when_too_few():
    r = pd.Series([np.nan, 0.01])
    # Only one non-NaN — too few.
    assert realized_vol_annualized(r) == 0.0


def test_realized_vol_basic():
    np.random.seed(0)
    daily = pd.Series(np.random.normal(0, 0.01, 252))  # 1% daily vol
    rv = realized_vol_annualized(daily)
    # Expected ~ 0.01 * sqrt(252) ≈ 0.1587. Allow generous tolerance.
    assert 0.12 < rv < 0.20


def test_sharpe_zero_when_flat():
    flat = pd.Series([0.0] * 50)
    assert sharpe_ratio(flat) == 0.0


def test_sharpe_positive_when_drift_positive():
    np.random.seed(1)
    rets = pd.Series(np.random.normal(0.001, 0.01, 252))  # positive drift
    sh = sharpe_ratio(rets)
    assert sh > 0


# ---------------------------- Volume metrics ---------------------------- #


def test_avg_daily_volume_empty():
    assert avg_daily_volume(pd.Series([], dtype=float)) == 0.0


def test_vol_expansion_days_short_input_returns_zero():
    # Less than 20-day window — returns 0
    assert vol_expansion_days(pd.Series([100.0] * 10)) == 0


def test_vol_expansion_days_detects_spikes():
    base = [1.0] * 25
    base[20] = 10.0  # >> 1.5x MA
    s = pd.Series(base)
    assert vol_expansion_days(s, multiplier=1.5) >= 1


def test_pct_days_above_sma_below():
    # Monotonically decreasing — should sit below SMA50 for warmup window
    s = pd.Series([100.0 - i for i in range(60)])
    p = pct_days_above_sma(s, window=50)
    assert p == pytest.approx(0.0)


def test_pct_days_above_sma_uptrend():
    # Monotonically increasing — closes are above their trailing SMA
    s = pd.Series([100.0 + i for i in range(60)])
    p = pct_days_above_sma(s, window=50)
    assert p == pytest.approx(1.0)


# --------------------------- Composite stats ---------------------------- #


def test_compute_period_stats_empty():
    stats = compute_period_stats(pd.DataFrame())
    assert stats["period_return"] == 0.0
    assert stats["vs_nifty_pp"] is None
    assert stats["max_drawdown"] == 0.0


def test_compute_period_stats_single_row_zero_return():
    df = pd.DataFrame({
        "trade_date": ["2026-01-01"],
        "close": [100.0],
        "total_traded_qty": [1_000_000],
    })
    stats = compute_period_stats(df)
    assert stats["period_return"] == 0.0
    assert stats["avg_daily_vol"] == 1_000_000


def test_compute_period_stats_with_nifty_overlay():
    sym = pd.DataFrame({
        "trade_date": pd.date_range("2026-01-01", periods=10, freq="D"),
        "close": np.linspace(100, 115, 10),
        "total_traded_qty": [1_000_000] * 10,
    })
    nifty = pd.DataFrame({
        "trade_date": pd.date_range("2026-01-01", periods=10, freq="D"),
        "close": np.linspace(100, 110, 10),
    })
    stats = compute_period_stats(sym, nifty_df=nifty)
    # Symbol +15%, Nifty +10% → alpha ≈ +5 pp
    assert stats["vs_nifty_pp"] == pytest.approx(5.0, abs=0.5)


def test_compute_period_stats_threshold_edges_no_crash():
    """All edge inputs should produce numeric outputs, no NaN/Inf."""
    rng = np.random.default_rng(0)
    n = 60
    df = pd.DataFrame({
        "trade_date": pd.date_range("2026-01-01", periods=n, freq="D"),
        "close": np.cumprod(1 + rng.normal(0, 0.01, n)) * 100,
        "total_traded_qty": rng.integers(1_000_000, 5_000_000, n),
    })
    stats = compute_period_stats(df)
    for k, v in stats.items():
        if v is not None:
            assert math.isfinite(v), f"{k} not finite: {v}"


# -------------------------- Period lookback ----------------------------- #


@pytest.mark.parametrize(
    "period,days",
    [("1M", 21), ("3M", 63), ("6M", 126), ("1Y", 252), ("3Y", 756), ("YTD", -1)],
)
def test_period_to_lookback_days_known(period: str, days: int):
    assert period_to_lookback_days(period) == days


def test_period_to_lookback_days_unknown_default_6m():
    assert period_to_lookback_days("99M") == 126
