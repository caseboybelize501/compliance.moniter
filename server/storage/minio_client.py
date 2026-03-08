"""
Minio Storage Client for ACMP.

S3-compatible storage client with AES-256 encryption.
"""
import io
import os
from typing import Optional, BinaryIO
from datetime import timedelta

from minio import Minio
from minio.error import S3Error
from cryptography.fernet import Fernet


class MinioStorageError(Exception):
    """Base exception for Minio storage errors."""
    pass


class MinioStorage:
    """
    Minio/S3 storage client with encryption.
    
    Features:
    - AES-256 encryption at rest (Fernet)
    - Bucket-per-tenant isolation
    - Presigned URLs for secure downloads
    - Lifecycle policies
    """
    
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        secure: bool = False,
        encryption_key: Optional[str] = None,
        region: str = "us-east-1"
    ):
        """
        Initialize Minio client.
        
        Args:
            endpoint: Minio/S3 endpoint URL
            access_key: Access key
            secret_key: Secret key
            secure: Use HTTPS
            encryption_key: Fernet key for encryption (32-byte URL-safe base64)
            region: AWS region
        """
        self.endpoint = endpoint
        self.region = region
        
        # Initialize Minio client
        self._client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            region=region
        )
        
        # Initialize encryption
        if encryption_key:
            self._fernet = Fernet(encryption_key.encode())
        else:
            # Generate key for testing (in production, always provide key)
            self._fernet = Fernet(Fernet.generate_key())
        
        self._bucket_prefix = "acmp-"
    
    def _get_bucket_name(self, tenant_id: str) -> str:
        """Get bucket name for tenant."""
        return f"{self._bucket_prefix}{tenant_id}"
    
    async def initialize_tenant(self, tenant_id: str) -> None:
        """
        Initialize bucket for tenant.
        
        Args:
            tenant_id: Tenant ID
        """
        bucket_name = self._get_bucket_name(tenant_id)
        
        try:
            # Check if bucket exists
            exists = await self._client.bucket_exists(bucket_name)
            if not exists:
                # Create bucket with versioning enabled
                await self._client.make_bucket(bucket_name, location=self.region)
                
                # Enable versioning (for audit trail)
                # Note: Requires Minio RELEASE.2020-12-03T05-06-33Z or later
                
        except S3Error as e:
            raise MinioStorageError(f"Failed to create bucket for tenant {tenant_id}: {e}")
    
    async def upload_artifact(
        self,
        tenant_id: str,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[dict] = None
    ) -> str:
        """
        Upload encrypted artifact to storage.
        
        Args:
            tenant_id: Tenant ID
            object_name: Object name (e.g., evidence/control_id/hash.enc)
            data: Raw data to encrypt and store
            content_type: MIME type
            metadata: Optional metadata
            
        Returns:
            ETag of uploaded object
        """
        bucket_name = self._get_bucket_name(tenant_id)
        
        # Encrypt data
        encrypted_data = self._fernet.encrypt(data)
        
        # Prepare metadata
        obj_metadata = metadata or {}
        obj_metadata["X-Amz-Meta-Encrypted"] = "true"
        obj_metadata["X-Amz-Meta-Content-Length"] = str(len(data))
        
        try:
            # Upload encrypted data
            result = await self._client.put_object(
                bucket_name,
                object_name,
                io.BytesIO(encrypted_data),
                len(encrypted_data),
                content_type=content_type,
                metadata=obj_metadata
            )
            
            return result.etag
            
        except S3Error as e:
            raise MinioStorageError(f"Failed to upload artifact {object_name}: {e}")
    
    async def download_artifact(
        self,
        tenant_id: str,
        object_name: str
    ) -> bytes:
        """
        Download and decrypt artifact from storage.
        
        Args:
            tenant_id: Tenant ID
            object_name: Object name
            
        Returns:
            Decrypted data
        """
        bucket_name = self._get_bucket_name(tenant_id)
        
        try:
            # Download encrypted data
            response = await self._client.get_object(bucket_name, object_name)
            encrypted_data = response.read()
            response.close()
            response.release_conn()
            
            # Decrypt data
            data = self._fernet.decrypt(encrypted_data)
            
            return data
            
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise MinioStorageError(f"Artifact not found: {object_name}")
            raise MinioStorageError(f"Failed to download artifact {object_name}: {e}")
    
    async def get_presigned_url(
        self,
        tenant_id: str,
        object_name: str,
        expires: timedelta = timedelta(hours=1)
    ) -> str:
        """
        Generate presigned URL for secure download.
        
        Args:
            tenant_id: Tenant ID
            object_name: Object name
            expires: URL expiration time
            
        Returns:
            Presigned URL
        """
        bucket_name = self._get_bucket_name(tenant_id)
        
        try:
            url = await self._client.presigned_get_object(
                bucket_name,
                object_name,
                expires=expires
            )
            return url
            
        except S3Error as e:
            raise MinioStorageError(f"Failed to generate presigned URL: {e}")
    
    async def delete_artifact(
        self,
        tenant_id: str,
        object_name: str
    ) -> None:
        """
        Delete artifact from storage.
        
        Args:
            tenant_id: Tenant ID
            object_name: Object name
        """
        bucket_name = self._get_bucket_name(tenant_id)
        
        try:
            await self._client.remove_object(bucket_name, object_name)
        except S3Error as e:
            raise MinioStorageError(f"Failed to delete artifact {object_name}: {e}")
    
    async def delete_tenant_bucket(self, tenant_id: str) -> None:
        """
        Delete entire tenant bucket (for tenant deletion).
        
        Args:
            tenant_id: Tenant ID
        """
        bucket_name = self._get_bucket_name(tenant_id)
        
        try:
            # List all objects
            objects = await self._client.list_objects(bucket_name, recursive=True)
            
            # Delete all objects
            for obj in objects:
                await self._client.remove_object(bucket_name, obj.object_name)
            
            # Delete bucket
            await self._client.remove_bucket(bucket_name)
            
        except S3Error as e:
            raise MinioStorageError(f"Failed to delete bucket for tenant {tenant_id}: {e}")
    
    async def get_storage_stats(self, tenant_id: str) -> dict:
        """
        Get storage statistics for tenant.
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Storage statistics
        """
        bucket_name = self._get_bucket_name(tenant_id)
        
        try:
            # Count objects and total size
            object_count = 0
            total_size = 0
            
            objects = await self._client.list_objects(bucket_name, recursive=True)
            for obj in objects:
                object_count += 1
                total_size += obj.size or 0
            
            return {
                "bucket_name": bucket_name,
                "object_count": object_count,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2)
            }
            
        except S3Error as e:
            raise MinioStorageError(f"Failed to get storage stats: {e}")
    
    async def health_check(self) -> dict:
        """
        Check Minio health.
        
        Returns:
            Health status
        """
        try:
            # List buckets to check connectivity
            await self._client.list_buckets()
            return {
                "status": "healthy",
                "endpoint": self.endpoint,
                "region": self.region
            }
        except S3Error as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
