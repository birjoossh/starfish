"""Returns computation engine.

Stateless: takes price DataFrame, returns returns DataFrame.
Computes 1D, 1M, 3M, 1Y returns per symbol based on close prices.

Usage:
    from analytics.returns_engine import compute_returns
    result = compute_returns(prices_df)
"""

from __future__ import annotations

import logging

import pandas as pd

from analytics.registry import register_engine
from config.thresholds import get_return_windows

logger = logging.getLogger(__name__)


@register_engine(
    name="returns",
    inputs=("prices",),
    outputs=("trade_date", "symbol", "return_1d", "return_1m", "return_3m", "return_1y"),
)
def compute_returns(df: pd.DataFrame) -> pd.DataFrame:
    """Compute returns for each symbol at each date.

    Args:
        df: DataFrame from fact_eod_price with columns:
            trade_date, symbol, close, prev_close.
            Must be sorted by (symbol, trade_date).

    Returns:
        DataFrame with columns:
            trade_date, symbol, return_1d, return_1m, return_3m, return_1y
    """
    if df.empty:
        return pd.DataFrame(columns=[
            "trade_date", "symbol", "return_1d", "return_1m", "return_3m", "return_1y"
        ])

    windows = get_return_windows()
    short = windows["short_window"]    # 1
    medium = windows["medium_window"]  # 21
    long_w = windows["long_window"]    # 63
    yearly = windows["yearly_window"]  # 252

    df = df.sort_values(["symbol", "trade_date"]).copy()

    results = []
    for symbol, group in df.groupby("symbol"):
        group = group.set_index("trade_date").sort_index()

        returns = pd.DataFrame(index=group.index)
        returns["symbol"] = symbol
        returns["trade_date"] = group.index

        # 1D return: (close - prev_close) / prev_close
        returns["return_1d"] = (
            (group["close"] - group["prev_close"]) / group["prev_close"]
        )

        # N-day returns: (close_t - close_{t-N}) / close_{t-N}
        for label, window in [("return_1m", medium), ("return_3m", long_w), ("return_1y", yearly)]:
            shifted = group["close"].shift(window)
            returns[label] = (group["close"] - shifted) / shifted

        results.append(returns.reset_index(drop=True))

    result = pd.concat(results, ignore_index=True)

    # Round to 4 decimal places
    for col in ["return_1d", "return_1m", "return_3m", "return_1y"]:
        result[col] = result[col].round(4)

    logger.info(f"Computed returns for {result['symbol'].nunique()} symbols, {len(result)} rows")
    return result
