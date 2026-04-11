"""Signal Classification Engine.

Assigns signal categories based on returns, volumes, ISS, and falling knife logics.
"""

from typing import Dict, Any

def classify_signal(row: Dict[str, Any], iss_score: float) -> str:
    """Classify the stock signal category per spec §6.2.

    Categories (in priority order):
        EVT  — significant corporate event in past 20d OR upcoming within 10d
        ACC  — accumulation setup (deep pullback, contracting volume, not a knife)
        MOM  — momentum (positive trend, volume-confirmed, beating Nifty)
        Neutral — everything else
    """
    r1y = row.get("return_1y")
    r3m = row.get("return_3m")
    vt3m = row.get("volume_trend_3m", "Mixed")
    dd = row.get("drawdown_from_52w_high_pct")
    rs3m = row.get("rs_vs_nifty_3m", 0)

    # ── Branch 1: Past events (significance >= 3 within past 20 days) ────────
    days_since = row.get("days_since_last_event")
    event_sig  = row.get("event_significance", 0) or 0
    past_evt = (
        days_since is not None
        and days_since <= 20
        and event_sig >= 3
    )

    # ── Branch 2: Upcoming events (within next 10 days, est. sig >= 3) ───────
    days_to_next = row.get("days_to_next_event")
    next_event_sig = row.get("next_event_significance", 0) or 0
    upcoming_evt = (
        days_to_next is not None
        and 0 <= days_to_next <= 10
        and next_event_sig >= 3
    )

    if past_evt or upcoming_evt:
        return "EventDriven"
        
    # ── Falling Knife Exclusion ───────────────────────────────────────────────
    if r3m is not None and r3m < -0.20 and vt3m != "Contracting":
        is_knife = True
    else:
        is_knife = False

    # ── Accumulation (ACC) Rules ──────────────────────────────────────────────
    if (
        not is_knife and
        r1y is not None and r1y < -0.15 and
        r3m is not None and r3m < -0.10 and
        dd is not None and dd < -0.20 and
        vt3m != "Expanding" and
        iss_score >= 25
    ):
        return "Accumulation"

    # ── Momentum (MOM) Rules ──────────────────────────────────────────────────
    if (
        ((r3m is not None and r3m > 0.08) or (r1y is not None and r1y > 0.20)) and
        vt3m != "Contracting" and
        rs3m > 0.0 and
        iss_score >= 50
    ):
        return "Momentum"

    return "Neutral"

def assign_momentum_tier(iss_score: float) -> str:
    """Classify momentum strength tier."""
    if iss_score >= 80: return "Strong"
    elif iss_score >= 65: return "Confirmed"
    elif iss_score >= 50: return "Watch"
    else: return ""
