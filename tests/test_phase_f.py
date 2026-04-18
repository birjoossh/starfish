"""Unit tests for Phase F dashboard tag helpers."""

from __future__ import annotations

import pandas as pd

from dashboard.phase_f import drawdown_signal_tag, momentum_tier_label


def _row(**kwargs) -> pd.Series:
    base = {
        "drawdown_from_52w_high_pct": -25.0,
        "volume_trend_3m": "Mixed",
        "signal_category": "Neutral",
        "event_flag": False,
        "accumulation_flag": False,
    }
    base.update(kwargs)
    return pd.Series(base)


def test_tag_empty_when_shallow_drawdown():
    r = _row(drawdown_from_52w_high_pct=-10.0, volume_trend_3m="Contracting")
    assert drawdown_signal_tag(r, -20.0) == ""


def test_tag_falling_knife_expanding_volume():
    r = _row(drawdown_from_52w_high_pct=-30.0, volume_trend_3m="Expanding")
    assert drawdown_signal_tag(r, -20.0) == "Falling Knife Risk"


def test_tag_potential_accumulation():
    r = _row(
        drawdown_from_52w_high_pct=-30.0,
        volume_trend_3m="Contracting",
        signal_category="Neutral",
        event_flag=False,
    )
    assert drawdown_signal_tag(r, -20.0) == "Potential Accumulation"


def test_tag_needs_event_review_event_flag():
    r = _row(
        drawdown_from_52w_high_pct=-30.0,
        volume_trend_3m="Mixed",
        event_flag=True,
    )
    assert drawdown_signal_tag(r, -20.0) == "Needs Event Review"


def test_momentum_tier_boundaries():
    assert momentum_tier_label(79.9) == "Confirmed"
    assert momentum_tier_label(80.0) == "Strong"
    assert momentum_tier_label(49.0) == ""
