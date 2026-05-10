"""52-week high/low computation engine.

Reads from fact_eod_price, writes to fact_52wk.
Rolling 252-trading-day lookback per symbol per date.
Handles < 252 day history by using available window.

Usage:
    from analytics.compute_52wk import compute_52wk
    compute_52wk()  # computes for all dates in fact_eod_price
    compute_52wk(trade_date=date(2024,1,17))  # single date
"""

from __future__ import annotations

import logging
from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy import text

from analytics.corp_action_adjuster import adjust_prices
from config.database import get_engine
from config.thresholds import get_fifty_two_week_lookback

logger = logging.getLogger(__name__)

_BATCH_SIZE = 5000


def _rolling_argmax_dates(closes: np.ndarray, dates: np.ndarray, lookback: int) -> np.ndarray:
    """For each i, return the date in closes[max(0,i-lookback+1):i+1] with the largest value.

    Ties resolve to the most recent occurrence (idiomatic for "52-week high").
    """
    n = len(closes)
    out = np.empty(n, dtype=dates.dtype)
    if n == 0:
        return out
    # cummax-from-the-right within each window; use a deque-like loop in numpy.
    # A simple O(n*lookback) numpy slice is fast enough at lookback=252 and beats
    # a Python pandas.apply because the inner work is vectorized.
    for i in range(n):
        start = max(0, i - lookback + 1)
        window = closes[start : i + 1]
        # argmax: first occurrence; flip to get last occurrence (tie-breaking
        # preference: most recent date that hit the max).
        rel = len(window) - 1 - np.argmax(window[::-1])
        out[i] = dates[start + rel]
    return out


def _rolling_argmin_dates(closes: np.ndarray, dates: np.ndarray, lookback: int) -> np.ndarray:
    n = len(closes)
    out = np.empty(n, dtype=dates.dtype)
    if n == 0:
        return out
    for i in range(n):
        start = max(0, i - lookback + 1)
        window = closes[start : i + 1]
        rel = len(window) - 1 - np.argmin(window[::-1])
        out[i] = dates[start + rel]
    return out


def compute_52wk(trade_date: date | None = None) -> int:
    """Compute 52-week high/low metrics and write to fact_52wk.

    Args:
        trade_date: If provided, compute only for this date.
                    If None, compute for all dates in fact_eod_price.

    Returns:
        Number of rows written.
    """
    engine = get_engine()
    lookback = get_fifty_two_week_lookback()  # 252

    # Load price data. The lookback window is N **distinct trading dates**,
    # not N rows — when the universe contains hundreds of symbols, an
    # un-distinct LIMIT collapses the window to a few hours of data.
    if trade_date:
        prices_query = text("""
            SELECT trade_date, symbol, close
            FROM fact_eod_price
            WHERE trade_date <= :end_date
              AND trade_date >= (
                  SELECT MIN(trade_date) FROM (
                      SELECT DISTINCT trade_date FROM fact_eod_price
                      WHERE trade_date <= :end_date
                      ORDER BY trade_date DESC
                      LIMIT :lookback
                  ) sub
              )
            ORDER BY symbol, trade_date
        """)
        df = pd.read_sql_query(prices_query, engine, params={
            "end_date": trade_date,
            "lookback": lookback,
        })
        target_dates: set[date] | None = {trade_date}
    else:
        prices_query = text("""
            SELECT trade_date, symbol, close
            FROM fact_eod_price
            ORDER BY symbol, trade_date
        """)
        df = pd.read_sql_query(prices_query, engine, params={})
        target_dates = None  # write every row

    if df.empty:
        logger.warning("No price data found for 52-week computation")
        return 0

    # Back-adjust close for splits/bonuses so the 52W high isn't poisoned
    # by an unadjusted pre-split spike (e.g. BAJFINANCE 2025-06-16, 10x).
    df = adjust_prices(df)

    upsert_sql = text("""
        INSERT INTO fact_52wk (
            trade_date, symbol, wk52_high, wk52_low,
            wk52_high_date, wk52_low_date,
            pct_from_high, pct_from_low
        ) VALUES (
            :trade_date, :symbol, :wk52_high, :wk52_low,
            :wk52_high_date, :wk52_low_date,
            :pct_from_high, :pct_from_low
        )
        ON CONFLICT (trade_date, symbol) DO UPDATE SET
            wk52_high = EXCLUDED.wk52_high,
            wk52_low = EXCLUDED.wk52_low,
            wk52_high_date = EXCLUDED.wk52_high_date,
            wk52_low_date = EXCLUDED.wk52_low_date,
            pct_from_high = EXCLUDED.pct_from_high,
            pct_from_low = EXCLUDED.pct_from_low
    """)

    df = df.sort_values(["symbol", "trade_date"]).reset_index(drop=True)

    rows_buffer: list[dict] = []
    total_written = 0
    n_symbols = df["symbol"].nunique()

    with engine.connect() as conn:
        def flush() -> int:
            nonlocal rows_buffer
            if not rows_buffer:
                return 0
            conn.execute(upsert_sql, rows_buffer)
            written = len(rows_buffer)
            rows_buffer = []
            return written

        for sym_idx, (symbol, group) in enumerate(df.groupby("symbol", sort=False), start=1):
            group = group.sort_values("trade_date")
            closes = group["close"].to_numpy(dtype=float)
            dates = group["trade_date"].to_numpy()

            # Vectorized rolling max/min, min_periods=1 to handle short history.
            close_series = pd.Series(closes)
            highs = close_series.rolling(window=lookback, min_periods=1).max().to_numpy()
            lows  = close_series.rolling(window=lookback, min_periods=1).min().to_numpy()
            high_dates = _rolling_argmax_dates(closes, dates, lookback)
            low_dates  = _rolling_argmin_dates(closes, dates, lookback)

            # Avoid div-by-zero; spec uses NUMERIC(12,2) closes so 0 is rare but possible.
            with np.errstate(divide="ignore", invalid="ignore"):
                pct_high = np.where(highs > 0, (closes - highs) / highs * 100, 0.0)
                pct_low  = np.where(lows  > 0, (closes - lows)  / lows  * 100, 0.0)

            for i in range(len(closes)):
                dt = dates[i]
                if target_dates is not None:
                    # numpy may give a numpy.datetime64; normalise to python date for comparison
                    py_dt = pd.Timestamp(dt).date() if not isinstance(dt, date) else dt
                    if py_dt not in target_dates:
                        continue
                    dt_py = py_dt
                else:
                    dt_py = pd.Timestamp(dt).date() if not isinstance(dt, date) else dt
                rows_buffer.append({
                    "trade_date": dt_py,
                    "symbol": symbol,
                    "wk52_high": float(highs[i]),
                    "wk52_low": float(lows[i]),
                    "wk52_high_date": pd.Timestamp(high_dates[i]).date(),
                    "wk52_low_date": pd.Timestamp(low_dates[i]).date(),
                    "pct_from_high": round(float(pct_high[i]), 4),
                    "pct_from_low":  round(float(pct_low[i]),  4),
                })

                if len(rows_buffer) >= _BATCH_SIZE:
                    total_written += flush()

            if sym_idx % 200 == 0:
                logger.info("compute_52wk: processed %d/%d symbols, %d rows written",
                            sym_idx, n_symbols, total_written + len(rows_buffer))

        total_written += flush()
        conn.commit()

    logger.info(f"Computed 52-week data: {total_written} rows written to fact_52wk")
    return total_written
