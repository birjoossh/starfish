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

import pandas as pd
from sqlalchemy import text

from config.database import get_engine
from config.thresholds import get_fifty_two_week_lookback

logger = logging.getLogger(__name__)


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
        target_dates = [trade_date]
    else:
        prices_query = text("""
            SELECT trade_date, symbol, close
            FROM fact_eod_price
            ORDER BY symbol, trade_date
        """)
        df = pd.read_sql_query(prices_query, engine, params={})
        target_dates = sorted(df["trade_date"].unique())

    if df.empty:
        logger.warning("No price data found for 52-week computation")
        return 0

    total_written = 0
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

    with engine.connect() as conn:
        for symbol, group in df.groupby("symbol"):
            group = group.set_index("trade_date").sort_index()

            for dt in target_dates:
                if dt not in group.index:
                    continue

                # Get lookback window ending at dt
                window = group.loc[:dt].tail(lookback)

                if window.empty:
                    continue

                current_close = window["close"].iloc[-1]
                wk52_high = window["close"].max()
                wk52_low = window["close"].min()
                wk52_high_date = window["close"].idxmax()
                wk52_low_date = window["close"].idxmin()

                pct_from_high = round(
                    (current_close - wk52_high) / wk52_high * 100, 4
                ) if wk52_high > 0 else 0.0
                pct_from_low = round(
                    (current_close - wk52_low) / wk52_low * 100, 4
                ) if wk52_low > 0 else 0.0

                conn.execute(upsert_sql, {
                    "trade_date": dt,
                    "symbol": symbol,
                    "wk52_high": float(wk52_high),
                    "wk52_low": float(wk52_low),
                    "wk52_high_date": wk52_high_date,
                    "wk52_low_date": wk52_low_date,
                    "pct_from_high": float(pct_from_high),
                    "pct_from_low": float(pct_from_low),
                })
                total_written += 1

        conn.commit()

    logger.info(f"Computed 52-week data: {total_written} rows written to fact_52wk")
    return total_written
