import pandas as pd
from datetime import date, timedelta
from analytics.rs_engine import compute_rs

def test_rs_computation_exact_values(monkeypatch):
    """Verify RS calculation exactly offsets index returns."""
    base = date(2024, 1, 15)
    
    # Mock window sizes so we don't have to build 253 rows.
    mock_windows = {
        "short_window": 1,
        "medium_window": 2,
        "long_window": 4,
        "yearly_window": 8
    }
    
    monkeypatch.setattr("analytics.rs_engine.get_return_windows", lambda: mock_windows)
    
    dates = [base + timedelta(days=i) for i in range(9)]
    
    # Index prices 
    prices = [100.0, 105.0, 110.0, 115.0, 120.0, 130.0, 135.0, 140.0, 150.0]
    idx_df = pd.DataFrame([
        {"trade_date": d, "close": p} for d, p in zip(dates, prices)
    ])
    
    # Stock returns
    returns = []
    for i in range(8):
        returns.append({
            "trade_date": dates[i],
            "symbol": "TCS",
            "return_1m": 0.0,
            "return_3m": 0.0,
            "return_1y": 0.0
        })
    returns.append({
        "trade_date": dates[8],
        "symbol": "TCS",
        "return_1m": 0.15, # 15%
        "return_3m": 0.30, # 30%
        "return_1y": 1.00  # 100%
    })
    ret_df = pd.DataFrame(returns)
    
    # Expected Index returns at Day 8:
    # 1m (window=2): (Day 8 - Day 6) / Day 6 -> (150 - 135) / 135 = 15/135 = 0.1111
    # 3m (window=4): (Day 8 - Day 4) / Day 4 -> (150 - 120) / 120 = 30/120 = 0.2500
    # 1y (window=8): (Day 8 - Day 0) / Day 0 -> (150 - 100) / 100 = 50/100 = 0.5000
    
    # Expected RS at Day 8:
    # rs_1m = 0.15 - 0.1111 = 0.0389
    # rs_3m = 0.30 - 0.2500 = 0.0500
    # rs_1y = 1.00 - 0.5000 = 0.5000
    
    out_df = compute_rs(ret_df, idx_df)
    
    assert len(out_df) == 9
    assert "rs_vs_nifty_1m" in out_df.columns
    assert "rs_vs_nifty_3m" in out_df.columns
    assert "rs_vs_nifty_1y" in out_df.columns
    
    row_day8 = out_df.iloc[8]
    assert row_day8["rs_vs_nifty_1m"] == 0.0389
    assert row_day8["rs_vs_nifty_3m"] == 0.0500
    assert row_day8["rs_vs_nifty_1y"] == 0.5000
