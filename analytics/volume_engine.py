"""Volume analysis engine.

Stateless: takes price DataFrame, returns volume metrics DataFrame.
Computes volume ratios, spike classification, and volume trend.

Usage:
    from analytics.volume_engine import compute_volume
    result = compute_volume(prices_df)
"""

from __future__ import annotations

import logging

import pandas as pd
import numpy as np
from scipy.stats import linregress

from analytics.registry import register_engine
from config.thresholds import get_volume_thresholds

logger = logging.getLogger(__name__)


@register_engine(
    name="volume",
    inputs=("prices",),
    outputs=(
        "trade_date", "symbol", "vol_ratio_1d", "vol_ratio_5d", "vol_ratio_20d",
        "avg_volume_20d", "volume_trend_3m",
    ),
)
def compute_volume(df: pd.DataFrame) -> pd.DataFrame:
    """Compute volume metrics for each symbol at each date.

    Args:
        df: DataFrame from fact_eod_price with columns:
            trade_date, symbol, total_traded_qty.
            Must be sorted by (symbol, trade_date).

    Returns:
        DataFrame with columns:
            trade_date, symbol, vol_ratio_1d, vol_ratio_5d, vol_ratio_20d,
            avg_volume_20d, volume_trend_3m
    """
    if df.empty:
        return pd.DataFrame(columns=[
            "trade_date", "symbol", "vol_ratio_1d", "vol_ratio_5d",
            "vol_ratio_20d", "avg_volume_20d", "volume_trend_3m"
        ])

    thresholds = get_volume_thresholds()
    avg_window = thresholds["avg_window_days"]     # 20
    long_avg_window = thresholds["long_avg_window_days"]  # 60

    df = df.sort_values(["symbol", "trade_date"]).copy()

    results = []
    for symbol, group in df.groupby("symbol"):
        group = group.set_index("trade_date").sort_index()

        vol = pd.DataFrame(index=group.index)
        vol["symbol"] = symbol
        vol["trade_date"] = group.index

        volume = group["total_traded_qty"].astype(float)

        # Rolling averages
        avg_20d = volume.rolling(window=avg_window, min_periods=1).mean()
        avg_5d = volume.rolling(window=5, min_periods=1).mean()
        avg_60d = volume.rolling(window=long_avg_window, min_periods=1).mean()

        # Volume ratios (today vs average)
        vol["vol_ratio_1d"] = (volume / avg_20d).round(4)
        vol["vol_ratio_5d"] = (avg_5d / avg_20d).round(4)
        vol["vol_ratio_20d"] = (avg_20d / avg_60d).round(4)
        vol["avg_volume_20d"] = avg_20d.round(0).astype("Int64")

        def calc_trend(arr):
            n = len(arr)
            if n < 63:
                return 0 # Mixed
            x = np.arange(n)
            slope, intercept, r_value, p_value, std_err = linregress(x, arr)
            r_squared = r_value ** 2
            if r_squared >= 0.30:
                if slope > 0:
                    return 1 # Expanding
                elif slope < 0:
                    return -1 # Contracting
            return 0 # Mixed

        trends = volume.rolling(window=63, min_periods=63).apply(calc_trend, raw=True)
        vol["volume_trend_3m"] = "Mixed"
        vol.loc[trends == 1, "volume_trend_3m"] = "Expanding"
        vol.loc[trends == -1, "volume_trend_3m"] = "Contracting"

        results.append(vol.reset_index(drop=True))

    result = pd.concat(results, ignore_index=True)

    logger.info(f"Computed volume metrics for {result['symbol'].nunique()} symbols, {len(result)} rows")
    return result
