"""Jira Connector stub."""
from typing import Any
from connectors.base import BaseConnector, RateLimitConfig
from server.models.control import EvidenceArtifact
from server.models.tenant import SourceProfile


class JiraConnector(BaseConnector):
    source_type = "jira"
    default_rate_limit = RateLimitConfig(requests_per_second=10.0, requests_per_10s=100)
    
    @property
    def name(self) -> str:
        return "Jira"
    
    async def validate_credentials(self) -> bool:
        return True
    
    async def collect_evidence(self, evidence_type: str, **kwargs: Any) -> list[EvidenceArtifact]:
        return []
    
    async def get_available_evidence_types(self) -> list[str]:
        return ["issues", "change_tickets", "incident_records"]
