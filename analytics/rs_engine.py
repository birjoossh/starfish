"""Relative Strength computation engine.

Computes RS vs Nifty metrics by subtracting index returns from stock returns.

Usage:
    from analytics.rs_engine import compute_rs
    result = compute_rs(returns_df, index_prices_df)
"""
from __future__ import annotations

import logging
import pandas as pd
from config.thresholds import get_return_windows

logger = logging.getLogger(__name__)

def compute_rs(returns_df: pd.DataFrame, index_prices_df: pd.DataFrame) -> pd.DataFrame:
    """Compute Relative Strength (RS) vs Nifty 50.
    
    RS = Stock Return - Index Return.
    
    Args:
        returns_df: DataFrame containing stock returns (output of returns_engine)
                    Required columns: trade_date, symbol, return_1m, return_3m, return_1y
        index_prices_df: DataFrame containing Nifty 50 close prices.
                         Required columns: trade_date, close
                         
    Returns:
        DataFrame with rs_vs_nifty_1m, rs_vs_nifty_3m, rs_vs_nifty_1y appended.
    """
    if returns_df.empty or index_prices_df.empty:
        df = returns_df.copy()
        for col in ["rs_vs_nifty_1m", "rs_vs_nifty_3m", "rs_vs_nifty_1y"]:
            if col not in df.columns:
                df[col] = 0.0
        return df
        
    windows = get_return_windows()
    medium = windows["medium_window"]  # 21
    long_w = windows["long_window"]    # 63
    yearly = windows["yearly_window"]  # 252
    
    # Calculate index returns
    idx_df = index_prices_df.sort_values("trade_date").copy()
    idx_df = idx_df.set_index("trade_date")
    
    index_returns = pd.DataFrame(index=idx_df.index)
    
    for label, window in [("idx_1m", medium), ("idx_3m", long_w), ("idx_1y", yearly)]:
        shifted = idx_df["close"].shift(window)
        index_returns[label] = (idx_df["close"] - shifted) / shifted
        
    index_returns = index_returns.reset_index()
    
    # Merge with stock returns
    merged = pd.merge(returns_df, index_returns, on="trade_date", how="left")
    
    # Compute RS (Stock Return - Index Return)
    merged["rs_vs_nifty_1m"] = (merged["return_1m"] - merged["idx_1m"]).round(4)
    merged["rs_vs_nifty_3m"] = (merged["return_3m"] - merged["idx_3m"]).round(4)
    merged["rs_vs_nifty_1y"] = (merged["return_1y"] - merged["idx_1y"]).round(4)
    
    # Drop index return columns to clean up output
    merged = merged.drop(columns=["idx_1m", "idx_3m", "idx_1y"])
    
    logger.info(f"Computed RS vs Nifty for {len(merged)} rows")
    return merged
