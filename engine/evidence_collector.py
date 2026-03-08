"""
Evidence Collector for ACMP.

Orchestrates evidence collection from all sources.
Handles dedup and delta collection.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Any

from server.models.control import EvidenceArtifact
from server.models.tenant import SourceProfile
from connectors.connector_manager import ConnectorManager


class EvidenceCollectorError(Exception):
    """Base exception for evidence collector errors."""
    pass


class EvidenceCollector:
    """
    Orchestrates evidence collection.
    
    Responsibilities:
    - Coordinate collection across all sources
    - Handle dedup via EvidenceStore
    - Support delta collection
    - Track collection state
    """
    
    def __init__(
        self,
        connector_manager: ConnectorManager,
        evidence_store: Any,  # EvidenceStore
        framework_registry: Any,  # FrameworkRegistry
    ):
        self.connector_manager = connector_manager
        self.evidence_store = evidence_store
        self.framework_registry = framework_registry
    
    async def collect_for_control(
        self,
        control_id: str,
        tenant_id: str,
        evidence_types: list[str] | None = None
    ) -> list[EvidenceArtifact]:
        """
        Collect evidence for a specific control.
        
        Args:
            control_id: ID of the control.
            tenant_id: Tenant ID.
            evidence_types: Optional list of evidence types to collect.
            
        Returns:
            List of collected EvidenceArtifact objects.
        """
        # Get all sources for tenant
        sources = self.connector_manager.list_sources(tenant_id)
        
        if not sources:
            raise EvidenceCollectorError(f"No sources configured for tenant {tenant_id}")
        
        all_artifacts = []
        
        for source in sources:
            if not source.validated:
                continue
            
            try:
                artifacts = await self._collect_from_source(
                    source=source,
                    control_id=control_id,
                    evidence_types=evidence_types
                )
                all_artifacts.extend(artifacts)
            except Exception as e:
                # Log error but continue with other sources
                print(f"Error collecting from {source.source_type}: {e}")
        
        return all_artifacts
    
    async def collect_delta(
        self,
        tenant_id: str,
        since: datetime | None = None
    ) -> list[EvidenceArtifact]:
        """
        Collect delta evidence since last collection.
        
        Args:
            tenant_id: Tenant ID.
            since: Optional timestamp to collect since.
            
        Returns:
            List of new EvidenceArtifact objects.
        """
        if since is None:
            since = datetime.utcnow() - timedelta(hours=1)
        
        sources = self.connector_manager.list_sources(tenant_id)
        all_artifacts = []
        
        for source in sources:
            if not source.validated:
                continue
            
            # Get delta state
            delta_info = self.connector_manager.get_delta_since(source.id, since)
            
            if delta_info.get("full_sync"):
                # Full sync needed
                pass
            elif not delta_info.get("delta_available"):
                # No delta available
                continue
            
            # Collect delta (implementation depends on connector)
            # For now, collect all evidence types
            try:
                evidence_types = await self._get_source_evidence_types(source)
                for evidence_type in evidence_types:
                    artifacts = await self.connector_manager.collect_evidence(
                        source_id=source.id,
                        evidence_type=evidence_type,
                        control_id="*"  # Wildcard for delta collection
                    )
                    
                    # Dedup check
                    for artifact in artifacts:
                        existing = await self.evidence_store.check_dedup(
                            artifact.control_id,
                            artifact.source,
                            artifact.artifact_hash,
                            tenant_id
                        )
                        
                        if not existing:
                            await self.evidence_store.store_artifact(artifact)
                            all_artifacts.append(artifact)
            except Exception as e:
                print(f"Error in delta collection for {source.source_type}: {e}")
        
        return all_artifacts
    
    async def _collect_from_source(
        self,
        source: SourceProfile,
        control_id: str,
        evidence_types: list[str] | None = None
    ) -> list[EvidenceArtifact]:
        """Collect evidence from a single source."""
        if evidence_types is None:
            evidence_types = await self._get_source_evidence_types(source)
        
        all_artifacts = []
        
        for evidence_type in evidence_types:
            try:
                artifacts = await self.connector_manager.collect_evidence(
                    source_id=source.id,
                    evidence_type=evidence_type,
                    control_id=control_id
                )
                
                # Dedup and store
                for artifact in artifacts:
                    existing = await self.evidence_store.check_dedup(
                        artifact.control_id,
                        artifact.source,
                        artifact.artifact_hash,
                        source.tenant_id
                    )
                    
                    if existing:
                        # Update last_seen on existing artifact
                        # (implementation depends on EvidenceStore)
                        continue
                    
                    await self.evidence_store.store_artifact(artifact)
                    all_artifacts.append(artifact)
                    
            except Exception as e:
                print(f"Error collecting {evidence_type} from {source.source_type}: {e}")
        
        return all_artifacts
    
    async def _get_source_evidence_types(self, source: SourceProfile) -> list[str]:
        """Get available evidence types for a source."""
        connector_type = self.connector_manager.registry.get(source.source_type)
        if connector_type:
            # Create temporary connector instance
            connector = connector_type(source)
            try:
                return await connector.get_available_evidence_types()
            finally:
                await connector.close()
        return []
    
    async def collect_all(
        self,
        tenant_id: str,
        framework_id: str
    ) -> dict[str, list[EvidenceArtifact]]:
        """
        Collect evidence for all controls in a framework.
        
        Args:
            tenant_id: Tenant ID.
            framework_id: Framework ID.
            
        Returns:
            Dictionary mapping control_id to list of artifacts.
        """
        framework = self.framework_registry.get_framework(framework_id)
        results = {}
        
        for control in framework.controls:
            if isinstance(control, dict):
                control_id = control.get("id")
                evidence_types = control.get("evidence_types", [])
                
                artifacts = await self.collect_for_control(
                    control_id=control_id,
                    tenant_id=tenant_id,
                    evidence_types=evidence_types
                )
                
                results[control_id] = artifacts
        
        return results
