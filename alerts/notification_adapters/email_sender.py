"""Email notification adapter.

Sends alerts via SMTP email.
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional

from alerts.notification_adapters.base import BaseAdapter, NotificationResult

logger = logging.getLogger(__name__)


class EmailAdapter(BaseAdapter):
    """Email notification adapter using SMTP."""

    name: str = "email"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.smtp_host = self.config.get("smtp_host", "smtp.gmail.com")
        self.smtp_port = self.config.get("smtp_port", 587)
        self.smtp_user = self.config.get("smtp_user", "")
        self.smtp_password = self.config.get("smtp_password", "")
        self.from_email = self.config.get("from_email", self.smtp_user)
        self.to_emails = self.config.get("to_emails", [])

        if not self.smtp_user or not self.smtp_password:
            logger.warning("Email adapter missing credentials - will only log")

    def _build_email(self, alert: Dict[str, Any]) -> MIMEMultipart:
        """Build MIME email message from alert."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = self._format_subject(alert)
        msg["From"] = self.from_email
        msg["To"] = ", ".join(self.to_emails)

        # Plain text version
        text_body = self._format_plain_text(alert)
        msg.attach(MIMEText(text_body, "plain"))

        # HTML version
        html_body = self._format_html(alert)
        msg.attach(MIMEText(html_body, "html"))

        return msg

    def _format_subject(self, alert: Dict[str, Any]) -> str:
        """Format email subject line."""
        severity = alert.get("severity", "Medium")
        symbol = alert.get("symbol", "MARKET")

        return f"[{severity}] {alert['alert_name']} - {symbol}"

    def _format_plain_text(self, alert: Dict[str, Any]) -> str:
        """Format plain text email body."""
        lines = [
            f"Alert: {alert['alert_name']}",
            f"Severity: {alert.get('severity', 'Medium')}",
            "",
        ]

        if alert.get("symbol"):
            lines.append(f"Symbol: {alert['symbol']}")

        lines.extend([
            "",
            "Description:",
            alert.get("description", "No description"),
            "",
            f"Triggered: {alert.get('triggered_at', 'Unknown')}",
        ])

        trigger_value = alert.get("trigger_value")
        if trigger_value:
            lines.append("")
            lines.append("Details:")
            for key, value in trigger_value.items():
                lines.append(f"  {key}: {value}")

        return "\n".join(lines)

    def _format_html(self, alert: Dict[str, Any]) -> str:
        """Format HTML email body."""
        severity_colors = {
            "Critical": "#dc2626",
            "High": "#ea580c",
            "Medium": "#ca8a04",
            "Low": "#6b7280",
        }
        color = severity_colors.get(alert.get("severity", "Medium"), "#6b7280")

        html = f"""
        <html>
        <body>
            <div style="font-family: Arial, sans-serif; max-width: 600px;">
                <div style="background: {color}; color: white; padding: 12px; border-radius: 4px;">
                    <h2 style="margin: 0;">{alert['alert_name']}</h2>
                    <p style="margin: 4px 0 0 0;">Severity: {alert.get('severity', 'Medium')}</p>
                </div>

                <div style="padding: 16px; background: #f9fafb; border-radius: 4px; margin-top: 16px;">
        """

        if alert.get("symbol"):
            html += f'<p><strong>Symbol:</strong> {alert["symbol"]}</p>'

        html += f"""
                    <p><strong>Description:</strong><br>{alert.get('description', 'No description')}</p>

                    <p><strong>Triggered:</strong> {alert.get('triggered_at', 'Unknown')}</p>
        """

        trigger_value = alert.get("trigger_value")
        if trigger_value:
            html += "<p><strong>Details:</strong></p><ul>"
            for key, value in trigger_value.items():
                html += f"<li>{key}: {value}</li>"
            html += "</ul>"

        html += """
                </div>
            </div>
        </body>
        </html>
        """

        return html

    async def send(self, alert: Dict[str, Any]) -> NotificationResult:
        """Send alert via email."""
        if not self.smtp_user or not self.smtp_password:
            logger.info(f"[EMAIL] {alert['alert_name']} for {alert.get('symbol')}: {alert.get('description', '')[:100]}")
            return NotificationResult(
                success=True,
                message="Email not configured - logged instead",
                provider=self.name,
            )

        if not self.to_emails:
            return NotificationResult(
                success=False,
                message="No recipient emails configured",
                error="Missing to_emails",
                provider=self.name,
            )

        try:
            msg = self._build_email(alert)

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent for {alert['alert_name']} to {self.to_emails}")

            return NotificationResult(
                success=True,
                message=f"Email sent to {len(self.to_emails)} recipients",
                provider=self.name,
            )

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP auth error: {e}")
            return NotificationResult(
                success=False,
                message="Failed to send email",
                error=f"SMTP auth error: {e}",
                provider=self.name,
            )

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return NotificationResult(
                success=False,
                message="Failed to send email",
                error=str(e),
                provider=self.name,
            )

    async def test_connection(self) -> NotificationResult:
        """Test SMTP connection."""
        if not self.smtp_user or not self.smtp_password:
            return NotificationResult(
                success=False,
                message="SMTP credentials not configured",
                provider=self.name,
            )

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)

            return NotificationResult(
                success=True,
                message="SMTP connection successful",
                provider=self.name,
            )

        except Exception as e:
            return NotificationResult(
                success=False,
                message="SMTP connection failed",
                error=str(e),
                provider=self.name,
            )