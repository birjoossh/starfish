"""Volume anomaly computation engine.

Reads from fact_eod_price, writes to mart_volume_anomaly.
Classifies volume spikes per threshold config and evaluates VA-1
through VA-7 rules in spec priority order (§6.3).

Usage:
    from analytics.compute_volume_anomalies import compute_volume_anomalies
    compute_volume_anomalies()  # all dates
    compute_volume_anomalies(trade_date=date(2024,1,17))  # single date
"""

from __future__ import annotations

import logging
from datetime import date

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


def _match_va_rule(
    volume_ratio: float,
    price_chg: float,
    delivery_pct: float | None,
    has_event_within_3d: bool,
    dry_count_5d: int,
) -> str | None:
    """Evaluate VA-1 through VA-7 rules in priority order (first match wins).

    Args:
        volume_ratio: Today's volume / 20-day average volume.
        price_chg: Today's price change as a ratio (e.g. 0.03 = +3%).
        delivery_pct: Delivery % on spike day (None if not yet available).
        has_event_within_3d: True if a corporate event exists within ±3 trading days.
        dry_count_5d: Number of consecutive prior sessions with volume_ratio < 0.4.

    Returns:
        The matched rule label, or None if no rule fires.
    """
    # VA-5: volume_ratio > 3.0 AND event within ±3 trading days
    if volume_ratio > 3.0 and has_event_within_3d:
        return "VA-5 Event-Driven Volume"

    # VA-1: volume_ratio > 2.0 AND price_chg > +3%
    if volume_ratio > 2.0 and price_chg > 0.03:
        return "VA-1 Bullish Volume Surge"

    # VA-2: volume_ratio > 2.0 AND price_chg < -3%
    if volume_ratio > 2.0 and price_chg < -0.03:
        return "VA-2 Distribution Signal"

    # VA-3: volume_ratio > 2.0 AND ABS(price_chg) < 1%
    if volume_ratio > 2.0 and abs(price_chg) < 0.01:
        return "VA-3 A/D Unclear — Watch"

    # VA-6: volume_ratio > 1.5 AND delivery_pct > 60%
    if volume_ratio > 1.5 and delivery_pct is not None and delivery_pct > 60:
        return "VA-6 Institutional Accumulation"

    # VA-7: volume_ratio > 1.5 AND delivery_pct < 25%
    if volume_ratio > 1.5 and delivery_pct is not None and delivery_pct < 25:
        return "VA-7 Speculative Activity"

    # VA-4: volume_ratio < 0.4 for 5 consecutive sessions (incl. today)
    if volume_ratio < 0.4 and dry_count_5d >= 5:
        return "VA-4 Drying Up — Breakout Setup"

    return None


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

    # Load corporate events for nearest-event and ±3d lookups
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

    # Build per-symbol event-date set for fast ±3d membership checks
    event_dates_by_symbol: dict[str, set[date]] = {}
    if not events_df.empty:
        for sym, grp in events_df.groupby("symbol"):
            event_dates_by_symbol[sym] = set(grp["event_date"])

    upsert_sql = text("""
        INSERT INTO mart_volume_anomaly (
            calc_date, symbol, volume_today, avg_vol_20d, volume_ratio,
            spike_level, price_chg_on_spike_day, delivery_pct,
            nearest_event_within_5d, nearest_event_type, anomaly_direction,
            va_rule
        ) VALUES (
            :calc_date, :symbol, :volume_today, :avg_vol_20d, :volume_ratio,
            :spike_level, :price_chg_on_spike_day, :delivery_pct,
            :nearest_event_within_5d, :nearest_event_type, :anomaly_direction,
            :va_rule
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
            anomaly_direction = EXCLUDED.anomaly_direction,
            va_rule = EXCLUDED.va_rule
    """)

    rows_written = 0

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

            # Consecutive dry-up count for VA-4 (volume_ratio < 0.4)
            dry_count = 0
            dry_counts = []
            for _, r in group.iterrows():
                if float(r["volume_ratio"]) < 0.4:
                    dry_count += 1
                else:
                    dry_count = 0
                dry_counts.append(dry_count)
            group["dry_count_5d"] = dry_counts

            # Event dates for this symbol
            sym_event_dates = event_dates_by_symbol.get(symbol, set())

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
                has_event_within_3d = False
                if not sym_events.empty:
                    for _, e in sym_events.iterrows():
                        delta = abs((e["event_date"] - dt).days)
                        if delta <= 3:
                            has_event_within_3d = True
                        if delta <= 5 and nearest_event is None:
                            nearest_event = str(e["event_date"])
                            nearest_type = e["event_type"]

                # Match VA rule
                vol_ratio = float(r["volume_ratio"])
                price_chg = float(r["price_chg_on_spike_day"])
                delivery = float(r["delivery_pct"]) if pd.notna(r["delivery_pct"]) else None
                dry_count_5d = int(r["dry_count_5d"])

                va_rule = _match_va_rule(
                    volume_ratio=vol_ratio,
                    price_chg=price_chg,
                    delivery_pct=delivery,
                    has_event_within_3d=has_event_within_3d,
                    dry_count_5d=dry_count_5d,
                )

                conn.execute(upsert_sql, {
                    "calc_date": dt,
                    "symbol": symbol,
                    "volume_today": int(r["total_traded_qty"]),
                    "avg_vol_20d": int(r["avg_vol_20d"]),
                    "volume_ratio": vol_ratio,
                    "spike_level": r["spike_level"],
                    "price_chg_on_spike_day": price_chg,
                    "delivery_pct": delivery,
                    "nearest_event_within_5d": nearest_event,
                    "nearest_event_type": nearest_type,
                    "anomaly_direction": r["anomaly_direction"],
                    "va_rule": va_rule,
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
