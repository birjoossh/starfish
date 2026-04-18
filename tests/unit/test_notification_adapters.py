"""Unit tests for notification adapters."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from alerts.notification_adapters.base import BaseAdapter, MockAdapter, NotificationResult
from alerts.notification_adapters.email_sender import EmailAdapter
from alerts.notification_adapters.slack_sender import SlackAdapter
from alerts.notification_adapters.dashboard_notifier import DashboardAdapter


class TestNotificationResult:
    """Test NotificationResult dataclass."""

    def test_to_dict(self):
        result = NotificationResult(
            success=True,
            message="Test message",
            error=None,
            provider="test",
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["message"] == "Test message"
        assert d["provider"] == "test"


class TestMockAdapter:
    """Test mock notification adapter."""

    @pytest.mark.asyncio
    async def test_send_returns_success(self):
        adapter = MockAdapter()
        alert = {"alert_name": "A-01", "symbol": "RELIANCE", "description": "Test alert"}

        result = await adapter.send(alert)

        assert result.success is True
        assert "Mock notification" in result.message


class TestEmailAdapter:
    """Test email notification adapter."""

    def test_initialization(self):
        config = {
            "smtp_host": "smtp.test.com",
            "smtp_port": 587,
            "smtp_user": "test@test.com",
            "smtp_password": "password",
            "from_email": "test@test.com",
            "to_emails": ["user@test.com"],
        }
        adapter = EmailAdapter(config)

        assert adapter.smtp_host == "smtp.test.com"
        assert adapter.smtp_port == 587
        assert adapter.to_emails == ["user@test.com"]

    def test_format_subject(self):
        adapter = EmailAdapter()
        alert = {"alert_name": "A-01", "symbol": "RELIANCE", "severity": "High"}

        subject = adapter._format_subject(alert)

        assert "A-01" in subject
        assert "RELIANCE" in subject
        assert "[High]" in subject

    def test_format_plain_text(self):
        adapter = EmailAdapter()
        alert = {
            "alert_name": "A-01",
            "symbol": "RELIANCE",
            "severity": "Medium",
            "description": "Test description",
            "triggered_at": "2024-01-17",
            "trigger_value": {"drawdown_pct": -25.0},
        }

        body = adapter._format_plain_text(alert)

        assert "A-01" in body
        assert "RELIANCE" in body
        assert "Test description" in body
        assert "drawdown_pct" in body

    @pytest.mark.asyncio
    async def test_send_without_credentials_logs(self):
        adapter = EmailAdapter({})
        alert = {"alert_name": "A-01", "symbol": "RELIANCE", "description": "Test"}

        result = await adapter.send(alert)

        assert result.success is True
        assert "not configured" in result.message.lower()

    @pytest.mark.asyncio
    async def test_send_without_recipients_fails(self):
        adapter = EmailAdapter({
            "smtp_user": "test@test.com",
            "smtp_password": "password",
            "to_emails": [],
        })
        alert = {"alert_name": "A-01", "symbol": "RELIANCE"}

        result = await adapter.send(alert)

        assert result.success is False
        assert "recipient" in result.message.lower()


class TestSlackAdapter:
    """Test Slack notification adapter."""

    def test_initialization(self):
        adapter = SlackAdapter({"slack_webhook_url": "https://hooks.slack.com/test"})
        assert adapter.webhook_url == "https://hooks.slack.com/test"

    def test_build_payload(self):
        adapter = SlackAdapter()
        alert = {
            "alert_name": "A-01",
            "symbol": "RELIANCE",
            "severity": "High",
            "description": "Test alert",
            "triggered_at": "2024-01-17",
            "trigger_value": {"drawdown_pct": -25.0},
        }

        payload = adapter._build_payload(alert)

        assert "attachments" in payload
        assert len(payload["attachments"]) == 1
        assert payload["attachments"][0]["color"] == "#ea580c"  # High = orange

    @pytest.mark.asyncio
    async def test_send_without_webhook_logs(self):
        adapter = SlackAdapter({})
        alert = {"alert_name": "A-01", "symbol": "RELIANCE", "description": "Test"}

        result = await adapter.send(alert)

        assert result.success is True
        assert "not configured" in result.message.lower()


class TestDashboardAdapter:
    """Test dashboard notification adapter."""

    def test_initialization(self):
        adapter = DashboardAdapter({"max_stored_alerts": 50})
        assert adapter.max_stored_alerts == 50
        assert adapter.engine is not None

    @pytest.mark.asyncio
    async def test_send_without_alert_id(self):
        adapter = DashboardAdapter()
        alert = {
            "alert_name": "A-01",
            "symbol": "RELIANCE",
            "description": "Test",
            # No alert_id - just tests the code path
        }

        result = await adapter.send(alert)

        assert result.success is True
        assert "dashboard" in result.message.lower()

    @pytest.mark.asyncio
    async def test_get_alert_counts(self):
        adapter = DashboardAdapter()

        counts = await adapter.get_alert_counts()

        assert isinstance(counts, dict)
        assert "total" in counts
        assert "pending" in counts
        assert "sent" in counts

    @pytest.mark.asyncio
    async def test_mark_as_read_empty_list(self):
        adapter = DashboardAdapter()

        count = await adapter.mark_as_read([])

        assert count == 0