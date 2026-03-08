"""
Evidence Store - Full Implementation

Stores evidence artifacts in Minio with encryption.
Tracks metadata in PostgreSQL.
"""
import json
import hashlib
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from server.models.control import EvidenceArtifact
from server.db.models.evidence import EvidenceArtifact as EvidenceArtifactModel
from server.db.repositories.evidence_repository import EvidenceRepository
from server.storage.minio_client import MinioStorage


class EvidenceStoreError(Exception):
    """Base exception for evidence store errors."""
    pass


class EvidenceStore:
    """
    Evidence store with PostgreSQL metadata and Minio storage.
    
    Features:
    - AES-256 encryption at rest
    - Dedup by (control_id + source + artifact_hash)
    - Tenant isolation
    - Audit logging
    """
    
    def __init__(
        self,
        db_session: AsyncSession,
        minio_storage: MinioStorage
    ):
        """
        Initialize evidence store.
        
        Args:
            db_session: Async database session
            minio_storage: Minio storage client
        """
        self.db_session = db_session
        self.minio = minio_storage
        self.repository = EvidenceRepository(db_session)
    
    def _compute_artifact_hash(self, content: dict[str, Any]) -> str:
        """Compute SHA256 hash of artifact content."""
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()
    
    def _compute_s3_key(self, tenant_id: str, control_id: str, artifact_hash: str) -> str:
        """Compute S3 key for artifact."""
        return f"evidence/{control_id}/{artifact_hash}.enc"
    
    async def store_artifact(
        self,
        control_id: str,
        source_id: str,
        tenant_id: str,
        content: dict[str, Any],
        metadata: Optional[dict[str, Any]] = None,
        collected_at: Optional[datetime] = None
    ) -> EvidenceArtifact:
        """
        Store evidence artifact.
        
        Args:
            control_id: Associated control ID
            source_id: Source profile ID
            tenant_id: Tenant ID
            content: Artifact content (will be encrypted)
            metadata: Optional metadata
            collected_at: Collection timestamp
            
        Returns:
            Stored EvidenceArtifact
        """
        # Compute hash for dedup
        artifact_hash = self._compute_artifact_hash(content)
        
        # Check dedup
        existing = await self.repository.check_dedup(
            control_id=control_id,
            source_id=source_id,
            artifact_hash=artifact_hash
        )
        
        if existing:
            # Update last_seen_at
            await self.repository.update_last_seen(existing.id)
            
            # Return existing artifact
            return EvidenceArtifact(
                id=existing.id,
                control_id=existing.control_id,
                source=existing.source_id,
                source_id=existing.source_id,
                artifact_hash=existing.artifact_hash,
                content=content,  # Return unencrypted content
                collected_at=existing.collected_at,
                tenant_id=existing.tenant_id,
                s3_key=existing.s3_key,
                encryption_key_id="default",
                metadata=existing.content_metadata
            )
        
        # Encrypt and upload to Minio
        content_json = json.dumps(content, sort_keys=True).encode()
        s3_key = self._compute_s3_key(tenant_id, control_id, artifact_hash)
        
        etag = await self.minio.upload_artifact(
            tenant_id=tenant_id,
            object_name=s3_key,
            data=content_json,
            content_type="application/json",
            metadata=metadata or {}
        )
        
        # Create database record
        artifact_model = EvidenceArtifactModel(
            id=str(uuid4()),
            control_id=control_id,
            source_id=source_id,
            tenant_id=tenant_id,
            artifact_hash=artifact_hash,
            s3_key=s3_key,
            s3_bucket=self.minio._get_bucket_name(tenant_id),
            encryption_key_id="default",
            content_metadata=metadata or {},
            content_size=len(content_json),
            collected_at=collected_at or datetime.utcnow(),
            last_seen_at=datetime.utcnow()
        )
        
        await self.repository.create(artifact_model)
        
        # Return EvidenceArtifact (Pydantic model)
        return EvidenceArtifact(
            id=artifact_model.id,
            control_id=artifact_model.control_id,
            source=source_id,
            source_id=source_id,
            artifact_hash=artifact_hash,
            content=content,
            collected_at=artifact_model.collected_at,
            tenant_id=artifact_model.tenant_id,
            s3_key=s3_key,
            encryption_key_id="default",
            metadata=metadata or {}
        )
    
    async def get_artifact(
        self,
        artifact_id: str,
        tenant_id: str
    ) -> Optional[EvidenceArtifact]:
        """
        Retrieve evidence artifact.
        
        Args:
            artifact_id: Artifact ID
            tenant_id: Tenant ID
            
        Returns:
            EvidenceArtifact or None
        """
        # Get from database
        artifact_model = await self.repository.get(artifact_id)
        
        if not artifact_model:
            return None
        
        # Verify tenant isolation
        if artifact_model.tenant_id != tenant_id:
            raise EvidenceStoreError("Access denied: tenant mismatch")
        
        # Download and decrypt from Minio
        encrypted_data = await self.minio.download_artifact(
            tenant_id=tenant_id,
            object_name=artifact_model.s3_key
        )
        
        # Parse content
        content = json.loads(encrypted_data.decode())
        
        return EvidenceArtifact(
            id=artifact_model.id,
            control_id=artifact_model.control_id,
            source=artifact_model.source_id,
            source_id=artifact_model.source_id,
            artifact_hash=artifact_model.artifact_hash,
            content=content,
            collected_at=artifact_model.collected_at,
            tenant_id=artifact_model.tenant_id,
            s3_key=artifact_model.s3_key,
            encryption_key_id=artifact_model.encryption_key_id,
            metadata=artifact_model.content_metadata
        )
    
    async def get_content(
        self,
        artifact_id: str,
        tenant_id: str
    ) -> Optional[dict[str, Any]]:
        """
        Get artifact content without full model.
        
        Args:
            artifact_id: Artifact ID
            tenant_id: Tenant ID
            
        Returns:
            Content dict or None
        """
        artifact = await self.get_artifact(artifact_id, tenant_id)
        return artifact.content if artifact else None
    
    async def list_artifacts(
        self,
        tenant_id: str,
        control_id: Optional[str] = None,
        source_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> list[EvidenceArtifact]:
        """
        List artifacts with filters.
        
        Args:
            tenant_id: Tenant ID
            control_id: Optional control filter
            source_id: Optional source filter
            since: Optional timestamp filter
            limit: Result limit
            
        Returns:
            List of EvidenceArtifact (metadata only, no content)
        """
        # Build filters
        filters = {"tenant_id": tenant_id}
        if control_id:
            filters["control_id"] = control_id
        if source_id:
            filters["source_id"] = source_id
        
        artifacts = await self.repository.list_by(limit=limit, **filters)
        
        return [
            EvidenceArtifact(
                id=a.id,
                control_id=a.control_id,
                source=a.source_id,
                source_id=a.source_id,
                artifact_hash=a.artifact_hash,
                content={},  # Don't load content in list
                collected_at=a.collected_at,
                tenant_id=a.tenant_id,
                s3_key=a.s3_key,
                encryption_key_id=a.encryption_key_id,
                metadata=a.content_metadata
            )
            for a in artifacts
        ]
    
    async def delete_artifact(
        self,
        artifact_id: str,
        tenant_id: str
    ) -> bool:
        """
        Delete artifact.
        
        Args:
            artifact_id: Artifact ID
            tenant_id: Tenant ID
            
        Returns:
            True if deleted
        """
        artifact = await self.repository.get(artifact_id)
        
        if not artifact:
            return False
        
        # Verify tenant isolation
        if artifact.tenant_id != tenant_id:
            raise EvidenceStoreError("Access denied: tenant mismatch")
        
        # Delete from Minio
        await self.minio.delete_artifact(
            tenant_id=tenant_id,
            object_name=artifact.s3_key
        )
        
        # Delete from database
        await self.repository.delete(artifact_id)
        
        return True
    
    async def get_storage_stats(self, tenant_id: str) -> dict:
        """
        Get storage statistics for tenant.
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Storage statistics
        """
        return await self.minio.get_storage_stats(tenant_id)
    
    async def health_check(self) -> dict:
        """
        Check storage health.
        
        Returns:
            Health status
        """
        return await self.minio.health_check()
