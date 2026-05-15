import math

import pandas as pd
import pytest

from analytics.iss_scorer import compute_iss


def test_compute_iss_max_score():
    # Construct a perfect row summing 100 points
    row = {
        "return_3m": 0.20,              # F1: 15 pts
        "return_1y": 0.30,              # F1: 10 pts
        "rs_vs_nifty_3m": 0.10,         # F2: 12 pts
        "rs_vs_nifty_1y": 0.15,         # F2: 8 pts
        "drawdown_from_52w_high_pct": -0.02, # F3: 15 pts
        "vol_ratio_1d": 2.0,            # F4: 15 pts
        "return_1d": 0.05,              # F4 needs positive price direction
        "direction_consistency_20d": 1.0, # F6: 10 pts
        "intraday_reversal_count_20d": 0,
        "distance_from_52w_low_pct": 0.50, # F7: 5 pts
        # F5 is manually hardcoded to 0 for now pending Phase E
    }
    
    res = compute_iss(row)
    assert res["iss_score"] == 90 # Out of 90 because F5 defaults to 0
    assert res["iss_score_breakdown"]["Price Performance (F1)"] == 25
    assert res["iss_score_breakdown"]["Relative Strength (F2)"] == 20
    assert res["iss_score_breakdown"]["Volume Confirmation (F4)"] == 15

def test_compute_iss_null_defaults():
    # Pass a row with only minimal parameters representing a new listing without 1Y history
    row = {
        "return_3m": 0.0,
        # return_1y is missing!
        # rs_1y is missing!
    }

    res = compute_iss(row)
    # Check default fallbacks injected by formula based on missing
    assert res["iss_score_breakdown"]["Price Performance (F1)"] == 3 # Default 1Y 3 pts
    assert res["iss_score_breakdown"]["Relative Strength (F2)"] == 2 # Default 1Y 2 pts


# ─── TODO-122: NaN must be treated like None ─────────────────────────────────

@pytest.mark.parametrize(
    "nan_value",
    [float("nan"), pd.NA, math.nan],
    ids=["python-nan", "pandas-NA", "math-nan"],
)
def test_nan_return_1y_gets_spec_default(nan_value):
    """return_1y = NaN must give 3 pts (spec default), not 0 (was the bug)."""
    row = {"return_3m": 0.0, "return_1y": nan_value}
    res = compute_iss(row)
    assert res["iss_score_breakdown"]["Price Performance (F1)"] == 3


@pytest.mark.parametrize(
    "nan_value",
    [float("nan"), pd.NA, math.nan],
    ids=["python-nan", "pandas-NA", "math-nan"],
)
def test_nan_rs_vs_nifty_1y_gets_spec_default(nan_value):
    """rs_vs_nifty_1y = NaN must give 2 pts (spec default), not 0 (was the bug).

    rs_vs_nifty_3m = -0.10 falls into the negative branch (0 pts), so the
    only Factor 2 contribution comes from the 1Y default — isolating the
    NaN-vs-None semantics under test.
    """
    row = {
        "return_3m": 0.0,
        "return_1y": 0.0,
        "rs_vs_nifty_3m": -0.10,
        "rs_vs_nifty_1y": nan_value,
    }
    res = compute_iss(row)
    assert res["iss_score_breakdown"]["Relative Strength (F2)"] == 2


def test_nan_rs_vs_nifty_3m_scores_zero_like_none():
    """rs_vs_nifty_3m has no spec default; NaN must score 0, same as None."""
    row_nan = {
        "return_3m": 0.0,
        "return_1y": 0.0,
        "rs_vs_nifty_3m": float("nan"),
        "rs_vs_nifty_1y": 0.0,
    }
    row_none = {
        "return_3m": 0.0,
        "return_1y": 0.0,
        "rs_vs_nifty_3m": None,
        "rs_vs_nifty_1y": 0.0,
    }
    assert compute_iss(row_nan)["iss_score_breakdown"]["Relative Strength (F2)"] \
        == compute_iss(row_none)["iss_score_breakdown"]["Relative Strength (F2)"]


def test_nan_drawdown_scores_zero():
    row = {"return_3m": 0.0, "drawdown_from_52w_high_pct": float("nan")}
    res = compute_iss(row)
    assert res["iss_score_breakdown"]["Drawdown Base (F3)"] == 0


def test_nan_direction_consistency_scores_zero():
    row = {"return_3m": 0.0, "direction_consistency_20d": float("nan")}
    res = compute_iss(row)
    assert res["iss_score_breakdown"]["Trend Stability (F6)"] == 0
