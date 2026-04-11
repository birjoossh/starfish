from analytics.signal_classifier import classify_signal, assign_momentum_tier

def test_classify_accumulation():
    row = {
        "return_1y": -0.25,
        "return_3m": -0.15,
        "drawdown_from_52w_high_pct": -0.30,
        "volume_trend_3m": "Contracting",
        "event_flag": False
    }
    
    # Needs ISS >= 35
    assert classify_signal(row, 40) == "Accumulation"
    # Fails ISS rule
    assert classify_signal(row, 30) == "Neutral"

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
    assert assign_momentum_tier(65) == "Watch"
    assert assign_momentum_tier(50) == ""
