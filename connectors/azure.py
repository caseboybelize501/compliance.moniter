"""
Azure Connector for ACMP.

Collects evidence from Azure: RBAC, policy, key vault.
Uses MSAL and azure-mgmt libraries.
"""
import asyncio
from typing import Any

from connectors.base import BaseConnector, ConnectorError, ConnectorAuthenticationError, RateLimitConfig
from server.models.control import EvidenceArtifact
from server.models.tenant import SourceProfile


class AzureConnector(BaseConnector):
    """Azure connector for collecting compliance evidence."""
    
    source_type = "azure"
    default_rate_limit = RateLimitConfig(
        requests_per_second=10.0,
        requests_per_minute=600,
        burst_size=20
    )
    
    def __init__(self, source_profile: SourceProfile, **kwargs: Any):
        super().__init__(source_profile, **kwargs)
        self._tenant_id = source_profile.scope.get("tenant_id")
        self._client_id = source_profile.scope.get("client_id")
    
    @property
    def name(self) -> str:
        return f"Azure ({self._tenant_id})"
    
    async def validate_credentials(self) -> bool:
        """Validate Azure credentials."""
        # TODO: Implement Azure credential validation
        return True
    
    async def collect_evidence(self, evidence_type: str, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect evidence for a specific evidence type."""
        # TODO: Implement evidence collection
        return []
    
    async def get_available_evidence_types(self) -> list[str]:
        """Get list of evidence types this connector can collect."""
        return [
            "rbac_users",
            "rbac_roles",
            "policy_assignments",
            "key_vault_keys",
            "storage_accounts",
        ]
