"""Trend Stability Engine.

Computes Direction Consistency and Intraday Reversal Count.
"""

from __future__ import annotations

import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

def compute_trend_stability(prices_df: pd.DataFrame, returns_df: pd.DataFrame) -> pd.DataFrame:
    """Compute trend stability metrics.
    
    Args:
        prices_df: DataFrame containing trade_date, symbol, open, high, low, close.
        returns_df: DataFrame containing trade_date, symbol, return_1d, return_1m.
        
    Returns:
        DataFrame with trade_date, symbol, direction_consistency_20d, intraday_reversal_count_20d.
    """
    if prices_df.empty or returns_df.empty:
        return pd.DataFrame(columns=[
            "trade_date", "symbol", "direction_consistency_20d", "intraday_reversal_count_20d"
        ])
        
    merged = pd.merge(
        prices_df[["trade_date", "symbol", "open", "high", "low", "close"]],
        returns_df[["trade_date", "symbol", "return_1d", "return_1m"]],
        on=["trade_date", "symbol"],
        how="inner"
    ).sort_values(["symbol", "trade_date"])

    results = []
    for symbol, group in merged.groupby("symbol"):
        group = group.set_index("trade_date").sort_index()
        
        # 1. Direction Consistency
        # Fraction of last 20 days where sign(return_1d) matches overall 20-day direction (sign(return_1m))
        direction_match = (np.sign(group["return_1d"]) == np.sign(group["return_1m"])).astype(int)
        consistency_20d = direction_match.rolling(window=20, min_periods=5).mean()
        
        # 2. Intraday Reversal Count
        # Bearish: (high-open)/open > 0.02 and (close-open)/open < -0.01
        # Bullish: (open-low)/low > 0.02 and (close-open)/open > 0.01
        
        # Protect against div by zero by filling 0 opens/lows with NaN or checking
        # But prices are strictly positive integers/floats generally
        bearish_rev = ((group["high"] - group["open"]) / group["open"] > 0.02) & \
                      ((group["close"] - group["open"]) / group["open"] < -0.01)
                      
        bullish_rev = ((group["open"] - group["low"]) / group["low"] > 0.02) & \
                      ((group["close"] - group["open"]) / group["open"] > 0.01)
                      
        is_reversal = (bearish_rev | bullish_rev).astype(int)
        reversal_count_20d = is_reversal.rolling(window=20, min_periods=5).sum()
        
        res = pd.DataFrame({
            "trade_date": group.index,
            "symbol": symbol,
            "direction_consistency_20d": consistency_20d.round(2),
            "intraday_reversal_count_20d": reversal_count_20d.astype("Int64")
        })
        results.append(res.reset_index(drop=True))
        
    result = pd.concat(results, ignore_index=True)
    logger.info(f"Computed trend stability for {result['symbol'].nunique()} symbols, {len(result)} rows")
    return result
