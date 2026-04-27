"""Dashboard notification adapter.

Stores alerts in database for dashboard polling/display.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from sqlalchemy import text

from alerts.notification_adapters.base import BaseAdapter, NotificationResult
from config.database import get_engine

logger = logging.getLogger(__name__)


class DashboardAdapter(BaseAdapter):
    """Dashboard notification adapter - stores for UI display."""

    name: str = "dashboard"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.engine = get_engine()
        self.max_stored_alerts = self.config.get("max_stored_alerts", 100)

    def _update_delivery_status(self, alert: Dict[str, Any], status: str) -> None:
        """Update alert delivery status in database."""
        alert_id = alert.get("alert_id")
        if not alert_id:
            return

        # Validate UUID format
        import uuid
        try:
            uuid.UUID(alert_id)
        except (ValueError, TypeError):
            logger.debug(f"Invalid alert_id format: {alert_id}")
            return

        with self.engine.connect() as conn:
            conn.execute(text("""
                UPDATE alerts
                SET delivery_status = :status
                WHERE alert_id = :alert_id
            """), {"status": status, "alert_id": alert_id})
            conn.commit()

    async def send(self, alert: Dict[str, Any]) -> NotificationResult:
        """Store alert in database for dashboard display."""
        alert_id = alert.get("alert_id")

        if not alert_id:
            # Try to find the alert by dedup key
            dedup_key = f"{alert['alert_name']}-{alert.get('symbol')}"
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT alert_id FROM alerts
                    WHERE dedup_key = :dedup_key
                    ORDER BY triggered_at DESC
                    LIMIT 1
                """), {"dedup_key": dedup_key})
                row = result.fetchone()
                if row:
                    alert_id = row.alert_id
                    alert["alert_id"] = alert_id

        if alert_id:
            self._update_delivery_status(alert, "Sent")
            logger.debug(f"Dashboard notification stored for {alert['alert_name']}")

        return NotificationResult(
            success=True,
            message="Alert stored for dashboard display",
            provider=self.name,
        )

    async def get_unread_alerts(
        self,
        user_id: Optional[int] = None,
        since: Optional[datetime] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get unread alerts for dashboard polling.

        Args:
            user_id: Filter by user (optional)
            since: Get alerts since this time (default: last hour)
            limit: Max number of alerts to return

        Returns:
            List of alert dicts
        """
        if since is None:
            since = datetime.now() - timedelta(hours=1)

        query = """
            SELECT alert_id, alert_name, symbol, triggered_at,
                   trigger_value, severity, description, delivery_status
            FROM alerts
            WHERE triggered_at >= :since
        """
        params = {"since": since}

        if user_id:
            query += " AND :user_id = ANY(user_ids_to_notify)"
            params["user_id"] = user_id

        query += " ORDER BY triggered_at DESC LIMIT :limit"
        params["limit"] = limit

        with self.engine.connect() as conn:
            result = conn.execute(text(query), params)
            rows = result.fetchall()

        alerts = []
        for row in rows:
            alerts.append({
                "alert_id": row.alert_id,
                "alert_name": row.alert_name,
                "symbol": row.symbol,
                "triggered_at": row.triggered_at.isoformat() if row.triggered_at else None,
                "trigger_value": row.trigger_value,
                "severity": row.severity,
                "description": row.description,
                "delivery_status": row.delivery_status,
                "read": row.delivery_status != "Pending",
            })

        return alerts

    async def mark_as_read(
        self,
        alert_ids: List[str],
        user_id: Optional[int] = None,
    ) -> int:
        """Mark alerts as read.

        Args:
            alert_ids: List of alert IDs to mark as read
            user_id: User marking as read (for audit)

        Returns:
            Number of alerts marked as read
        """
        if not alert_ids:
            return 0

        with self.engine.connect() as conn:
            result = conn.execute(text("""
                UPDATE alerts
                SET delivery_status = 'Sent'
                WHERE alert_id = ANY(:alert_ids)
                AND delivery_status = 'Pending'
                RETURNING alert_id
            """), {"alert_ids": alert_ids})
            conn.commit()
            rows = result.fetchall()

        return len(rows)

    async def get_alert_counts(self) -> Dict[str, int]:
        """Get count of alerts by status."""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT delivery_status, COUNT(*) as cnt
                FROM alerts
                WHERE triggered_at >= NOW() - INTERVAL '24 hours'
                GROUP BY delivery_status
            """))
            rows = result.fetchall()

        counts = {"total": 0, "pending": 0, "sent": 0, "failed": 0}
        for row in rows:
            status = row.delivery_status.lower()
            if status in counts:
                counts[status] = row.cnt
            counts["total"] += row.cnt

        return counts

    async def test_connection(self) -> NotificationResult:
        """Test database connectivity."""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            return NotificationResult(
                success=True,
                message="Database connection OK",
                provider=self.name,
            )

        except Exception as e:
            return NotificationResult(
                success=False,
                message="Database connection failed",
                error=str(e),
                provider=self.name,
            )