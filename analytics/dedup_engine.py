"""Alert deduplication engine - prevents alert fatigue.

For specific alert types (A-01, A-02, A-03, A-07), once an alert fires,
it won't re-fire for the same (symbol, alert_type) pair within 5 trading
days unless the condition resets.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from config.database import read_sql_df


# Alert types that have 5-day deduplication
DEDUP_ALERT_TYPES = {"A-01", "A-02", "A-03", "A-07"}

# Number of days to deduplicate
DEDUP_WINDOW_DAYS = 5


class DedupEngine:
    """Engine for alert deduplication logic."""

    def should_fire_alert(
        self,
        alert_name: str,
        symbol: Optional[str],
        calc_date: date,
    ) -> bool:
        """Check if an alert should fire given dedup rules.

        Args:
            alert_name: Alert identifier (A-01 through A-14)
            symbol: Stock symbol, or None for market-wide alerts
            calc_date: Date being evaluated

        Returns:
            True if alert should fire, False if deduplicated
        """
        if alert_name not in DEDUP_ALERT_TYPES:
            # No deduplication for this alert type
            return True

        if symbol is None:
            # Market-wide alerts don't use symbol-based dedup
            return True

        # Check if alert already fired for this (alert_name, symbol) recently
        recent_fires = self._get_recent_alert_fires(alert_name, symbol, calc_date)

        if recent_fires is None:
            # No previous fire - can fire now
            return True

        # Check if condition has reset (stock exited and re-entered threshold)
        if self._condition_reset(alert_name, symbol, recent_fires, calc_date):
            return True

        # Alert fired within dedup window - suppress
        return False

    def _get_recent_alert_fires(
        self,
        alert_name: str,
        symbol: str,
        calc_date: date,
    ) -> Optional[date]:
        """Get the most recent alert fire date for (alert_name, symbol).

        Returns:
            Date of most recent fire, or None if never fired
        """
        df = read_sql_df("""
            SELECT MAX(triggered_at) AS last_fire
            FROM alerts
            WHERE alert_name = :alert_name
              AND symbol = :symbol
              AND triggered_at >= :cutoff
        """, params={
            "alert_name": alert_name,
            "symbol": symbol,
            "cutoff": calc_date - timedelta(days=DEDUP_WINDOW_DAYS),
        })

        if df.empty or df.iloc[0]["last_fire"] is None:
            return None

        return df.iloc[0]["last_fire"].date()

    def _condition_reset(
        self,
        alert_name: str,
        symbol: str,
        last_fire_date: date,
        current_date: date,
    ) -> bool:
        """Check if the alert condition has reset since last fire.

        Args:
            alert_name: Alert identifier
            symbol: Stock symbol
            last_fire_date: When alert last fired
            current_date: Current evaluation date

        Returns:
            True if condition has reset, False otherwise
        """
        # Reload data to check current state
        df = read_sql_df("""
            SELECT *
            FROM mart_stock_signals
            WHERE calc_date = :calc_date
              AND symbol = :symbol
        """, params={"calc_date": current_date, "symbol": symbol})

        if df.empty:
            return False

        row = df.iloc[0]

        # Check each alert type's reset condition
        if alert_name == "A-01":
            # Deep drawdown - condition resets when stock exits < -20%
            return float(row.get("drawdown_from_52w_high_pct", 0)) >= -20

        elif alert_name == "A-02":
            # ISS breakout - condition resets when ISS drops below 70
            return float(row.get("iss_score", 0)) < 70

        elif alert_name == "A-03":
            # ISS breakdown - condition resets when ISS rises above 60
            return float(row.get("iss_score", 0)) > 60

        elif alert_name == "A-07":
            # Watchlist large move - condition resets when 1D return < 5%
            return abs(float(row.get("return_1d", 0))) < 0.05

        return True

    def record_alert_fired(
        self,
        alert_name: str,
        symbol: Optional[str],
        dedup_key: str,
        triggered_at: date,
    ) -> None:
        """Record that an alert was fired.

        Args:
            alert_name: Alert identifier
            symbol: Stock symbol, or None for market-wide alerts
            dedup_key: Unique key for deduplication (e.g., "A-01-RELIANCE")
            triggered_at: Date/time alert fired
        """
        # Insert is handled by alert_engine.fire_alert()
        # This method is a placeholder for future enhancements
        pass
