"""Investment Signal Score (ISS) Engine.

Computes a 0-100 score based on 7 technical and momentum factors.
"""

from typing import Any, Dict, Optional

import pandas as pd


def _missing(value: Any) -> bool:
    """Treat None and NaN identically.

    Pandas tends to surface a missing numeric as ``float('nan')`` rather
    than ``None``; the original scorer fell through to the negative-return
    branches when given NaN, silently denying the spec's explicit defaults
    (rs_vs_nifty_1y → 2 pts, return_1y → 3 pts). This helper centralises
    the check.
    """
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _get(row: Dict[str, Any], key: str) -> Optional[float]:
    """Return the row's value for ``key`` or ``None`` if missing/NaN."""
    val = row.get(key)
    return None if _missing(val) else val


def compute_iss(row: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate the Investment Signal Score for a given stock row."""
    breakdown = {}
    total_score = 0

    # -------------------------------------------------------------
    # Factor 1: Price Performance (Max 25 pts)
    # -------------------------------------------------------------
    # 3M Ret (Max 15)
    r3 = _get(row, "return_3m")
    if r3 is None:
        f1_3m = 0
    elif r3 > 0.40: f1_3m = 5  # Bubble penalty
    elif r3 > 0.15: f1_3m = 15
    elif r3 > 0.05: f1_3m = 10
    elif r3 > 0.0:  f1_3m = 5
    else:           f1_3m = 0

    # 1Y Ret (Max 10)
    r1y = _get(row, "return_1y")
    if r1y is None:
        f1_1y = 3 # SPEC EXPLICIT DEFAULT
    elif r1y > 0.60: f1_1y = 3   # Bubble penalty
    elif r1y > 0.20: f1_1y = 10  # Optimal target range
    elif r1y > 0.10: f1_1y = 7
    elif r1y > 0.0:  f1_1y = 3
    else:            f1_1y = 0

    f1_total = f1_3m + f1_1y
    total_score += f1_total
    breakdown["Price Performance (F1)"] = f1_total

    # -------------------------------------------------------------
    # Factor 2: Relative Strength vs Nifty (Max 20 pts)
    # -------------------------------------------------------------
    # 3M RS (Max 12)
    rs3 = _get(row, "rs_vs_nifty_3m")
    if rs3 is None:
        f2_3m = 0
    elif rs3 > 0.05: f2_3m = 12
    elif rs3 > 0.0:  f2_3m = 8
    elif rs3 > -0.05:f2_3m = 4
    else:            f2_3m = 0

    # 1Y RS (Max 8)
    rs1y = _get(row, "rs_vs_nifty_1y")
    if rs1y is None:
        f2_1y = 2 # SPEC EXPLICIT DEFAULT
    elif rs1y > 0.10: f2_1y = 8
    elif rs1y > 0.0:  f2_1y = 4
    else:             f2_1y = 0

    f2_total = f2_3m + f2_1y
    total_score += f2_total
    breakdown["Relative Strength (F2)"] = f2_total

    # -------------------------------------------------------------
    # Factor 3: Drawdown Recovery & Base (Max 15 pts)
    # -------------------------------------------------------------
    dd = _get(row, "drawdown_from_52w_high_pct")
    if dd is None:
        f3 = 0
    elif dd > -0.02: f3 = 5  # Too overextended, mean reversion likely
    elif dd > -0.15: f3 = 15 # The sweet spot pullback!
    elif dd > -0.20: f3 = 10
    elif dd > -0.30: f3 = 5
    else:
        # ACC Mode context, if volume is contracting let's give it some base points
        vt = row.get("volume_trend_3m", "Mixed")
        if vt == "Contracting":
            f3 = 10 # Reward tight consolidations near bottoms
        else:
            f3 = 0

    total_score += f3
    breakdown["Drawdown Base (F3)"] = f3

    # -------------------------------------------------------------
    # Factor 4: Volume Confirmation (Max 15 pts)
    # -------------------------------------------------------------
    vr1 = _get(row, "vol_ratio_1d")
    if vr1 is None:
        f4 = 0
    else:
        # Check alignment with 1d price direction
        r1d = _get(row, "return_1d") or 0
        is_up = r1d > 0
        
        if vr1 > 1.5 and is_up: f4 = 15
        elif vr1 > 1.1 and is_up: f4 = 10
        elif vr1 > 0.8: f4 = 5
        else: f4 = 0
        
    total_score += f4
    breakdown["Volume Confirmation (F4)"] = f4
    
    # -------------------------------------------------------------
    # Factor 5: Corporate Event Presence (Max 10 pts)
    # -------------------------------------------------------------
    # event_significance is populated by compute_signals from the latest past fact_corporate_event.
    # If there is no recent past event but a significant upcoming event (EVT window), use that
    # significance for Factor 5 so ISS aligns with EventDriven classification.
    # Scoring:
    #   sig 5 (bonus/split/buyback):   10 pts
    #   sig 4 (rights/large dividend): 8 pts
    #   sig 3 (dividend/results):      5 pts
    #   sig 1-2 (AGM/EGM/other):       2 pts
    #   no event (None or 0):          0 pts
    event_sig = row.get("event_significance")
    if event_sig is None or event_sig == 0:
        days_to = row.get("days_to_next_event")
        next_sig = row.get("next_event_significance")
        if (
            days_to is not None
            and not pd.isna(days_to)
            and 0 <= float(days_to) <= 10
            and next_sig is not None
            and not pd.isna(next_sig)
            and float(next_sig) >= 3
        ):
            event_sig = int(next_sig)
        else:
            event_sig = 0
    if event_sig is None:
        event_sig = 0
    if event_sig == 0:
        f5 = 0
    elif event_sig >= 5:
        f5 = 10
    elif event_sig >= 4:
        f5 = 8
    elif event_sig >= 3:
        f5 = 5
    else:
        f5 = 2
    total_score += f5
    breakdown["Corporate Event (F5)"] = f5
    
    # -------------------------------------------------------------
    # Factor 6: Trend Stability (Max 10 pts)
    # -------------------------------------------------------------
    dc = _get(row, "direction_consistency_20d")
    revs = _get(row, "intraday_reversal_count_20d")
    if dc is None:
        f6 = 0
    else:
        f6_base = int(dc * 10)
        penalty = (revs or 0) * 2
        f6 = max(0, f6_base - penalty)

    total_score += f6
    breakdown["Trend Stability (F6)"] = f6

    # -------------------------------------------------------------
    # Factor 7: Accumulation / Breakout Alignment (Max 5 pts)
    # -------------------------------------------------------------
    dlow = _get(row, "distance_from_52w_low_pct")
    if dlow is None:
        f7 = 0
    elif dlow > 0.30: f7 = 5
    elif dlow > 0.10: f7 = 3
    else: f7 = 0
        
    total_score += f7
    breakdown["Breakout Alignment (F7)"] = f7
    
    return {
        "iss_score": min(100, max(0, total_score)),
        "iss_score_breakdown": breakdown
    }
