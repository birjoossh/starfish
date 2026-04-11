import pandas as pd
from datetime import date, timedelta
from analytics.volume_engine import compute_volume
import numpy as np

def test_volume_trend_expanding():
    # 65 days of monotonically increasing volume
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(65)]
    volume = np.linspace(1000, 5000, 65)
    
    df = pd.DataFrame({
        "trade_date": dates,
        "symbol": "TCS",
        "total_traded_qty": volume
    })
    
    res = compute_volume(df)
    # The last row should have a perfect regression fit predicting Expanding
    assert res.iloc[-1]["volume_trend_3m"] == "Expanding"

def test_volume_trend_contracting():
    # 65 days of monotonically decreasing volume
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(65)]
    volume = np.linspace(5000, 1000, 65)
    
    df = pd.DataFrame({
        "trade_date": dates,
        "symbol": "TCS",
        "total_traded_qty": volume
    })
    
    res = compute_volume(df)
    assert res.iloc[-1]["volume_trend_3m"] == "Contracting"

def test_volume_trend_mixed():
    # 65 days of random noise (low R-squared)
    np.random.seed(42)
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(65)]
    volume = np.random.randint(1000, 5000, 65)
    
    df = pd.DataFrame({
        "trade_date": dates,
        "symbol": "TCS",
        "total_traded_qty": volume
    })
    
    res = compute_volume(df)
    assert res.iloc[-1]["volume_trend_3m"] == "Mixed"
