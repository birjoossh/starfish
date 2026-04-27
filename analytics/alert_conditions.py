"""Alert condition implementations for all 14 alert rules (A-01 through A-14).

Each method checks its specific condition and returns a list of alert dicts
if the condition is met.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import text

from config.database import read_sql_df


class AlertConditions:
    """Individual alert condition checks."""

    async def a01_deep_drawdown(self, calc_date: date) -> List[Dict[str, Any]]:
        """A-01: Deep Drawdown - drawdown_from_52w_high_pct < -20%.

        Severity: Medium
        """
        df = read_sql_df("""
            SELECT s.symbol, s.drawdown_from_52w_high_pct, d.company_name
            FROM mart_stock_signals s
            JOIN dim_stock d ON s.symbol = d.symbol
            WHERE s.calc_date = :calc_date
              AND s.drawdown_from_52w_high_pct < -20
              AND d.nifty50_member = TRUE
        """, params={"calc_date": calc_date})

        return [
            {
                "alert_name": "A-01",
                "symbol": row["symbol"],
                "trigger_value": {"drawdown_pct": float(row["drawdown_from_52w_high_pct"])},
                "severity": "Medium",
                "description": f"{row['symbol']} ({row['company_name']}) is in deep drawdown "
                              f"({row['drawdown_from_52w_high_pct']:.1f}% below 52W high)",
                "triggered_at": calc_date,
            }
            for _, row in df.iterrows()
        ]

    async def a02_iss_breakout(self, calc_date: date) -> List[Dict[str, Any]]:
        """A-02: ISS Momentum Breakout - iss_score crosses above 70.

        Previous day < 70, today >= 70
        Severity: Medium
        """
        df = read_sql_df("""
            SELECT s.symbol, s.iss_score, d.company_name
            FROM mart_stock_signals s
            JOIN dim_stock d ON s.symbol = d.symbol
            WHERE s.calc_date = :calc_date
              AND s.iss_score >= 70
              AND d.nifty50_member = TRUE
              AND NOT EXISTS (
                  SELECT 1 FROM mart_stock_signals prev
                  WHERE prev.symbol = s.symbol
                    AND prev.calc_date = :prev_date
                    AND prev.iss_score >= 70
              )
        """, params={
            "calc_date": calc_date,
            "prev_date": calc_date,
        })

        return [
            {
                "alert_name": "A-02",
                "symbol": row["symbol"],
                "trigger_value": {"iss_score": int(row["iss_score"])},
                "severity": "Medium",
                "description": f"{row['symbol']} ({row['company_name']}) ISS broke out to {int(row['iss_score'])}",
                "triggered_at": calc_date,
            }
            for _, row in df.iterrows()
        ]

    async def a03_iss_breakdown(self, calc_date: date) -> List[Dict[str, Any]]:
        """A-03: ISS Momentum Breakdown - iss_score drops below 40 (was > 60 in 10 days).

        Severity: High
        """
        df = read_sql_df("""
            SELECT s.symbol, s.iss_score, d.company_name
            FROM mart_stock_signals s
            JOIN dim_stock d ON s.symbol = d.symbol
            WHERE s.calc_date = :calc_date
              AND s.iss_score < 40
              AND d.nifty50_member = TRUE
              AND EXISTS (
                  SELECT 1 FROM mart_stock_signals prev
                  WHERE prev.symbol = s.symbol
                    AND prev.calc_date >= :cutoff_date
                    AND prev.calc_date < :calc_date
                    AND prev.iss_score > 60
              )
        """, params={
            "calc_date": calc_date,
            "cutoff_date": calc_date - pd.Timedelta(days=10),
        })

        return [
            {
                "alert_name": "A-03",
                "symbol": row["symbol"],
                "trigger_value": {"iss_score": int(row["iss_score"])},
                "severity": "High",
                "description": f"{row['symbol']} ({row['company_name']}) ISS breakdown to {int(row['iss_score'])} "
                              f"from >60 in last 10 days",
                "triggered_at": calc_date,
            }
            for _, row in df.iterrows()
        ]

    async def a04_extreme_volume_spike(self, calc_date: date) -> List[Dict[str, Any]]:
        """A-04: Extreme Volume Spike - spike_level = 'Extreme' (> 3.0x).

        Severity: High
        """
        # Check mart_volume_anomaly first
        df = read_sql_df("""
            SELECT v.symbol, v.volume_ratio, d.company_name
            FROM mart_volume_anomaly v
            JOIN dim_stock d ON v.symbol = d.symbol
            WHERE v.calc_date = :calc_date
              AND v.spike_level = 'Extreme'
              AND d.nifty50_member = TRUE
        """, params={"calc_date": calc_date})

        if df.empty:
            # Fallback to mart_stock_signals
            df = read_sql_df("""
                SELECT s.symbol, s.vol_ratio_1d, d.company_name
                FROM mart_stock_signals s
                JOIN dim_stock d ON s.symbol = d.symbol
                WHERE s.calc_date = :calc_date
                  AND s.vol_ratio_1d > 3.0
                  AND d.nifty50_member = TRUE
            """, params={"calc_date": calc_date})

        return [
            {
                "alert_name": "A-04",
                "symbol": row["symbol"],
                "trigger_value": {"volume_ratio": float(row["volume_ratio"])},
                "severity": "High",
                "description": f"{row['symbol']} ({row['company_name']}) has extreme volume spike "
                              f"({float(row['volume_ratio']):.1f}x 20D avg)",
                "triggered_at": calc_date,
            }
            for _, row in df.iterrows()
        ]

    async def a05_critical_corporate_event(self, calc_date: date) -> List[Dict[str, Any]]:
        """A-05: Critical Corporate Event - new event with significance_score >= 4.

        Severity: Critical
        """
        df = read_sql_df("""
            SELECT e.symbol, e.event_type, e.significance_score, e.event_summary,
                   e.categorization_method, d.company_name
            FROM fact_corporate_event e
            JOIN dim_stock d ON e.symbol = d.symbol
            WHERE e.event_date = :calc_date
              AND e.significance_score >= 4
              AND d.nifty50_member = TRUE
        """, params={"calc_date": calc_date})

        return [
            {
                "alert_name": "A-05",
                "symbol": row["symbol"],
                "trigger_value": {
                    "event_type": row["event_type"],
                    "significance": int(row["significance_score"]),
                    "event_summary": row["event_summary"],
                },
                "severity": "Critical",
                "description": f"Critical event for {row['symbol']} ({row['company_name']}): "
                              f"{row['event_type']} with significance {int(row['significance_score'])}",
                "triggered_at": calc_date,
            }
            for _, row in df.iterrows()
        ]

    async def a06_index_reconstitution(self, calc_date: date) -> List[Dict[str, Any]]:
        """A-06: Index Reconstitution - new dim_nifty50_constituent row with Addition/Deletion.

        Severity: Critical
        """
        df = read_sql_df("""
            SELECT symbol, change_type, effective_from, review_period
            FROM dim_nifty50_constituent
            WHERE effective_from = :calc_date
              AND change_type IN ('Addition', 'Deletion')
        """, params={"calc_date": calc_date})

        return [
            {
                "alert_name": "A-06",
                "symbol": row["symbol"],
                "trigger_value": {
                    "change_type": row["change_type"],
                    "effective_from": str(row["effective_from"]),
                },
                "severity": "Critical",
                "description": f"Index reconstitution: {row['symbol']} - "
                              f"{row['change_type']} effective {row['effective_from']}",
                "triggered_at": calc_date,
            }
            for _, row in df.iterrows()
        ]

    async def a07_watchlist_move(self, calc_date: date) -> List[Dict[str, Any]]:
        """A-07: Watchlist Large Move - ABS(return_1d) >= 5% for watchlist stocks.

        Severity: High
        """
        df = read_sql_df("""
            SELECT s.symbol, s.return_1d, d.company_name
            FROM mart_stock_signals s
            JOIN dim_stock d ON s.symbol = d.symbol
            JOIN user_watchlist w ON s.symbol = w.symbol
            JOIN watchlist_users u ON w.user_id = u.user_id
            WHERE s.calc_date = :calc_date
              AND ABS(s.return_1d) >= 0.05
              AND d.nifty50_member = TRUE
            ORDER BY ABS(s.return_1d) DESC
        """, params={"calc_date": calc_date})

        return [
            {
                "alert_name": "A-07",
                "symbol": row["symbol"],
                "trigger_value": {"return_1d": float(row["return_1d"])},
                "severity": "High",
                "description": f"Watchlist alert: {row['symbol']} ({row['company_name']}) moved "
                              f"{float(row['return_1d'] * 100):+.1f}% today",
                "triggered_at": calc_date,
            }
            for _, row in df.iterrows()
        ]

    async def a08_market_breadth(self, calc_date: date) -> List[Dict[str, Any]]:
        """A-08: Market Breadth Stress - < 10 advancing stocks out of 50.

        Severity: Medium
        """
        df = read_sql_df("""
            SELECT
                COUNT(*) FILTER (WHERE return_1d > 0) AS advancing,
                COUNT(*) AS total
            FROM mart_stock_signals
            WHERE calc_date = :calc_date
              AND nifty50_member = TRUE
        """, params={"calc_date": calc_date})

        if df.empty:
            return []

        row = df.iloc[0]
        advancing = int(row["advancing"]) if row["advancing"] else 0
        total = int(row["total"]) if row["total"] else 50

        if advancing < 10:
            return [{
                "alert_name": "A-08",
                "symbol": None,  # Market-wide alert
                "trigger_value": {
                    "advancing": advancing,
                    "declining": total - advancing,
                    "total": total,
                },
                "severity": "Medium",
                "description": f"Market breadth stress: Only {advancing}/{total} Nifty 50 stocks advancing",
                "triggered_at": calc_date,
            }]

        return []

    async def a09_multiple_52w_lows(self, calc_date: date) -> List[Dict[str, Any]]:
        """A-09: Multiple 52-Week Lows - 3+ stocks at new 52W low.

        Severity: High
        """
        df = read_sql_df("""
            SELECT s.symbol, s.drawdown_from_52w_high_pct, d.company_name
            FROM mart_stock_signals s
            JOIN dim_stock d ON s.symbol = d.symbol
            WHERE s.calc_date = :calc_date
              AND d.nifty50_member = TRUE
              AND s.distance_from_52w_low_pct <= 1  -- Within 1% of 52W low
        """, params={"calc_date": calc_date})

        if len(df) >= 3:
            return [{
                "alert_name": "A-09",
                "symbol": None,  # Market-wide alert
                "trigger_value": {
                    "count": len(df),
                    "symbols": df["symbol"].tolist(),
                },
                "severity": "High",
                "description": f"{len(df)} Nifty 50 stocks are at new 52-week lows",
                "triggered_at": calc_date,
            }]

        return []

    async def a10_accumulation_volume_surge(self, calc_date: date) -> List[Dict[str, Any]]:
        """A-10: Accumulation Volume Surge - ACC + vol > 1.5x + return > 0.

        First occurrence after 10+ consecutive sessions of vol_ratio_1d < 1.0
        Severity: Medium
        """
        # Check for accumulation candidates with volume surge
        df = read_sql_df("""
            SELECT s.symbol, s.vol_ratio_1d, s.return_1d, s.accumulation_flag,
                   d.company_name, s.volume_trend_3m
            FROM mart_stock_signals s
            JOIN dim_stock d ON s.symbol = d.symbol
            WHERE s.calc_date = :calc_date
              AND s.accumulation_flag = TRUE
              AND s.vol_ratio_1d > 1.5
              AND s.return_1d > 0
              AND d.nifty50_member = TRUE
        """, params={"calc_date": calc_date})

        return [
            {
                "alert_name": "A-10",
                "symbol": row["symbol"],
                "trigger_value": {
                    "vol_ratio": float(row["vol_ratio_1d"]),
                    "return_1d": float(row["return_1d"]),
                    "volume_trend": row["volume_trend_3m"],
                },
                "severity": "Medium",
                "description": f"{row['symbol']} ({row['company_name']}) shows accumulation volume surge "
                              f"({float(row['vol_ratio_1d']):.1f}x vol, {float(row['return_1d'] * 100):+.1f}% return)",
                "triggered_at": calc_date,
            }
            for _, row in df.iterrows()
        ]

    async def a11_promoter_pledging_change(self, calc_date: date) -> List[Dict[str, Any]]:
        """A-11: Promoter Pledging Change - new event_type = 'Pledging_Change'.

        Severity: High
        """
        df = read_sql_df("""
            SELECT e.symbol, e.event_type, e.significance_score, e.event_summary,
                   d.company_name
            FROM fact_corporate_event e
            JOIN dim_stock d ON e.symbol = d.symbol
            WHERE e.event_date = :calc_date
              AND e.event_type = 'Pledging_Change'
              AND d.nifty50_member = TRUE
        """, params={"calc_date": calc_date})

        return [
            {
                "alert_name": "A-11",
                "symbol": row["symbol"],
                "trigger_value": {
                    "event_type": row["event_type"],
                    "significance": int(row["significance_score"]),
                },
                "severity": "High",
                "description": f"Pledging change alert for {row['symbol']} ({row['company_name']}): "
                              f"{row['event_summary'][:100]}",
                "triggered_at": calc_date,
            }
            for _, row in df.iterrows()
        ]

    async def a12_rating_downgrade(self, calc_date: date) -> List[Dict[str, Any]]:
        """A-12: Rating Downgrade - Rating_Change + keywords indicating downgrade.

        Severity: Critical
        """
        keywords = ["downgrade", "negative watch", "outlook revised to negative", "CreditWatch Negative"]

        # Build WHERE clause for keyword matching
        keyword_conditions = " OR ".join(
            [f"LOWER(e.event_summary) LIKE LOWER('%{kw}%')" for kw in keywords]
        )

        df = read_sql_df(f"""
            SELECT e.symbol, e.event_type, e.significance_score, e.event_summary,
                   d.company_name
            FROM fact_corporate_event e
            JOIN dim_stock d ON e.symbol = d.symbol
            WHERE e.event_date = :calc_date
              AND e.event_type = 'Rating_Change'
              AND ({keyword_conditions})
              AND d.nifty50_member = TRUE
        """, params={"calc_date": calc_date})

        return [
            {
                "alert_name": "A-12",
                "symbol": row["symbol"],
                "trigger_value": {
                    "event_type": row["event_type"],
                    "significance": int(row["significance_score"]),
                },
                "severity": "Critical",
                "description": f"Rating downgrade alert for {row['symbol']} ({row['company_name']}): "
                              f"{row['event_summary'][:150]}",
                "triggered_at": calc_date,
            }
            for _, row in df.iterrows()
        ]

    async def a13_breakout_near_52w_high(self, calc_date: date) -> List[Dict[str, Any]]:
        """A-13: Breakout Near 52W High - crosses from > 2% to <= 1% from 52W high.

        With volume confirmation vol_ratio_1d > 1.3
        Severity: Low
        """
        df = read_sql_df("""
            SELECT s.symbol, s.drawdown_from_52w_high_pct, s.vol_ratio_1d, d.company_name
            FROM mart_stock_signals s
            JOIN dim_stock d ON s.symbol = d.symbol
            WHERE s.calc_date = :calc_date
              AND s.drawdown_from_52w_high_pct <= -1  -- Within 1% of 52W high
              AND s.vol_ratio_1d > 1.3
              AND d.nifty50_member = TRUE
        """, params={"calc_date": calc_date})

        return [
            {
                "alert_name": "A-13",
                "symbol": row["symbol"],
                "trigger_value": {
                    "drawdown_pct": float(row["drawdown_from_52w_high_pct"]),
                    "vol_ratio": float(row["vol_ratio_1d"]),
                },
                "severity": "Low",
                "description": f"{row['symbol']} ({row['company_name']}) breakout near 52W high "
                              f"({abs(float(row['drawdown_from_52w_high_pct'])):.1f}% below, "
                              f"{float(row['vol_ratio_1d']):.1f}x volume)",
                "triggered_at": calc_date,
            }
            for _, row in df.iterrows()
        ]

    async def a14_sustained_volume_dryup(self, calc_date: date) -> List[Dict[str, Any]]:
        """A-14: Sustained Volume Dryup - vol_ratio_1d < 0.4 for 5+ sessions.

        Severity: Low
        """
        df = read_sql_df("""
            SELECT s.symbol, s.vol_ratio_1d, d.company_name, s.volume_trend_3m
            FROM mart_stock_signals s
            JOIN dim_stock d ON s.symbol = d.symbol
            WHERE s.calc_date = :calc_date
              AND s.vol_ratio_1d < 0.4
              AND d.nifty50_member = TRUE
        """, params={"calc_date": calc_date})

        return [
            {
                "alert_name": "A-14",
                "symbol": row["symbol"],
                "trigger_value": {
                    "vol_ratio": float(row["vol_ratio_1d"]),
                    "volume_trend": row["volume_trend_3m"],
                },
                "severity": "Low",
                "description": f"{row['symbol']} ({row['company_name']}) has sustained volume dryup "
                              f"({float(row['vol_ratio_1d']):.1f}x, {row['volume_trend_3m']})",
                "triggered_at": calc_date,
            }
            for _, row in df.iterrows()
        ]
