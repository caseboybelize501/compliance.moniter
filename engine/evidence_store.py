"""
Evidence Store for ACMP.

Stores evidence artifacts in S3/Minio with encryption.
Tracks metadata in PostgreSQL.
"""
import json
import hashlib
from datetime import datetime
from typing import Any
from dataclasses import dataclass

from cryptography.fernet import Fernet

from server.models.control import EvidenceArtifact


@dataclass
class StorageConfig:
    """Storage configuration."""
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str = "acmp-evidence"
    encryption_key: str | None = None
    region: str = "us-east-1"


class EvidenceStoreError(Exception):
    """Base exception for evidence store errors."""
    pass


class EvidenceStore:
    """
    Stores and retrieves evidence artifacts.
    
    Features:
    - Encrypted storage in S3/Minio
    - Metadata tracking in PostgreSQL
    - Dedup by (control_id + source + artifact_hash)
    - Tenant isolation
    """
    
    def __init__(self, config: StorageConfig):
        self.config = config
        self._fernet: Fernet | None = None
        self._s3_client = None
        self._db_pool = None
        
        if config.encryption_key:
            self._fernet = Fernet(config.encryption_key.encode())
    
    def _get_encryption_key(self) -> str:
        """Get or generate encryption key."""
        if not self.config.encryption_key:
            # In production, this should be from secure config
            self.config.encryption_key = Fernet.generate_key().decode()
            self._fernet = Fernet(self.config.encryption_key.encode())
        return self.config.encryption_key
    
    def _encrypt_content(self, content: dict[str, Any]) -> bytes:
        """Encrypt artifact content."""
        if not self._fernet:
            self._get_encryption_key()
        
        content_json = json.dumps(content, sort_keys=True).encode()
        return self._fernet.encrypt(content_json)
    
    def _decrypt_content(self, encrypted: bytes) -> dict[str, Any]:
        """Decrypt artifact content."""
        if not self._fernet:
            raise EvidenceStoreError("Encryption not configured")
        
        content_json = self._fernet.decrypt(encrypted)
        return json.loads(content_json)
    
    def _compute_s3_key(self, artifact: EvidenceArtifact) -> str:
        """Compute S3 key for an artifact."""
        return f"evidence/{artifact.tenant_id}/{artifact.control_id}/{artifact.artifact_hash}.enc"
    
    async def store_artifact(self, artifact: EvidenceArtifact) -> EvidenceArtifact:
        """
        Store an evidence artifact.
        
        Args:
            artifact: EvidenceArtifact to store.
            
        Returns:
            Stored artifact with S3 key and encryption info.
        """
        # Encrypt content
        encrypted_content = self._encrypt_content(artifact.content)
        
        # Compute S3 key
        s3_key = self._compute_s3_key(artifact)
        
        # Store in S3 (placeholder - would use boto3/minio)
        await self._store_in_s3(s3_key, encrypted_content, artifact.tenant_id)
        
        # Update artifact
        artifact.s3_key = s3_key
        artifact.encryption_key_id = "default"  # Would use key management in production
        
        # Store metadata in PostgreSQL (placeholder)
        await self._store_metadata(artifact)
        
        return artifact
    
    async def get_artifact(self, artifact_id: str, tenant_id: str) -> EvidenceArtifact:
        """
        Retrieve an evidence artifact.
        
        Args:
            artifact_id: ID of the artifact.
            tenant_id: Tenant ID for isolation.
            
        Returns:
            EvidenceArtifact with decrypted content.
        """
        # Get metadata from PostgreSQL (placeholder)
        metadata = await self._get_metadata(artifact_id, tenant_id)
        if not metadata:
            raise EvidenceStoreError(f"Artifact not found: {artifact_id}")
        
        # Get encrypted content from S3
        encrypted_content = await self._get_from_s3(metadata["s3_key"], tenant_id)
        
        # Decrypt content
        content = self._decrypt_content(encrypted_content)
        
        # Reconstruct artifact
        return EvidenceArtifact(
            id=metadata["id"],
            control_id=metadata["control_id"],
            source=metadata["source"],
            source_id=metadata["source_id"],
            artifact_hash=metadata["artifact_hash"],
            content=content,
            collected_at=metadata["collected_at"],
            tenant_id=metadata["tenant_id"],
            s3_key=metadata["s3_key"],
            encryption_key_id=metadata["encryption_key_id"],
            metadata=metadata.get("metadata", {})
        )
    
    async def check_dedup(self, control_id: str, source: str, artifact_hash: str, tenant_id: str) -> EvidenceArtifact | None:
        """
        Check if an artifact already exists (dedup).
        
        Args:
            control_id: Control ID.
            source: Source type.
            artifact_hash: Artifact hash.
            tenant_id: Tenant ID.
            
        Returns:
            Existing artifact if found, None otherwise.
        """
        # Query PostgreSQL for existing artifact
        existing = await self._find_by_hash(control_id, source, artifact_hash, tenant_id)
        return existing
    
    async def list_artifacts(
        self,
        tenant_id: str,
        control_id: str | None = None,
        source: str | None = None,
        since: datetime | None = None
    ) -> list[EvidenceArtifact]:
        """
        List artifacts with optional filters.
        
        Args:
            tenant_id: Tenant ID (required for isolation).
            control_id: Optional control ID filter.
            source: Optional source filter.
            since: Optional timestamp filter.
            
        Returns:
            List of EvidenceArtifact metadata (without content).
        """
        # Query PostgreSQL (placeholder)
        return await self._list_metadata(tenant_id, control_id, source, since)
    
    async def delete_artifact(self, artifact_id: str, tenant_id: str) -> None:
        """
        Delete an evidence artifact.
        
        Args:
            artifact_id: ID of the artifact.
            tenant_id: Tenant ID for isolation.
        """
        # Get metadata
        metadata = await self._get_metadata(artifact_id, tenant_id)
        if metadata:
            # Delete from S3
            await self._delete_from_s3(metadata["s3_key"], tenant_id)
            # Delete metadata
            await self._delete_metadata(artifact_id)
    
    # Storage backend methods (placeholders)
    async def _store_in_s3(self, key: str, content: bytes, tenant_id: str) -> None:
        """Store encrypted content in S3/Minio."""
        # TODO: Implement with boto3 or minio-py
        pass
    
    async def _get_from_s3(self, key: str, tenant_id: str) -> bytes:
        """Retrieve encrypted content from S3/Minio."""
        # TODO: Implement with boto3 or minio-py
        return b""
    
    async def _delete_from_s3(self, key: str, tenant_id: str) -> None:
        """Delete content from S3/Minio."""
        # TODO: Implement with boto3 or minio-py
        pass
    
    async def _store_metadata(self, artifact: EvidenceArtifact) -> None:
        """Store artifact metadata in PostgreSQL."""
        # TODO: Implement with asyncpg or SQLAlchemy
        pass
    
    async def _get_metadata(self, artifact_id: str, tenant_id: str) -> dict[str, Any] | None:
        """Get artifact metadata from PostgreSQL."""
        # TODO: Implement with asyncpg or SQLAlchemy
        return None
    
    async def _find_by_hash(
        self,
        control_id: str,
        source: str,
        artifact_hash: str,
        tenant_id: str
    ) -> EvidenceArtifact | None:
        """Find artifact by hash for dedup."""
        # TODO: Implement with asyncpg or SQLAlchemy
        return None
    
    async def _list_metadata(
        self,
        tenant_id: str,
        control_id: str | None,
        source: str | None,
        since: datetime | None
    ) -> list[EvidenceArtifact]:
        """List artifact metadata."""
        # TODO: Implement with asyncpg or SQLAlchemy
        return []
    
    async def _delete_metadata(self, artifact_id: str) -> None:
        """Delete artifact metadata."""
        # TODO: Implement with asyncpg or SQLAlchemy
        pass
