"""Base notification adapter interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod


@dataclass
class NotificationResult:
    """Result of a notification send attempt."""

    success: bool
    message: str
    error: Optional[str] = None
    provider: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "error": self.error,
            "provider": self.provider,
        }


class BaseAdapter(ABC):
    """Abstract base class for notification adapters.

    All notification providers should inherit from this class
    and implement the send method.
    """

    name: str = "base"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    @abstractmethod
    async def send(self, alert: Dict[str, Any]) -> NotificationResult:
        """Send an alert notification.

        Args:
            alert: Alert dict with keys:
                - alert_name: A-01 through A-14
                - symbol: Stock symbol
                - severity: Critical/High/Medium/Low
                - description: Human-readable message
                - triggered_at: Timestamp

        Returns:
            NotificationResult indicating success/failure
        """
        raise NotImplementedError

    async def send_batch(
        self, alerts: list[Dict[str, Any]]
    ) -> list[NotificationResult]:
        """Send multiple alerts.

        Default implementation sends each individually.
        Override for batch optimization.
        """
        results = []
        for alert in alerts:
            result = await self.send(alert)
            results.append(result)
        return results

    def format_message(self, alert: Dict[str, Any]) -> str:
        """Format alert as a message string.

        Can be overridden for custom formatting.
        """
        severity_emoji = {
            "Critical": "🔴",
            "High": "🟠",
            "Medium": "🟡",
            "Low": "⚪",
        }

        emoji = severity_emoji.get(alert.get("severity", "Medium"), "⚪")
        msg = f"{emoji} *{alert['alert_name']}*"

        if alert.get("symbol"):
            msg += f" for *{alert['symbol']}*"

        msg += f"\n{alert.get('description', 'No description')}"

        return msg

    async def test_connection(self) -> NotificationResult:
        """Test the notification channel connection.

        Override in subclasses to verify credentials/connectivity.
        """
        return NotificationResult(
            success=True,
            message=f"{self.name} adapter initialized",
            provider=self.name,
        )


class MockAdapter(BaseAdapter):
    """Mock adapter for testing."""

    name: str = "mock"

    async def send(self, alert: Dict[str, Any]) -> NotificationResult:
        """Mock send - just log and return success."""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[MOCK] Would send {alert.get('alert_name')} to {alert.get('symbol')}")

        return NotificationResult(
            success=True,
            message=f"Mock notification sent for {alert.get('alert_name')}",
            provider=self.name,
        )