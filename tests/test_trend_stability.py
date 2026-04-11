import pandas as pd
from datetime import date, timedelta
import numpy as np
from analytics.trend_stability_engine import compute_trend_stability

def test_trend_stability():
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(25)]
    
    # Let return_1m always be positive (+0.10)
    # Give return_1d positive signs for the first 15 days out of the last 20
    # Over 25 days:
    # 0-4: don't care much, we look at rolling 20 at day 24 (which is days 5-24, i.e. 20 days)
    # So days 5-24 are the crucial 20 days!
    
    # Within days 5-24:
    # 15 days positive, 5 days negative -> consistency = 15/20 = 0.75
    
    r1d = np.zeros(25)
    r1d[5:20] = 0.05   # 15 days positive
    r1d[20:25] = -0.05 # 5 days negative
    
    r1m = np.full(25, 0.10)
    
    returns_df = pd.DataFrame({
        "trade_date": dates,
        "symbol": "TCS",
        "return_1d": r1d,
        "return_1m": r1m
    })
    
    # Prices for intraday reversals
    # Normal days (no reversal): open=100, high=101, low=99, close=100
    prices = []
    for i in range(25):
        prices.append({
            "trade_date": dates[i],
            "symbol": "TCS",
            "open": 100, "high": 101, "low": 99, "close": 100
        })
        
    # Day 24 (last day): Bullish Reversal
    # (open-low)/low > 0.02 AND (close-open)/open > 0.01
    prices[24]["low"] = 96     # (100 - 96)/96 = 0.041 > 0.02
    prices[24]["close"] = 102  # (102 - 100)/100 = 0.02 > 0.01
    
    # Day 23: Bearish Reversal
    # (high-open)/open > 0.02 AND (close-open)/open < -0.01
    prices[23]["high"] = 103   # (103 - 100)/100 = 0.03 > 0.02
    prices[23]["close"] = 98   # (98 - 100)/100 = -0.02 < -0.01
    
    prices_df = pd.DataFrame(prices)
    
    res = compute_trend_stability(prices_df, returns_df)
    
    assert len(res) == 25
    last_row = res.iloc[-1]
    
    # Consistency = 15/20 = 0.75
    assert last_row["direction_consistency_20d"] == 0.75
    
    # 2 Reversals within the last 20 days (Day 23 and Day 24)
    assert last_row["intraday_reversal_count_20d"] == 2
