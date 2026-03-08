"""
Evidence Repository

Data access for EvidenceArtifact and SourceProfile entities.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from server.db.models.evidence import EvidenceArtifact, SourceProfile
from server.db.repositories.base import BaseRepository


class EvidenceRepository(BaseRepository[EvidenceArtifact]):
    """Repository for EvidenceArtifact operations."""
    
    def __init__(self, db_session: AsyncSession):
        super().__init__(EvidenceArtifact, db_session)
    
    async def check_dedup(self, control_id: str, source_id: str, artifact_hash: str) -> EvidenceArtifact | None:
        """Check if artifact already exists (dedup)."""
        return await self.get_by(
            control_id=control_id,
            source_id=source_id,
            artifact_hash=artifact_hash
        )
    
    async def list_by_control(self, control_id: str, tenant_id: str, limit: int = 100) -> list[EvidenceArtifact]:
        """List evidence for a control."""
        return await self.list_by(
            limit=limit,
            control_id=control_id,
            tenant_id=tenant_id
        )
    
    async def list_by_tenant(self, tenant_id: str, since: datetime = None, limit: int = 100) -> list[EvidenceArtifact]:
        """List evidence for a tenant, optionally since a timestamp."""
        if since:
            return await self.list_by(
                limit=limit,
                tenant_id=tenant_id,
                collected_at__gte=since
            )
        return await self.list_by(limit=limit, tenant_id=tenant_id)
    
    async def update_last_seen(self, artifact_id: str) -> None:
        """Update last_seen_at timestamp."""
        artifact = await self.get(artifact_id)
        if artifact:
            artifact.last_seen_at = datetime.utcnow()
            await self.db_session.flush()


class SourceProfileRepository(BaseRepository[SourceProfile]):
    """Repository for SourceProfile operations."""
    
    def __init__(self, db_session: AsyncSession):
        super().__init__(SourceProfile, db_session)
    
    async def list_by_tenant(self, tenant_id: str) -> list[SourceProfile]:
        """List all sources for a tenant."""
        return await self.list_by(tenant_id=tenant_id)
    
    async def list_cloud_sources(self, tenant_id: str) -> list[SourceProfile]:
        """List cloud infrastructure sources."""
        cloud_types = ['aws', 'gcp', 'azure']
        result = await self.db_session.execute(
            select(SourceProfile).where(
                SourceProfile.tenant_id == tenant_id,
                SourceProfile.source_type.in_(cloud_types)
            )
        )
        return list(result.scalars().all())
    
    async def mark_validated(self, source_id: str) -> None:
        """Mark source as validated."""
        await self.update(source_id, {"validated": True, "sync_status": "success"})
    
    async def mark_sync_complete(self, source_id: str) -> None:
        """Mark sync as complete."""
        await self.update(source_id, {
            "sync_status": "success",
            "last_sync": datetime.utcnow()
        })
    
    async def mark_sync_error(self, source_id: str, error: str) -> None:
        """Mark sync as failed."""
        await self.update(source_id, {
            "sync_status": "error",
            "last_error": error
        })
