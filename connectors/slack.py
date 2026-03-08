"""Slack Connector stub."""
from typing import Any
from connectors.base import BaseConnector, RateLimitConfig
from server.models.control import EvidenceArtifact
from server.models.tenant import SourceProfile


class SlackConnector(BaseConnector):
    source_type = "slack"
    default_rate_limit = RateLimitConfig(requests_per_second=100.0, burst_size=50)
    
    @property
    def name(self) -> str:
        return "Slack"
    
    async def validate_credentials(self) -> bool:
        return True
    
    async def collect_evidence(self, evidence_type: str, **kwargs: Any) -> list[EvidenceArtifact]:
        return []
    
    async def get_available_evidence_types(self) -> list[str]:
        return ["channels", "retention_policy", "dlp_config"]
