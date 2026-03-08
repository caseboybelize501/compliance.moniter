"""GitLab Connector stub."""
from typing import Any
from connectors.base import BaseConnector, RateLimitConfig
from server.models.control import EvidenceArtifact
from server.models.tenant import SourceProfile


class GitLabConnector(BaseConnector):
    source_type = "gitlab"
    default_rate_limit = RateLimitConfig(requests_per_second=5.0, requests_per_hour=2000)
    
    @property
    def name(self) -> str:
        return "GitLab"
    
    async def validate_credentials(self) -> bool:
        return True
    
    async def collect_evidence(self, evidence_type: str, **kwargs: Any) -> list[EvidenceArtifact]:
        return []
    
    async def get_available_evidence_types(self) -> list[str]:
        return ["repositories", "branch_protection", "ci_config"]
