"""
GCP Connector for ACMP.

Collects evidence from GCP: IAM, audit logs, GCS, KMS.
Uses google-api-python-client with service account credentials.
"""
import asyncio
from typing import Any

from connectors.base import BaseConnector, ConnectorError, ConnectorAuthenticationError, RateLimitConfig
from server.models.control import EvidenceArtifact
from server.models.tenant import SourceProfile


class GCPConnector(BaseConnector):
    """GCP connector for collecting compliance evidence."""
    
    source_type = "gcp"
    default_rate_limit = RateLimitConfig(
        requests_per_second=5.0,
        requests_per_minute=300,
        burst_size=10
    )
    
    def __init__(self, source_profile: SourceProfile, **kwargs: Any):
        super().__init__(source_profile, **kwargs)
        self._credentials_path = source_profile.scope.get("credentials_path")
        self._project_id = source_profile.scope.get("project_id")
    
    @property
    def name(self) -> str:
        return f"GCP ({self._project_id})"
    
    async def validate_credentials(self) -> bool:
        """Validate GCP credentials."""
        # TODO: Implement GCP credential validation
        return True
    
    async def collect_evidence(self, evidence_type: str, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect evidence for a specific evidence type."""
        # TODO: Implement evidence collection
        return []
    
    async def get_available_evidence_types(self) -> list[str]:
        """Get list of evidence types this connector can collect."""
        return [
            "iam_users",
            "iam_roles",
            "audit_logs",
            "gcs_buckets",
            "kms_keys",
        ]
