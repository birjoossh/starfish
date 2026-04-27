"""Volume anomaly computation engine.

Reads from fact_eod_price, writes to mart_volume_anomaly.
Classifies volume spikes per threshold config.

Usage:
    from analytics.compute_volume_anomalies import compute_volume_anomalies
    compute_volume_anomalies()  # all dates
    compute_volume_anomalies(trade_date=date(2024,1,17))  # single date
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import text

from config.database import get_engine
from config.thresholds import get_volume_thresholds

logger = logging.getLogger(__name__)


def _classify_spike(ratio: float, thresholds: dict) -> str:
    """Classify volume spike level based on ratio."""
    if ratio >= thresholds.get("spike_extreme", 3.0):
        return "Extreme"
    if ratio >= thresholds.get("spike_high", 2.0):
        return "High"
    if ratio >= thresholds.get("spike_moderate", 1.5):
        return "Moderate"
    if ratio >= thresholds.get("spike_mild", 1.2):
        return "Mild"
    return "Normal"


def compute_volume_anomalies(trade_date: date | None = None) -> int:
    """Compute volume anomaly metrics and write to mart_volume_anomaly.

    Args:
        trade_date: If provided, compute only for this date.
                    If None, compute for all dates in fact_eod_price.

    Returns:
        Number of rows written.
    """
    engine = get_engine()
    thresholds = get_volume_thresholds()
    avg_window = int(thresholds.get("avg_window_days", 20))

    # Load price data with volume and delivery
    if trade_date:
        query = text("""
            SELECT trade_date, symbol, total_traded_qty, close, prev_close,
                   delivery_pct
            FROM fact_eod_price
            WHERE trade_date <= :end_date
            ORDER BY symbol, trade_date
        """)
        df = pd.read_sql_query(query, engine, params={"end_date": trade_date})
        target_dates = [pd.Timestamp(trade_date).date()]
    else:
        query = text("""
            SELECT trade_date, symbol, total_traded_qty, close, prev_close,
                   delivery_pct
            FROM fact_eod_price
            ORDER BY symbol, trade_date
        """)
        df = pd.read_sql_query(query, engine)
        target_dates = sorted(df["trade_date"].unique())

    if df.empty:
        logger.warning("No price data found for volume anomaly computation")
        return 0

    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    df = df.sort_values(["symbol", "trade_date"])

    # Load corporate events for nearest-event lookup
    event_query = text("""
        SELECT symbol, event_date, event_type
        FROM fact_corporate_event
        ORDER BY symbol, event_date
    """)
    try:
        events_df = pd.read_sql_query(event_query, engine)
        events_df["event_date"] = pd.to_datetime(events_df["event_date"]).dt.date
    except Exception:
        events_df = pd.DataFrame(columns=["symbol", "event_date", "event_type"])

    rows_written = 0
    upsert_sql = text("""
        INSERT INTO mart_volume_anomaly (
            calc_date, symbol, volume_today, avg_vol_20d, volume_ratio,
            spike_level, price_chg_on_spike_day, delivery_pct,
            nearest_event_within_5d, nearest_event_type, anomaly_direction
        ) VALUES (
            :calc_date, :symbol, :volume_today, :avg_vol_20d, :volume_ratio,
            :spike_level, :price_chg_on_spike_day, :delivery_pct,
            :nearest_event_within_5d, :nearest_event_type, :anomaly_direction
        )
        ON CONFLICT (calc_date, symbol) DO UPDATE SET
            volume_today = EXCLUDED.volume_today,
            avg_vol_20d = EXCLUDED.avg_vol_20d,
            volume_ratio = EXCLUDED.volume_ratio,
            spike_level = EXCLUDED.spike_level,
            price_chg_on_spike_day = EXCLUDED.price_chg_on_spike_day,
            delivery_pct = EXCLUDED.delivery_pct,
            nearest_event_within_5d = EXCLUDED.nearest_event_within_5d,
            nearest_event_type = EXCLUDED.nearest_event_type,
            anomaly_direction = EXCLUDED.anomaly_direction
    """)

    with engine.begin() as conn:
        for symbol, group in df.groupby("symbol"):
            group = group.sort_values("trade_date").reset_index(drop=True)

            # Rolling 20-day average volume
            group["avg_vol_20d"] = (
                group["total_traded_qty"]
                .rolling(window=avg_window, min_periods=1)
                .mean()
                .round(0)
                .astype("int64")
            )

            group["volume_ratio"] = (
                group["total_traded_qty"] / group["avg_vol_20d"]
            ).round(4)

            group["spike_level"] = group["volume_ratio"].apply(
                lambda r: _classify_spike(float(r), thresholds)
            )

            # Price change on spike day
            group["price_chg_on_spike_day"] = (
                (group["close"] - group["prev_close"]) / group["prev_close"]
            ).round(4)

            # Anomaly direction
            group["anomaly_direction"] = group["price_chg_on_spike_day"].apply(
                lambda x: "Up" if x >= 0 else "Down"
            )

            # Filter to target dates
            for dt in target_dates:
                row = group[group["trade_date"] == dt]
                if row.empty:
                    continue

                r = row.iloc[0]

                # Find nearest event within 5 days
                sym_events = events_df[events_df["symbol"] == symbol]
                nearest_event = None
                nearest_type = None
                if not sym_events.empty:
                    for _, e in sym_events.iterrows():
                        delta = abs((e["event_date"] - dt).days)
                        if delta <= 5:
                            nearest_event = str(e["event_date"])
                            nearest_type = e["event_type"]
                            break

                conn.execute(upsert_sql, {
                    "calc_date": dt,
                    "symbol": symbol,
                    "volume_today": int(r["total_traded_qty"]),
                    "avg_vol_20d": int(r["avg_vol_20d"]),
                    "volume_ratio": float(r["volume_ratio"]),
                    "spike_level": r["spike_level"],
                    "price_chg_on_spike_day": float(r["price_chg_on_spike_day"]),
                    "delivery_pct": float(r["delivery_pct"]) if pd.notna(r["delivery_pct"]) else None,
                    "nearest_event_within_5d": nearest_event,
                    "nearest_event_type": nearest_type,
                    "anomaly_direction": r["anomaly_direction"],
                })
                rows_written += 1

    logger.info(f"Volume anomalies computed: {rows_written} rows written to mart_volume_anomaly")
    return rows_written


def main():
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Compute volume anomalies")
    parser.add_argument("--date", type=str, help="Compute for this date only (YYYY-MM-DD)")
    args = parser.parse_args()

    trade_date = date.fromisoformat(args.date) if args.date else None
    count = compute_volume_anomalies(trade_date)
    print(f"Volume anomalies: {count} rows in mart_volume_anomaly")


if __name__ == "__main__":
    main()
