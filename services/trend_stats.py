"""Trend Workbench — period statistics over a price/volume series.

All functions are pure pandas with explicit signatures; no DB or network I/O.
They take pre-loaded DataFrames keyed by ``trade_date`` and return either a
single ``dict`` of summary stats or a ``pd.Series`` (for SMAs / drawdown
curves) so the FastAPI router and tests can compose them freely.

Used by:
    * ``api/routers/trend.py`` — period_stats payload for `GET /trend`
    * Frontend section §03 Trend Workbench — stats sidebar rendering

Conventions:
    * Returns are calculated as ``close.pct_change()`` (simple, not log).
    * Annualization assumes 252 trading days.
    * Empty / insufficient inputs return safe defaults (0.0 or None) so
      callers don't need to special-case the cold-start window.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd


TRADING_DAYS_PER_YEAR = 252


# ---------------------------- Atomic helpers ---------------------------- #


def compute_sma(close: pd.Series, window: int) -> pd.Series:
    """Simple moving average of ``close`` over ``window`` days.

    Returns NaN-filled head until enough history accumulates. Empty input
    returns an empty Series with the same dtype.
    """
    if close.empty:
        return close.copy()
    return close.rolling(window=window, min_periods=window).mean()


def compute_returns(close: pd.Series) -> pd.Series:
    """Daily simple returns (no log). First element will be NaN."""
    if close.empty:
        return close.copy()
    return close.pct_change()


def compute_drawdown_series(close: pd.Series) -> pd.Series:
    """Drawdown from running peak, expressed as a negative fraction.

    Each element ``i`` is ``(close[i] - max(close[:i+1])) / max(close[:i+1])``.
    Empty input returns an empty Series.
    """
    if close.empty:
        return close.copy()
    peak = close.cummax()
    return (close - peak) / peak


def max_drawdown(close: pd.Series) -> float:
    """Largest negative drawdown in the series. 0.0 if empty or all-flat."""
    dd = compute_drawdown_series(close)
    if dd.empty:
        return 0.0
    mn = dd.min()
    if pd.isna(mn):
        return 0.0
    return float(mn)


def realized_vol_annualized(returns: pd.Series) -> float:
    """Annualized realized vol from daily simple returns.

    Defined as ``std(daily_returns) * sqrt(252)``. Returns 0.0 if fewer than
    2 non-NaN observations.
    """
    r = returns.dropna()
    if len(r) < 2:
        return 0.0
    return float(r.std(ddof=0) * math.sqrt(TRADING_DAYS_PER_YEAR))


def sharpe_ratio(returns: pd.Series, *, risk_free_annual: float = 0.06) -> float:
    """Annualized Sharpe with the given risk-free rate (default 6% p.a.).

    Returns 0.0 if vol is 0 or there are too few observations.
    """
    r = returns.dropna()
    if len(r) < 2:
        return 0.0
    daily_rf = (1 + risk_free_annual) ** (1 / TRADING_DAYS_PER_YEAR) - 1
    excess = r - daily_rf
    sd = float(excess.std(ddof=0))
    if sd <= 0:
        return 0.0
    return float(excess.mean() / sd * math.sqrt(TRADING_DAYS_PER_YEAR))


# -------------------------- Vol-based metrics --------------------------- #


def avg_daily_volume(volume: pd.Series) -> float:
    """Mean daily traded quantity over the window. 0.0 if empty."""
    if volume.empty:
        return 0.0
    return float(volume.mean())


def vol_expansion_days(volume: pd.Series, *, multiplier: float = 1.5) -> int:
    """Count of days where volume exceeded ``multiplier × 20-day MA``.

    Used as a proxy for "institutional interest" days in the period stats.
    Returns 0 if the series is shorter than the rolling window.
    """
    if len(volume) < 20:
        return 0
    ma = volume.rolling(window=20, min_periods=20).mean()
    excess = (volume > ma * multiplier).fillna(False)
    return int(excess.sum())


def pct_days_above_sma(close: pd.Series, *, window: int = 50) -> float:
    """Fraction of days where ``close > SMA(window)``. 0.0 if insufficient."""
    sma = compute_sma(close, window)
    aligned = close.align(sma, join="inner")[0]
    sma_inner = sma.dropna()
    if sma_inner.empty:
        return 0.0
    aligned = close.loc[sma_inner.index]
    return float((aligned > sma_inner).mean())


# ---------------------------- Composite API ----------------------------- #


def compute_period_stats(
    price_df: pd.DataFrame,
    *,
    nifty_df: Optional[pd.DataFrame] = None,
    avg_delivery_pct: Optional[float] = None,
    iss_now: Optional[float] = None,
    iss_period_avg: Optional[float] = None,
) -> dict[str, Optional[float]]:
    """Single-call period summary for the Trend Workbench stats sidebar.

    Args:
        price_df: Must contain columns ``trade_date``, ``close``, ``total_traded_qty``.
            Ordered by ``trade_date`` ascending. Output is symmetric over the
            full input window; caller is responsible for slicing to the period.
        nifty_df: Optional Nifty 50 index series with ``trade_date`` and
            ``close`` columns. When provided, ``vs_nifty_pp`` is computed.
        avg_delivery_pct: Pre-computed average delivery % (since delivery is
            optional and may be NULL in fact_eod_price); pass ``None`` to omit.
        iss_now / iss_period_avg: Pre-computed ISS values from
            ``mart_stock_signals``; passed through so the sidebar can render
            them without a second lookup.

    Returns:
        Dict with these keys (values are float or None):
            ``period_return``, ``vs_nifty_pp``, ``max_drawdown``,
            ``realized_vol``, ``sharpe``, ``avg_daily_vol``,
            ``avg_delivery_pct``, ``vol_expansion_days``,
            ``pct_days_above_sma50``, ``iss_now``, ``iss_period_avg``.
    """
    if price_df.empty or "close" not in price_df.columns:
        return _empty_stats()

    closes = price_df["close"].astype(float).reset_index(drop=True)
    volumes = (
        price_df["total_traded_qty"].astype(float).reset_index(drop=True)
        if "total_traded_qty" in price_df.columns
        else pd.Series(dtype=float)
    )

    rets = compute_returns(closes)
    period_return = (
        float(closes.iloc[-1] / closes.iloc[0] - 1) if len(closes) >= 2 else 0.0
    )

    vs_nifty_pp: Optional[float] = None
    if nifty_df is not None and not nifty_df.empty and "close" in nifty_df.columns:
        n_close = nifty_df["close"].astype(float).reset_index(drop=True)
        if len(n_close) >= 2:
            nifty_return = float(n_close.iloc[-1] / n_close.iloc[0] - 1)
            vs_nifty_pp = (period_return - nifty_return) * 100  # percentage points

    return {
        "period_return": period_return,
        "vs_nifty_pp": vs_nifty_pp,
        "max_drawdown": max_drawdown(closes),
        "realized_vol": realized_vol_annualized(rets),
        "sharpe": sharpe_ratio(rets),
        "avg_daily_vol": avg_daily_volume(volumes),
        "avg_delivery_pct": avg_delivery_pct,
        "vol_expansion_days": vol_expansion_days(volumes),
        "pct_days_above_sma50": pct_days_above_sma(closes, window=50),
        "iss_now": iss_now,
        "iss_period_avg": iss_period_avg,
    }


def _empty_stats() -> dict[str, Optional[float]]:
    """Safe defaults for empty input — surfaces visually as "—" in the UI."""
    return {
        "period_return": 0.0,
        "vs_nifty_pp": None,
        "max_drawdown": 0.0,
        "realized_vol": 0.0,
        "sharpe": 0.0,
        "avg_daily_vol": 0.0,
        "avg_delivery_pct": None,
        "vol_expansion_days": 0,
        "pct_days_above_sma50": 0.0,
        "iss_now": None,
        "iss_period_avg": None,
    }


# ------------------------- Period range helpers ------------------------- #


PERIOD_TO_DAYS: dict[str, int] = {
    "1M": 21,
    "3M": 63,
    "6M": 126,
    "1Y": 252,
    "3Y": 756,
    "YTD": -1,   # special: use Jan 1 of current year
}


def period_to_lookback_days(period: str) -> int:
    """Trading-day lookback for a named period.

    ``YTD`` returns -1 as a sentinel — caller resolves the actual date.
    Unknown periods default to 126 (6M).
    """
    return PERIOD_TO_DAYS.get(period.upper(), 126)


__all__ = [
    "TRADING_DAYS_PER_YEAR",
    "PERIOD_TO_DAYS",
    "compute_sma",
    "compute_returns",
    "compute_drawdown_series",
    "max_drawdown",
    "realized_vol_annualized",
    "sharpe_ratio",
    "avg_daily_volume",
    "vol_expansion_days",
    "pct_days_above_sma",
    "compute_period_stats",
    "period_to_lookback_days",
]
