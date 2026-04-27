"""Slack notification adapter.

Sends alerts via Slack webhook.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from alerts.notification_adapters.base import BaseAdapter, NotificationResult

logger = logging.getLogger(__name__)


class SlackAdapter(BaseAdapter):
    """Slack notification adapter using Incoming Webhooks."""

    name: str = "slack"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.webhook_url = self.config.get("slack_webhook_url", "")

        if not self.webhook_url:
            logger.warning("Slack adapter missing webhook URL - will only log")

    def _build_payload(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """Build Slack message payload."""
        severity_colors = {
            "Critical": "#dc2626",
            "High": "#ea580c",
            "Medium": "#ca8a04",
            "Low": "#6b7280",
        }

        color = severity_colors.get(alert.get("severity", "Medium"), "#6b7280")

        fields = [
            {"title": "Alert", "value": alert.get("alert_name", "Unknown"), "short": True},
            {"title": "Severity", "value": alert.get("severity", "Medium"), "short": True},
        ]

        if alert.get("symbol"):
            fields.append({"title": "Symbol", "value": alert["symbol"], "short": True})

        trigger_value = alert.get("trigger_value")
        if trigger_value:
            for key, value in list(trigger_value.items())[:3]:
                fields.append({
                    "title": key.replace("_", " ").title(),
                    "value": str(value)[:50],
                    "short": True
                })

        return {
            "attachments": [{
                "color": color,
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"🚨 {alert.get('alert_name', 'Alert')}",
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": alert.get("description", "No description")
                        }
                    },
                    {
                        "type": "section",
                        "fields": fields
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"Triggered: {alert.get('triggered_at', 'Unknown')}"
                            }
                        ]
                    }
                ]
            }]
        }

    async def send(self, alert: Dict[str, Any]) -> NotificationResult:
        """Send alert to Slack."""
        if not self.webhook_url:
            logger.info(f"[SLACK] {alert['alert_name']} for {alert.get('symbol')}: {alert.get('description', '')[:100]}")
            return NotificationResult(
                success=True,
                message="Slack webhook not configured - logged instead",
                provider=self.name,
            )

        try:
            payload = self._build_payload(alert)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10.0,
                )
                response.raise_for_status()

            logger.info(f"Slack notification sent for {alert['alert_name']}")

            return NotificationResult(
                success=True,
                message="Slack notification sent",
                provider=self.name,
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"Slack webhook error: {e.response.status_code}")
            return NotificationResult(
                success=False,
                message="Failed to send Slack notification",
                error=f"HTTP {e.response.status_code}",
                provider=self.name,
            )

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return NotificationResult(
                success=False,
                message="Failed to send Slack notification",
                error=str(e),
                provider=self.name,
            )

    async def test_connection(self) -> NotificationResult:
        """Test Slack webhook."""
        if not self.webhook_url:
            return NotificationResult(
                success=False,
                message="Slack webhook URL not configured",
                provider=self.name,
            )

        test_alert = {
            "alert_name": "TEST",
            "symbol": "TEST",
            "severity": "Low",
            "description": "Test notification from Starfish dashboard",
            "triggered_at": "Now",
            "trigger_value": {},
        }

        return await self.send(test_alert)