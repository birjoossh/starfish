"""Alert notification adapters.

Base classes and implementations for sending alerts via various channels.
"""

from alerts.notification_adapters.base import BaseAdapter, NotificationResult
from alerts.notification_adapters.email_sender import EmailAdapter
from alerts.notification_adapters.slack_sender import SlackAdapter
from alerts.notification_adapters.dashboard_notifier import DashboardAdapter

__all__ = [
    "BaseAdapter",
    "NotificationResult",
    "EmailAdapter",
    "SlackAdapter",
    "DashboardAdapter",
]