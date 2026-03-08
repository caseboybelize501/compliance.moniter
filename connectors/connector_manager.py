"""
Connector Manager for ACMP.

Manages connector registry, SourceProfile lifecycle, and delta sync state.
"""
import asyncio
from datetime import datetime
from typing import Any
from dataclasses import dataclass, field

from server.models.tenant import SourceProfile, SourceValidationResult
from connectors.base import BaseConnector, ConnectorError, ConnectorAuthenticationError


@dataclass
class ConnectorRegistry:
    """Registry of available connector types."""
    connectors: dict[str, type[BaseConnector]] = field(default_factory=dict)
    
    def register(self, connector_type: type[BaseConnector]) -> None:
        """Register a connector type."""
        self.connectors[connector_type.source_type] = connector_type
    
    def get(self, source_type: str) -> type[BaseConnector] | None:
        """Get a connector type by source type."""
        return self.connectors.get(source_type)
    
    def list_available(self) -> list[str]:
        """List all available connector types."""
        return list(self.connectors.keys())


# Global registry instance
registry = ConnectorRegistry()


def register_default_connectors() -> None:
    """Register all default connectors."""
    # Import here to avoid circular dependencies
    try:
        from connectors.aws import AWSConnector
        registry.register(AWSConnector)
    except ImportError:
        pass
    
    try:
        from connectors.github import GitHubConnector
        registry.register(GitHubConnector)
    except ImportError:
        pass
    
    try:
        from connectors.okta import OktaConnector
        registry.register(OktaConnector)
    except ImportError:
        pass
    
    # Additional connectors can be registered similarly
    # from connectors.gcp import GCPConnector
    # registry.register(GCPConnector)
    # from connectors.azure import AzureConnector
    # registry.register(AzureConnector)


class ConnectorManager:
    """
    Manages source connections and evidence collection.
    
    Responsibilities:
    - Validate source credentials
    - Create connector instances
    - Track sync state
    - Manage delta collection
    """
    
    def __init__(self):
        self._source_profiles: dict[str, SourceProfile] = {}
        self._sync_state: dict[str, dict[str, Any]] = {}
        self._connectors: dict[str, BaseConnector] = {}
    
    def register_source(self, profile: SourceProfile) -> None:
        """Register a source profile."""
        self._source_profiles[profile.id] = profile
    
    def get_source(self, source_id: str) -> SourceProfile | None:
        """Get a source profile by ID."""
        return self._source_profiles.get(source_id)
    
    def list_sources(self, tenant_id: str | None = None) -> list[SourceProfile]:
        """List all source profiles, optionally filtered by tenant."""
        sources = list(self._source_profiles.values())
        if tenant_id:
            sources = [s for s in sources if s.tenant_id == tenant_id]
        return sources
    
    def list_cloud_sources(self, tenant_id: str | None = None) -> list[SourceProfile]:
        """List cloud infrastructure sources (AWS, GCP, Azure)."""
        cloud_types = {"aws", "gcp", "azure"}
        sources = self.list_sources(tenant_id)
        return [s for s in sources if s.source_type in cloud_types]
    
    async def validate_source(self, source_id: str) -> SourceValidationResult:
        """
        Validate credentials for a source.
        
        Args:
            source_id: ID of the source to validate.
            
        Returns:
            SourceValidationResult with validation status.
        """
        profile = self.get_source(source_id)
        if not profile:
            return SourceValidationResult(
                source_id=source_id,
                validated=False,
                error_message="Source not found",
                read_only_confirmed=False,
                scope_discovered={}
            )
        
        connector_type = registry.get(profile.source_type)
        if not connector_type:
            return SourceValidationResult(
                source_id=source_id,
                validated=False,
                error_message=f"Unknown source type: {profile.source_type}",
                read_only_confirmed=False,
                scope_discovered={}
            )
        
        try:
            connector = connector_type(profile)
            async with connector:
                validated = await connector.validate_credentials()
                
                # Update profile
                profile.validated = validated
                profile.sync_status = "success" if validated else "error"
                profile.updated_at = datetime.utcnow()
                
                return SourceValidationResult(
                    source_id=source_id,
                    validated=validated,
                    error_message=None,
                    read_only_confirmed=profile.read_only,
                    scope_discovered=profile.scope
                )
                
        except ConnectorAuthenticationError as e:
            profile.validated = False
            profile.sync_status = "error"
            profile.last_error = str(e)
            profile.updated_at = datetime.utcnow()
            
            return SourceValidationResult(
                source_id=source_id,
                validated=False,
                error_message=str(e),
                read_only_confirmed=False,
                scope_discovered={}
            )
            
        except ConnectorError as e:
            profile.validated = False
            profile.sync_status = "error"
            profile.last_error = str(e)
            profile.updated_at = datetime.utcnow()
            
            return SourceValidationResult(
                source_id=source_id,
                validated=False,
                error_message=str(e),
                read_only_confirmed=False,
                scope_discovered={}
            )
    
    async def collect_evidence(
        self,
        source_id: str,
        evidence_type: str,
        control_id: str,
        **kwargs: Any
    ) -> list:
        """
        Collect evidence from a source.
        
        Args:
            source_id: ID of the source.
            evidence_type: Type of evidence to collect.
            control_id: Associated control ID.
            **kwargs: Additional parameters.
            
        Returns:
            List of EvidenceArtifact objects.
        """
        profile = self.get_source(source_id)
        if not profile:
            raise ConnectorError(f"Source not found: {source_id}")
        
        if not profile.validated:
            raise ConnectorError(f"Source not validated: {source_id}")
        
        connector_type = registry.get(profile.source_type)
        if not connector_type:
            raise ConnectorError(f"Unknown source type: {profile.source_type}")
        
        connector = connector_type(profile)
        async with connector:
            artifacts = await connector.collect_evidence(evidence_type, **kwargs)
            
            # Update sync state
            profile.last_sync = datetime.utcnow()
            profile.sync_status = "success"
            
            # Store delta state
            self._sync_state[source_id] = {
                "evidence_type": evidence_type,
                "control_id": control_id,
                "last_sync": profile.last_sync.isoformat(),
                "artifact_count": len(artifacts),
            }
            
            return artifacts
    
    def get_sync_state(self, source_id: str) -> dict[str, Any]:
        """Get sync state for a source."""
        return self._sync_state.get(source_id, {})
    
    def get_delta_since(self, source_id: str, since: datetime) -> dict[str, Any]:
        """Get delta sync information since a timestamp."""
        state = self._sync_state.get(source_id, {})
        last_sync_str = state.get("last_sync")
        
        if not last_sync_str:
            return {"full_sync": True}
        
        last_sync = datetime.fromisoformat(last_sync_str)
        return {
            "full_sync": False,
            "since": last_sync.isoformat(),
            "delta_available": last_sync > since
        }
    
    async def validate_all_sources(self, tenant_id: str) -> dict[str, SourceValidationResult]:
        """Validate all sources for a tenant."""
        sources = self.list_sources(tenant_id)
        results = {}
        
        for source in sources:
            results[source.id] = await self.validate_source(source.id)
        
        return results
    
    def has_cloud_source(self, tenant_id: str) -> bool:
        """Check if tenant has at least one validated cloud source."""
        cloud_sources = self.list_cloud_sources(tenant_id)
        return any(s.validated for s in cloud_sources)


# Initialize registry with default connectors
register_default_connectors()
