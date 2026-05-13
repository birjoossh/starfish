"""Unit tests for the Trend Workbench RS-vs-Nifty overlay (TODO-106 wiring).

Covers the pure-Python helper added to ``api/routers/trend.py`` that
constructs the per-day ``rs_vs_nifty_series`` payload from a price series and
a Nifty 50 index series.

The endpoint integration (DB → /trend) is not exercised here — those calls
require a live API server. These tests pin the contract of the overlay
computation itself so the §03 Trend Workbench overlay rendering stays
stable as the wiring evolves.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from api.routers.trend import _compute_rs_series


def _nifty_df(rows: list[tuple[str, float]]) -> pd.DataFrame:
    """Helper: build the same frame shape that ``_fetch_index_history`` returns."""
    return pd.DataFrame(
        {
            "trade_date": [dt.date.fromisoformat(d) for d, _ in rows],
            "close": [c for _, c in rows],
        }
    )


# ----------------------------- Happy path -------------------------------- #


def test_full_overlap_returns_per_day_rs() -> None:
    """Stock outperforming Nifty by 5pp over 3 days → final value = 5.0."""
    price_dates = ["2026-05-01", "2026-05-02", "2026-05-03"]
    price_closes = [100.0, 105.0, 110.0]  # +10% over the window
    nifty = _nifty_df(
        [("2026-05-01", 1000.0), ("2026-05-02", 1025.0), ("2026-05-03", 1050.0)]
    )  # +5%
    series = _compute_rs_series(price_dates, price_closes, nifty)
    assert series is not None
    assert [pt["date"] for pt in series] == price_dates
    assert series[0]["value"] == pytest.approx(0.0)
    # 110/100 - 1 = 0.10 vs 1050/1000 - 1 = 0.05  →  (0.10 - 0.05) * 100 = 5.0
    assert series[-1]["value"] == pytest.approx(5.0)


def test_underperformer_returns_negative_rs() -> None:
    """Stock down 4% vs Nifty up 1% → final RS = -5.0 pp."""
    series = _compute_rs_series(
        ["2026-05-01", "2026-05-02"],
        [100.0, 96.0],
        _nifty_df([("2026-05-01", 1000.0), ("2026-05-02", 1010.0)]),
    )
    assert series is not None
    assert series[-1]["value"] == pytest.approx(-5.0)


# ----------------------------- Degenerate cases -------------------------- #


def test_empty_nifty_df_returns_none() -> None:
    """No index data ⇒ overlay hidden (UI shows pill)."""
    assert _compute_rs_series(["2026-05-01"], [100.0], pd.DataFrame()) is None


def test_nifty_df_without_close_column_returns_none() -> None:
    """Schema drift safety — missing ``close`` column ⇒ overlay hidden."""
    bad = pd.DataFrame({"trade_date": [dt.date(2026, 5, 1)], "high": [1000.0]})
    assert _compute_rs_series(["2026-05-01"], [100.0], bad) is None


def test_no_date_overlap_returns_none() -> None:
    """Price + index series share zero dates ⇒ no valid anchor ⇒ overlay hidden."""
    nifty = _nifty_df([("2026-04-15", 1000.0), ("2026-04-16", 1010.0)])
    assert _compute_rs_series(["2026-05-01", "2026-05-02"], [100.0, 101.0], nifty) is None


def test_empty_price_dates_returns_none() -> None:
    """No subject price data ⇒ nothing to overlay."""
    nifty = _nifty_df([("2026-05-01", 1000.0)])
    assert _compute_rs_series([], [], nifty) is None


# ----------------------- Partial / gap-tolerant cases -------------------- #


def test_partial_overlap_emits_none_for_gap_days() -> None:
    """Days where the index is missing → ``value: None`` (not 0, not a crash)."""
    series = _compute_rs_series(
        ["2026-05-01", "2026-05-02", "2026-05-03"],
        [100.0, 105.0, 110.0],
        _nifty_df([("2026-05-01", 1000.0), ("2026-05-03", 1050.0)]),
    )
    assert series is not None
    values = [pt["value"] for pt in series]
    assert values[0] == 0.0
    assert values[1] is None  # gap day
    assert values[2] == pytest.approx(5.0)


def test_anchor_skips_initial_gap_then_anchors_at_first_overlap() -> None:
    """When price[0] has no index data, anchor at the next overlapping day."""
    series = _compute_rs_series(
        ["2026-05-01", "2026-05-02", "2026-05-03"],
        [100.0, 200.0, 210.0],
        _nifty_df([("2026-05-02", 1000.0), ("2026-05-03", 1050.0)]),
    )
    assert series is not None
    assert series[0]["value"] is None
    assert series[1]["value"] == pytest.approx(0.0)
    # 210/200 - 1 = 0.05 vs 1050/1000 - 1 = 0.05  →  0pp
    assert series[2]["value"] == pytest.approx(0.0)
