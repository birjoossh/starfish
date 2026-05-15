"""Signal pipeline orchestrator.

Runs all analytics engines and populates mart_stock_signals.
Entry point for signal computation after ingestion.

Usage:
    python -m analytics.compute_signals
    python -m analytics.compute_signals --date 2024-01-17
"""

from __future__ import annotations

import argparse
import logging
from datetime import date

import pandas as pd
from sqlalchemy import text

from config.database import get_engine
from analytics.corp_action_adjuster import adjust_prices
from analytics.returns_engine import compute_returns
from analytics.volume_engine import compute_volume
from analytics.compute_52wk import compute_52wk
from analytics.rs_engine import compute_rs
from analytics.trend_stability_engine import compute_trend_stability
from analytics.iss_scorer import compute_iss
from analytics.signal_classifier import classify_signal, assign_momentum_tier
import json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_prices(trade_date: date | None = None) -> pd.DataFrame:
    """Load price data for signal computation."""
    engine = get_engine()
    if trade_date:
        query = text("""
            SELECT trade_date, symbol, open, high, low, close, prev_close,
                   total_traded_qty, total_traded_value_lakh, total_trades,
                   series, delivery_qty, delivery_pct
            FROM fact_eod_price
            WHERE trade_date <= :trade_date
            ORDER BY symbol, trade_date
        """)
        return pd.read_sql_query(query, engine, params={"trade_date": trade_date})
    else:
        query = text("""
            SELECT trade_date, symbol, open, high, low, close, prev_close,
                   total_traded_qty, total_traded_value_lakh, total_trades,
                   series, delivery_qty, delivery_pct
            FROM fact_eod_price
            ORDER BY symbol, trade_date
        """)
        return pd.read_sql_query(query, engine)


def load_index_prices(trade_date: date | None = None) -> pd.DataFrame:
    """Load index prices for RS computation."""
    engine = get_engine()
    if trade_date:
        query = text("""
            SELECT trade_date, close
            FROM nifty50_index_prices
            WHERE trade_date <= :trade_date
            ORDER BY trade_date
        """)
        return pd.read_sql_query(query, engine, params={"trade_date": trade_date})
    else:
        query = text("""
            SELECT trade_date, close
            FROM nifty50_index_prices
            ORDER BY trade_date
        """)
        return pd.read_sql_query(query, engine)


def load_event_data(trade_date: date | None = None) -> pd.DataFrame:
    """Load most-recent past event and nearest future event per symbol from fact_corporate_event.

    Past row powers ISS Factor 5 and the first EVT branch (recent significant event).
    Future row powers the second EVT branch (upcoming event within 10 days).
    """
    engine = get_engine()
    ref_date = trade_date or date.today()
    query = text("""
        WITH ranked_past AS (
            SELECT symbol, event_date, event_type, significance_score,
                   (CAST(:ref_date AS DATE) - event_date) AS days_since,
                   ROW_NUMBER() OVER (
                       PARTITION BY symbol
                       ORDER BY event_date DESC, significance_score DESC
                   ) AS rn
            FROM fact_corporate_event
            WHERE event_date <= CAST(:ref_date AS DATE)
        ),
        past AS (
            SELECT symbol,
                   event_date AS last_event_date,
                   event_type AS last_event_type,
                   significance_score AS event_significance,
                   days_since AS days_since_last_event
            FROM ranked_past
            WHERE rn = 1
        ),
        ranked_future AS (
            SELECT symbol, event_date, significance_score,
                   (event_date - CAST(:ref_date AS DATE)) AS days_to_next,
                   ROW_NUMBER() OVER (
                       PARTITION BY symbol
                       ORDER BY event_date ASC, significance_score DESC
                   ) AS rn
            FROM fact_corporate_event
            WHERE event_date > CAST(:ref_date AS DATE)
        ),
        future AS (
            SELECT symbol,
                   days_to_next AS days_to_next_event,
                   significance_score AS next_event_significance
            FROM ranked_future
            WHERE rn = 1
        )
        SELECT COALESCE(past.symbol, future.symbol) AS symbol,
               past.last_event_date,
               past.last_event_type,
               past.event_significance,
               past.days_since_last_event,
               future.days_to_next_event,
               future.next_event_significance
        FROM past
        FULL OUTER JOIN future ON past.symbol = future.symbol
    """)
    try:
        return pd.read_sql_query(query, engine, params={"ref_date": str(ref_date)})
    except Exception as e:
        logger.warning("Could not load event data (table may be empty): %s", e)
        return pd.DataFrame()


