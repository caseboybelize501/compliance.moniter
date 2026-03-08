"""Alert Dispatcher stub - sends violation alerts via Slack/email/webhook."""
from typing import Any
from server.models.violation import Violation


class AlertDispatcher:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
    
    async def send_alert(self, violation: Violation) -> bool:
        return True
    
    async def send_slack(self, message: str) -> bool:
        return True
    
    async def send_email(self, to: str, subject: str, body: str) -> bool:
        return True
    
    async def send_webhook(self, url: str, payload: dict[str, Any]) -> bool:
        return True
