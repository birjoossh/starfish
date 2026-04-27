"""Alert engine - evaluates all alert conditions and fires alerts.

The alert engine monitors mart_stock_signals, mart_volume_anomaly,
fact_corporate_event, and dim_nifty50_constituent tables for conditions
defined in the specification.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, List, Optional
from uuid import uuid4

import pandas as pd
from sqlalchemy import text

from analytics.alert_conditions import AlertConditions
from analytics.dedup_engine import DedupEngine
from config.database import get_engine


class AlertEngine:
    """Main alert evaluation engine."""

    def __init__(self):
        self.dedup = DedupEngine()
        self.conditions = AlertConditions()

    async def evaluate_all_alerts(self, calc_date: date) -> List[Dict[str, Any]]:
        """Run all alert conditions for a given date.

        Args:
            calc_date: Date to evaluate alerts for

        Returns:
            List of fired alerts with their details
        """
        alerts = []

        # A-01: Deep Drawdown
        alerts.extend(await self.conditions.a01_deep_drawdown(calc_date))

        # A-02: ISS Momentum Breakout
        alerts.extend(await self.conditions.a02_iss_breakout(calc_date))

        # A-03: ISS Momentum Breakdown
        alerts.extend(await self.conditions.a03_iss_breakdown(calc_date))

        # A-04: Extreme Volume Spike
        alerts.extend(await self.conditions.a04_extreme_volume_spike(calc_date))

        # A-05: Critical Corporate Event
        alerts.extend(await self.conditions.a05_critical_corporate_event(calc_date))

        # A-06: Index Reconstitution (handled separately)
        # A-06 alert is triggered by data ingestion, not daily evaluation

        # A-07: Watchlist Large Move
        alerts.extend(await self.conditions.a07_watchlist_move(calc_date))

        # A-08: Market Breadth Stress
        alerts.extend(await self.conditions.a08_market_breadth(calc_date))

        # A-09: Multiple 52-Week Lows
        alerts.extend(await self.conditions.a09_multiple_52w_lows(calc_date))

        # A-10: Accumulation Volume Surge
        alerts.extend(await self.conditions.a10_accumulation_volume_surge(calc_date))

        # A-11: Promoter Pledging Change
        alerts.extend(await self.conditions.a11_promoter_pledging_change(calc_date))

        # A-12: Rating Downgrade
        alerts.extend(await self.conditions.a12_rating_downgrade(calc_date))

        # A-13: Breakout Near 52W High
        alerts.extend(await self.conditions.a13_breakout_near_52w_high(calc_date))

        # A-14: Sustained Volume Dryup
        alerts.extend(await self.conditions.a14_sustained_volume_dryup(calc_date))

        return alerts

    async def fire_alert(self, alert: Dict[str, Any]) -> Optional[str]:
        """Fire an alert by inserting it into the database.

        Args:
            alert: Alert details dict with keys:
                - alert_name: A-01 through A-14
                - symbol: Stock symbol, or None for market-wide
                - trigger_value: Context data (e.g., drawdown_pct)
                - description: Human-readable alert description
                - severity: Critical/High/Medium/Low

        Returns:
            alert_id if fired, None if deduplicated
        """
        alert_name = alert["alert_name"]
        symbol = alert.get("symbol")
        triggered_at = alert.get("triggered_at", date.today())

        # Check deduplication
        if not self.dedup.should_fire_alert(alert_name, symbol, triggered_at):
            return None

        # Generate dedup key for alert fatigue prevention
        dedup_key = f"{alert_name}-{symbol}" if symbol else alert_name

        # Insert into database
        engine = get_engine()
        alert_id = str(uuid4())

        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO alerts
                    (alert_id, alert_name, symbol, triggered_at,
                     trigger_value, severity, dedup_key, delivery_status)
                VALUES
                    (:alert_id, :alert_name, :symbol, :triggered_at,
                     :trigger_value, :severity, :dedup_key, :delivery_status)
            """), {
                "alert_id": alert_id,
                "alert_name": alert_name,
                "symbol": symbol,
                "triggered_at": triggered_at,
                "trigger_value": json.dumps(alert.get("trigger_value", {})),
                "severity": alert.get("severity", "Medium"),
                "dedup_key": dedup_key,
                "delivery_status": "Pending",
            })

        return alert_id

    async def fire_alerts(self, alerts: List[Dict[str, Any]]) -> List[Optional[str]]:
        """Fire multiple alerts.

        Args:
            alerts: List of alert dicts

        Returns:
            List of alert_ids (or None for deduplicated alerts)
        """
        return [await self.fire_alert(alert) for alert in alerts]


async def run_daily_alert_evaluation(calc_date: Optional[date] = None) -> List[Dict[str, Any]]:
    """Run daily alert evaluation and return results.

    Args:
        calc_date: Date to evaluate (defaults to today)

    Returns:
        List of fired alert details
    """
    if calc_date is None:
        calc_date = date.today()

    engine = AlertEngine()
    alerts = await engine.evaluate_all_alerts(calc_date)

    results = []
    for alert in alerts:
        alert_id = await engine.fire_alert(alert)
        results.append({
            "alert_id": alert_id,
            **alert,
        })

    return results
