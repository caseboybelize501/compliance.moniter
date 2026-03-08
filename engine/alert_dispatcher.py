"""
Alert Dispatcher for ACMP.

Sends violation alerts via WhatsApp, Slack, or Microsoft Teams.
Configurable provider with user-provided credentials.
"""
import logging
from typing import Any
from datetime import datetime

import httpx

from server.models.violation import Violation


logger = logging.getLogger(__name__)


class AlertDispatcherError(Exception):
    """Base exception for alert dispatcher errors."""
    pass


class AlertDispatcher:
    """
    Dispatches alerts via multiple messaging providers.
    
    Supported providers:
    - WhatsApp (via Twilio) - default
    - Slack
    - Microsoft Teams
    """
    
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.provider = self.config.get("messaging_provider", "whatsapp")
        self._http_client: httpx.AsyncClient | None = None
        
        # Provider-specific config
        self.twilio_config = {
            "account_sid": self.config.get("twilio_account_sid"),
            "auth_token": self.config.get("twilio_auth_token"),
            "whatsapp_number": self.config.get("twilio_whatsapp_number", "whatsapp:+14155238886"),
        }
        
        self.slack_config = {
            "bot_token": self.config.get("slack_bot_token"),
        }
        
        self.teams_config = {
            "webhook_url": self.config.get("teams_webhook_url"),
        }
    
    async def send_alert(self, violation: Violation, recipients: list[str] | None = None) -> bool:
        """
        Send alert for a violation.
        
        Args:
            violation: Violation to alert on.
            recipients: Optional list of recipient phone numbers/emails.
            
        Returns:
            True if alert sent successfully.
        """
        message = self._format_alert_message(violation)
        
        try:
            if self.provider == "whatsapp":
                return await self._send_whatsapp(message, recipients)
            elif self.provider == "slack":
                return await self._send_slack(message, violation)
            elif self.provider == "teams":
                return await self._send_teams(message, violation)
            else:
                logger.warning(f"Unknown messaging provider: {self.provider}")
                return False
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False
    
    def _format_alert_message(self, violation: Violation) -> str:
        """Format violation into alert message."""
        severity_emoji = {
            "LOW": "🟢",
            "MEDIUM": "🟡",
            "HIGH": "🟠",
            "CRITICAL": "🔴"
        }
        
        emoji = severity_emoji.get(violation.severity, "⚪")
        
        return f"""{emoji} *Compliance Alert*

*Control:* {violation.control_id}
*Severity:* {violation.severity}
*Description:* {violation.description}
*Opened:* {violation.opened_at.strftime('%Y-%m-%d %H:%M')}
*Age:* {violation.age_days} days

Review in ACMP dashboard for remediation steps."""
    
    async def _send_whatsapp(self, message: str, recipients: list[str] | None = None) -> bool:
        """
        Send WhatsApp message via Twilio.
        
        Args:
            message: Message text.
            recipients: List of phone numbers (with country code).
        """
        if not self.twilio_config["account_sid"] or not self.twilio_config["auth_token"]:
            logger.warning("Twilio credentials not configured")
            return False
        
        # Default recipient (would come from tenant config in production)
        if not recipients:
            logger.warning("No recipients specified for WhatsApp alert")
            return False
        
        client = self._get_http_client()
        
        for recipient in recipients:
            try:
                response = await client.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_config['account_sid']}/Messages.json",
                    data={
                        "From": self.twilio_config["whatsapp_number"],
                        "To": f"whatsapp:{recipient}",
                        "Body": message,
                    },
                    auth=(self.twilio_config["account_sid"], self.twilio_config["auth_token"])
                )
                
                if response.status_code == 201:
                    logger.info(f"WhatsApp alert sent to {recipient}")
                else:
                    logger.error(f"Twilio API error: {response.text}")
                    
            except Exception as e:
                logger.error(f"Failed to send WhatsApp to {recipient}: {e}")
        
        return True
    
    async def _send_slack(self, message: str, violation: Violation) -> bool:
        """
        Send Slack message.
        
        Args:
            message: Message text.
            violation: Violation context.
        """
        if not self.slack_config["bot_token"]:
            logger.warning("Slack bot token not configured")
            return False
        
        client = self._get_http_client()
        
        # Format as Slack block message
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🚨 Compliance Alert: {violation.severity}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Control:*\n{violation.control_id}"},
                    {"type": "mrkdwn", "text": f"*Severity:*\n{violation.severity}"},
                    {"type": "mrkdwn", "text": f"*Age:*\n{violation.age_days} days"},
                    {"type": "mrkdwn", "text": f"*Status:*\n{violation.status}"}
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": violation.description
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View in Dashboard"},
                        "url": "http://localhost:3000/violations"
                    }
                ]
            }
        ]
        
        try:
            response = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {self.slack_config['bot_token']}"},
                json={
                    "channel": "#compliance-alerts",
                    "blocks": blocks
                }
            )
            
            result = response.json()
            if result.get("ok"):
                logger.info("Slack alert sent")
                return True
            else:
                logger.error(f"Slack API error: {result.get('error')}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False
    
    async def _send_teams(self, message: str, violation: Violation) -> bool:
        """
        Send Microsoft Teams message via webhook.
        
        Args:
            message: Message text.
            violation: Violation context.
        """
        if not self.teams_config["webhook_url"]:
            logger.warning("Teams webhook URL not configured")
            return False
        
        client = self._get_http_client()
        
        # Format as Teams Adaptive Card
        card = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": self._get_severity_color(violation.severity),
            "summary": f"Compliance Alert: {violation.control_id}",
            "sections": [
                {
                    "activityTitle": f"🚨 Compliance Alert - {violation.severity}",
                    "facts": [
                        {"name": "Control", "value": violation.control_id},
                        {"name": "Severity", "value": violation.severity},
                        {"name": "Age", "value": f"{violation.age_days} days"},
                        {"name": "Status", "value": violation.status}
                    ],
                    "text": violation.description
                }
            ],
            "potentialAction": [
                {
                    "@type": "OpenUri",
                    "name": "View in Dashboard",
                    "targets": [{"os": "default", "uri": "http://localhost:3000/violations"}]
                }
            ]
        }
        
        try:
            response = await client.post(
                self.teams_config["webhook_url"],
                json=card,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                logger.info("Teams alert sent")
                return True
            else:
                logger.error(f"Teams webhook error: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send Teams alert: {e}")
            return False
    
    def _get_severity_color(self, severity: str) -> str:
        """Get hex color for severity level."""
        colors = {
            "LOW": "00FF00",
            "MEDIUM": "FFFF00",
            "HIGH": "FFA500",
            "CRITICAL": "FF0000"
        }
        return colors.get(severity, "808080")
    
    def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
        return self._http_client
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