def compute_signals(trade_date: date | None = None) -> int:
    """Run all engines and populate mart_stock_signals.

    Args:
        trade_date: If provided, compute signals up to this date.
                    If None, compute for all dates.

    Returns:
        Number of rows written to mart_stock_signals.
    """
    logger.info(f"Loading prices for signal computation (date={trade_date})")
    prices_df = load_prices(trade_date)

    if prices_df.empty:
        logger.warning("No price data found, skipping signal computation")
        return 0

    # Apply split/bonus back-adjustment so OHLC and prev_close are economically
    # comparable across ex-dates. Volume is left raw — share-count adjustment
    # for volume is a separate concern.
    prices_df = adjust_prices(prices_df)

    logger.info(f"Loaded {len(prices_df)} price rows for {prices_df['symbol'].nunique()} symbols")

    # Run engines
    logger.info("Computing returns...")
    returns_df = compute_returns(prices_df)

    logger.info("Computing RS vs Nifty...")
    index_df = load_index_prices(trade_date)
    returns_df = compute_rs(returns_df, index_df)

    logger.info("Computing volume metrics...")
    volume_df = compute_volume(prices_df)

    logger.info("Computing trend stability...")
    stability_df = compute_trend_stability(prices_df, returns_df)

    logger.info("Computing 52-week data...")
    compute_52wk(trade_date)

    # Load 52-week data for merging
    engine = get_engine()
    if trade_date:
        wk52_query = text("""
            SELECT trade_date, symbol, pct_from_high as drawdown_from_52w_high_pct,
                   pct_from_low as distance_from_52w_low_pct
            FROM fact_52wk
            WHERE trade_date <= :trade_date
        """)
        wk52_df = pd.read_sql_query(wk52_query, engine, params={"trade_date": trade_date})
    else:
        wk52_query = text("""
            SELECT trade_date, symbol, pct_from_high as drawdown_from_52w_high_pct,
                   pct_from_low as distance_from_52w_low_pct
            FROM fact_52wk
        """)
        wk52_df = pd.read_sql_query(wk52_query, engine)

    # Merge all signals
    # Fix architecture deviation: Merge returns and volume via INNER map preventing missing returns arrays.
    merged = returns_df.merge(
        volume_df, on=["trade_date", "symbol"], how="inner"
    ).merge(
        stability_df, on=["trade_date", "symbol"], how="left"
    ).merge(
        wk52_df, on=["trade_date", "symbol"], how="left"
    )

    # Fill defaults for missing non-event columns
    merged["iss_score"] = 0.0
    merged["signal_category"] = "Neutral"
    merged["last_event_is_negative"] = False
    merged["nifty50_member"] = True

    # Load event data and merge (drop pre-seeded event cols first to avoid _x/_y)
    logger.info("Loading corporate event data...")
    event_df = load_event_data(trade_date)

    if not event_df.empty:
        merged = merged.merge(event_df, on="symbol", how="left")
    
    # Ensure all event columns exist (fill with defaults if event_df was empty or symbol had no events)
    for col, default in [
        ("last_event_date",         None),
        ("last_event_type",         None),
        ("event_significance",      0),
        ("days_since_last_event",   None),
        ("days_to_next_event",      None),
        ("next_event_significance", 0),
    ]:
        if col not in merged.columns:
            merged[col] = default

    # Propagate event significance to last_event_significance for DB write
    merged["last_event_significance"] = merged["event_significance"]
    merged["last_event_type"]  = merged.get("last_event_type", None)
    merged["last_event_date"]  = merged.get("last_event_date", None)
    merged["days_since_last_event"] = merged["days_since_last_event"]
    merged["event_flag"] = False  # will be recomputed below

    # Derived event flag: recent past event OR significant upcoming event (matches EVT gates)
    past_evt = (
        merged["days_since_last_event"].notna()
        & (merged["days_since_last_event"] <= 20)
        & (merged["event_significance"].fillna(0) >= 3)
    )
    upcoming_evt = (
        merged["days_to_next_event"].notna()
        & (merged["days_to_next_event"] >= 0)
        & (merged["days_to_next_event"] <= 10)
        & (merged["next_event_significance"].fillna(0) >= 3)
    )
    merged["event_flag"] = past_evt | upcoming_evt

    # Fill NaN for non-nullable columns (insufficient history → 0).
    # rs_vs_nifty_1m / 3m / 1y are intentionally absent — when index data or
    # return history isn't deep enough we want NULL flowing through to the DB
    # and to the ISS scorer (TODO-122 sub-fix; spec deviation #2). The scorer
    # uses NULL to apply the spec's explicit default rather than penalising
    # the factor as a "0% relative return".
    not_null_defaults = {
        "return_1d": 0.0, "return_1m": 0.0, "return_3m": 0.0,
        "vol_ratio_1d": 1.0, "vol_ratio_5d": 1.0, "vol_ratio_20d": 1.0,
        "drawdown_from_52w_high_pct": 0.0, "distance_from_52w_low_pct": 0.0,
        "avg_volume_20d": 0, "volume_trend_3m": "Mixed",
        "direction_consistency_20d": 0.0, "intraday_reversal_count_20d": 0,
    }
    for col, default in not_null_defaults.items():
        if col in merged.columns:
            merged[col] = merged[col].fillna(default)

    iss_scores = []
    category = []
    breakdowns = []
    acc_flags = []
    mom_flags = []

    # Filter to only the requested date if provided
    if trade_date:
        target_dt = pd.Timestamp(trade_date).date()
        merged = merged[merged["trade_date"] == target_dt]
        if merged.empty:
            logger.warning(f"No rows found for date {target_dt} after merge.")
            return 0
        logger.info(f"Computing signals for {len(merged)} rows on {target_dt}")

    for _, row in merged.iterrows():
        row_dict = row.to_dict()
        iss_res = compute_iss(row_dict)
        score = iss_res["iss_score"]
        
        cat = classify_signal(row_dict, score)
        
        iss_scores.append(score)
        breakdowns.append(json.dumps(iss_res["iss_score_breakdown"]))
        category.append(cat)
        acc_flags.append(cat == "Accumulation")
        mom_flags.append(cat == "Momentum")
        
    merged["iss_score"] = iss_scores
    merged["iss_score_breakdown"] = breakdowns
    merged["signal_category"] = category
    merged["accumulation_flag"] = acc_flags
    merged["momentum_flag"] = mom_flags

    # Write to mart_stock_signals
    upsert_sql = text("""
        INSERT INTO mart_stock_signals (
            calc_date, symbol, return_1d, return_1m, return_3m, return_1y,
            rs_vs_nifty_1m, rs_vs_nifty_3m, rs_vs_nifty_1y,
            vol_ratio_1d, vol_ratio_5d, vol_ratio_20d,
            drawdown_from_52w_high_pct, distance_from_52w_low_pct,
            avg_volume_20d, volume_trend_3m,
            direction_consistency_20d, intraday_reversal_count_20d,
            iss_score, signal_category,
            accumulation_flag, momentum_flag, event_flag,
            last_event_type, last_event_date, days_since_last_event,
            last_event_significance, last_event_is_negative,
            nifty50_member, iss_score_breakdown
        ) VALUES (
            :calc_date, :symbol, :return_1d, :return_1m, :return_3m, :return_1y,
            :rs_vs_nifty_1m, :rs_vs_nifty_3m, :rs_vs_nifty_1y,
            :vol_ratio_1d, :vol_ratio_5d, :vol_ratio_20d,
            :drawdown_from_52w_high_pct, :distance_from_52w_low_pct,
            :avg_volume_20d, :volume_trend_3m,
            :direction_consistency_20d, :intraday_reversal_count_20d,
            :iss_score, :signal_category,
            :accumulation_flag, :momentum_flag, :event_flag,
            :last_event_type, :last_event_date, :days_since_last_event,
            :last_event_significance, :last_event_is_negative,
            :nifty50_member, :iss_score_breakdown
        )
        ON CONFLICT (calc_date, symbol) DO UPDATE SET
            return_1d = EXCLUDED.return_1d,
            return_1m = EXCLUDED.return_1m,
            return_3m = EXCLUDED.return_3m,
            return_1y = EXCLUDED.return_1y,
            rs_vs_nifty_1m = EXCLUDED.rs_vs_nifty_1m,
            rs_vs_nifty_3m = EXCLUDED.rs_vs_nifty_3m,
            rs_vs_nifty_1y = EXCLUDED.rs_vs_nifty_1y,
            vol_ratio_1d = EXCLUDED.vol_ratio_1d,
            vol_ratio_5d = EXCLUDED.vol_ratio_5d,
            vol_ratio_20d = EXCLUDED.vol_ratio_20d,
            drawdown_from_52w_high_pct = EXCLUDED.drawdown_from_52w_high_pct,
            distance_from_52w_low_pct = EXCLUDED.distance_from_52w_low_pct,
            avg_volume_20d = EXCLUDED.avg_volume_20d,
            volume_trend_3m = EXCLUDED.volume_trend_3m,
            direction_consistency_20d = EXCLUDED.direction_consistency_20d,
            intraday_reversal_count_20d = EXCLUDED.intraday_reversal_count_20d,
            iss_score = EXCLUDED.iss_score,
            signal_category = EXCLUDED.signal_category,
            accumulation_flag = EXCLUDED.accumulation_flag,
            momentum_flag = EXCLUDED.momentum_flag,
            event_flag = EXCLUDED.event_flag,
            last_event_type = EXCLUDED.last_event_type,
            last_event_date = EXCLUDED.last_event_date,
            days_since_last_event = EXCLUDED.days_since_last_event,
            last_event_significance = EXCLUDED.last_event_significance,
            last_event_is_negative = EXCLUDED.last_event_is_negative,
            nifty50_member = EXCLUDED.nifty50_member,
            iss_score_breakdown = EXCLUDED.iss_score_breakdown
    """)

    written = 0
    with engine.connect() as conn:
        for _, row in merged.iterrows():
            params = {}
            for col in merged.columns:
                val = row[col]
                if pd.isna(val):
                    params[col] = None
                elif hasattr(val, "item"):
                    params[col] = val.item()
                else:
                    params[col] = val

            # Rename columns to match SQL params
            params["calc_date"] = params.pop("trade_date")

            conn.execute(upsert_sql, params)
            written += 1
        conn.commit()

    logger.info(f"Signal computation complete: {written} rows written to mart_stock_signals")
    return written


def main():
    parser = argparse.ArgumentParser(description="Compute stock signals")
    parser.add_argument("--date", type=str, help="Compute signals up to this date (YYYY-MM-DD)")
    args = parser.parse_args()

    trade_date = date.fromisoformat(args.date) if args.date else None
    count = compute_signals(trade_date)
    print(f"Signals computed: {count} rows in mart_stock_signals")


if __name__ == "__main__":
    main()
