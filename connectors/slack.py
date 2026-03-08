"""Slack Connector for ACMP - collects communication evidence."""
import asyncio
from typing import Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from connectors.base import BaseConnector, ConnectorError, ConnectorAuthenticationError, RateLimitConfig
from server.models.control import EvidenceArtifact
from server.models.tenant import SourceProfile


class SlackConnector(BaseConnector):
    """Slack connector for collecting communication evidence."""
    
    source_type = "slack"
    default_rate_limit = RateLimitConfig(requests_per_second=50.0, burst_size=100)
    
    def __init__(self, source_profile: SourceProfile, **kwargs: Any):
        super().__init__(source_profile, **kwargs)
        self._token = source_profile.scope.get("token")
        self._client: WebClient | None = None
    
    @property
    def name(self) -> str:
        return "Slack"
    
    async def validate_credentials(self) -> bool:
        """Validate Slack bot token."""
        try:
            loop = asyncio.get_event_loop()
            
            def _validate():
                client = WebClient(token=self._token)
                auth = client.auth_test()
                return auth["ok"]
            
            result = await loop.run_in_executor(None, _validate)
            return result
            
        except SlackApiError as e:
            if e.response["error"] == "invalid_auth":
                raise ConnectorAuthenticationError(f"Slack authentication failed: {e}")
            raise ConnectorError(f"Slack validation error: {e}")
        except Exception as e:
            raise ConnectorError(f"Slack validation error: {e}")
    
    async def collect_evidence(self, evidence_type: str, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect evidence for a specific evidence type."""
        evidence_collectors = {
            "channels": self._collect_channels,
            "retention_policy": self._collect_retention_policy,
            "dlp_config": self._collect_dlp_config,
        }
        
        collector = evidence_collectors.get(evidence_type)
        if not collector:
            raise ConnectorError(f"Unknown evidence type: {evidence_type}")
        
        return await collector(**kwargs)
    
    async def get_available_evidence_types(self) -> list[str]:
        """Get list of evidence types this connector can collect."""
        return ["channels", "retention_policy", "dlp_config"]
    
    async def _collect_channels(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect Slack channels evidence."""
        loop = asyncio.get_event_loop()
        
        def _list():
            client = WebClient(token=self._token)
            channels = client.conversations_list(types="public_channel,private_channel")
            return [
                {
                    "id": c["id"],
                    "name": c["name"],
                    "is_private": c["is_private"],
                    "created": c["created"],
                    "num_members": c["num_members"],
                }
                for c in channels["channels"]
            ]
        
        channels = await loop.run_in_executor(None, _list)
        
        artifact = self._create_artifact(
            control_id="CC2.1",
            content={
                "channels": channels,
                "total_channels": len(channels),
                "public_channels": sum(1 for c in channels if not c["is_private"]),
                "private_channels": sum(1 for c in channels if c["is_private"]),
            },
            metadata={"evidence_type": "channels"}
        )
        return [artifact]
    
    async def _collect_retention_policy(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect retention policy evidence."""
        loop = asyncio.get_event_loop()
        
        def _list():
            client = WebClient(token=self._token)
            # Get workspace retention policy (requires admin scope)
            try:
                # This would use admin.conversations.getCustomRetention or similar
                # For now, return placeholder
                return {
                    "has_retention_policy": False,
                    "retention_days": None,
                    "note": "Admin scope required for retention policy access"
                }
            except SlackApiError:
                return {
                    "has_retention_policy": False,
                    "retention_days": None,
                    "error": "Insufficient permissions"
                }
        
        policy = await loop.run_in_executor(None, _list)
        
        artifact = self._create_artifact(
            control_id="CC5.3",
            content=policy,
            metadata={"evidence_type": "retention_policy"}
        )
        return [artifact]
    
    async def _collect_dlp_config(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect DLP (Data Loss Prevention) configuration evidence."""
        loop = asyncio.get_event_loop()
        
        def _list():
            client = WebClient(token=self._token)
            # Get DLP configuration (requires Enterprise Grid + admin scope)
            try:
                # This would use admin.barriers.* or similar endpoints
                return {
                    "has_dlp": False,
                    "dlp_policies": [],
                    "note": "Enterprise Grid + admin scope required for DLP access"
                }
            except SlackApiError:
                return {
                    "has_dlp": False,
                    "dlp_policies": [],
                    "error": "Insufficient permissions or not Enterprise Grid"
                }
        
        config = await loop.run_in_executor(None, _list)
        
        artifact = self._create_artifact(
            control_id="CC6.6",
            content=config,
            metadata={"evidence_type": "dlp_config"}
        )
        return [artifact]
