from analytics.signal_classifier import classify_signal, assign_momentum_tier

def test_classify_accumulation():
    row = {
        "return_1y": -0.25,
        "return_3m": -0.15,
        "drawdown_from_52w_high_pct": -0.30,
        "volume_trend_3m": "Contracting",
        "event_flag": False,
    }

    # Needs ISS >= 25 (see signal_classifier ACC branch)
    assert classify_signal(row, 40) == "Accumulation"
    assert classify_signal(row, 24) == "Neutral"

def test_classify_momentum():
    row = {
        "return_3m": 0.20,
        "volume_trend_3m": "Expanding",
        "rs_vs_nifty_3m": 0.10,
        "event_flag": False
    }
    
    assert classify_signal(row, 65) == "Momentum"
    
def test_falling_knife_prevention():
    row = {
        "return_1y": -0.25,
        "return_3m": -0.25, # Very extreme crash
        "drawdown_from_52w_high_pct": -0.30,
        "volume_trend_3m": "Mixed", # Not shrinking! Still crashing violently!
        "event_flag": False
    }
    
    # Despite 35+ score, should block due to knife exclusion
    assert classify_signal(row, 40) == "Neutral"
    
def test_momentum_tiers():
    assert assign_momentum_tier(90) == "Strong"
    assert assign_momentum_tier(75) == "Confirmed"
    assert assign_momentum_tier(65) == "Confirmed"
    assert assign_momentum_tier(64) == "Watch"
    assert assign_momentum_tier(50) == "Watch"
    assert assign_momentum_tier(49) == ""


def test_classify_event_driven_recent_past():
    """EVT branch 1: significant corporate event within the last 20 days."""
    row = {
        "days_since_last_event": 10,
        "event_significance": 4,
        "days_to_next_event": None,
        "next_event_significance": None,
        "return_3m": 0.20,
        "volume_trend_3m": "Expanding",
        "rs_vs_nifty_3m": 0.1,
        "return_1y": 0.25,
    }
    assert classify_signal(row, 80) == "EventDriven"


def test_classify_event_driven_upcoming():
    """EVT branch 2: significant event within the next 10 days."""
    row = {
        "days_since_last_event": None,
        "event_significance": 0,
        "days_to_next_event": 5,
        "next_event_significance": 4,
        "return_3m": 0.20,
        "volume_trend_3m": "Expanding",
        "rs_vs_nifty_3m": 0.1,
        "return_1y": 0.25,
    }
    assert classify_signal(row, 80) == "EventDriven"


def test_evt_priority_over_momentum():
    """EVT is evaluated before MOM/ACC in classify_signal."""
    row = {
        "days_since_last_event": 5,
        "event_significance": 4,
        "days_to_next_event": None,
        "next_event_significance": None,
        "return_3m": 0.20,
        "volume_trend_3m": "Expanding",
        "rs_vs_nifty_3m": 0.1,
        "return_1y": 0.25,
    }
    assert classify_signal(row, 75) == "EventDriven"


def test_evt_insufficient_upcoming_significance_is_neutral():
    row = {
        "days_since_last_event": None,
        "event_significance": 0,
        "days_to_next_event": 3,
        "next_event_significance": 2,
        "return_3m": 0.0,
        "volume_trend_3m": "Mixed",
        "rs_vs_nifty_3m": 0.0,
    }
    assert classify_signal(row, 40) == "Neutral"
