"""
GCP Connector for ACMP.

Collects evidence from GCP: IAM, audit logs, GCS, KMS.
Uses google-api-python-client with service account credentials.
"""
import asyncio
import json
from typing import Any
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from connectors.base import (
    BaseConnector,
    ConnectorError,
    ConnectorAuthenticationError,
    RateLimitConfig,
)
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
        self._credentials: service_account.Credentials | None = None
    
    @property
    def name(self) -> str:
        return f"GCP ({self._project_id})"
    
    async def validate_credentials(self) -> bool:
        """Validate GCP service account credentials."""
        try:
            loop = asyncio.get_event_loop()
            
            def _validate():
                if not self._credentials_path:
                    raise ConnectorAuthenticationError("Credentials path not configured")
                
                credentials = service_account.Credentials.from_service_account_file(
                    self._credentials_path,
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
                
                # Test by listing projects
                service = build('cloudresourcemanager', 'v1', credentials=credentials)
                projects = service.projects().list().execute()
                
                # Check if our project is accessible
                project_ids = [p['projectId'] for p in projects.get('projects', [])]
                if self._project_id and self._project_id not in project_ids:
                    raise ConnectorAuthenticationError(f"Project {self._project_id} not accessible")
                
                self._credentials = credentials
                return True
            
            return await loop.run_in_executor(None, _validate)
            
        except HttpError as e:
            if e.resp.status == 401:
                raise ConnectorAuthenticationError(f"GCP authentication failed: {e}")
            raise ConnectorError(f"GCP validation error: {e}")
        except Exception as e:
            raise ConnectorError(f"GCP validation error: {e}")
    
    async def collect_evidence(self, evidence_type: str, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect evidence for a specific evidence type."""
        evidence_collectors = {
            "iam_users": self._collect_iam_users,
            "iam_roles": self._collect_iam_roles,
            "audit_logs": self._collect_audit_logs,
            "gcs_buckets": self._collect_gcs_buckets,
            "gcs_encryption": self._collect_gcs_encryption,
            "kms_keys": self._collect_kms_keys,
        }
        
        collector = evidence_collectors.get(evidence_type)
        if not collector:
            raise ConnectorError(f"Unknown evidence type: {evidence_type}")
        
        return await collector(**kwargs)
    
    async def get_available_evidence_types(self) -> list[str]:
        """Get list of evidence types this connector can collect."""
        return [
            "iam_users",
            "iam_roles",
            "audit_logs",
            "gcs_buckets",
            "gcs_encryption",
            "kms_keys",
        ]
    
    async def _collect_iam_users(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect IAM users evidence."""
        loop = asyncio.get_event_loop()
        
        def _list():
            service = build('admin', 'directory_v1', credentials=self._credentials)
            users = service.users().list(customer='my_customer').execute()
            return users.get('users', [])
        
        users = await loop.run_in_executor(None, _list)
        
        artifact = self._create_artifact(
            control_id="CC6.1",
            content={
                "users": [
                    {
                        "email": u.get("primaryEmail"),
                        "name": u.get("name", {}).get("fullName"),
                        "creation_time": u.get("creationTime"),
                        "is_admin": u.get("isAdmin", False),
                        "is_mfa_enrolled": len(u.get("phones", [])) > 0,
                    }
                    for u in users
                ],
                "total_users": len(users),
            },
            metadata={"evidence_type": "iam_users"}
        )
        return [artifact]
    
    async def _collect_iam_roles(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect IAM roles evidence."""
        loop = asyncio.get_event_loop()
        
        def _list():
            service = build('iam', 'v1', credentials=self._credentials)
            roles = service.projects().roles().list(parent=f"projects/{self._project_id}").execute()
            return roles.get('roles', [])
        
        roles = await loop.run_in_executor(None, _list)
        
        artifact = self._create_artifact(
            control_id="CC6.3",
            content={
                "roles": [
                    {
                        "name": r.get("name"),
                        "title": r.get("title"),
                        "description": r.get("description"),
                        "stage": r.get("stage"),
                    }
                    for r in roles
                ],
                "total_roles": len(roles),
            },
            metadata={"evidence_type": "iam_roles"}
        )
        return [artifact]
    
    async def _collect_audit_logs(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect audit logs configuration evidence."""
        loop = asyncio.get_event_loop()
        
        def _list():
            service = build('logging', 'v2', credentials=self._credentials)
            sinks = service.projects().sinks().list(parent=f"projects/{self._project_id}").execute()
            return sinks.get('sinks', [])
        
        sinks = await loop.run_in_executor(None, _list)
        
        artifact = self._create_artifact(
            control_id="CC7.1",
            content={
                "audit_sinks": [
                    {
                        "name": s.get("name"),
                        "destination": s.get("destination"),
                        "filter": s.get("filter"),
                    }
                    for s in sinks
                ],
                "total_sinks": len(sinks),
            },
            metadata={"evidence_type": "audit_logs"}
        )
        return [artifact]
    
    async def _collect_gcs_buckets(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect GCS buckets evidence."""
        loop = asyncio.get_event_loop()
        
        def _list():
            service = build('storage', 'v1', credentials=self._credentials)
            buckets = service.buckets().list(project=self._project_id).execute()
            return buckets.get('items', [])
        
        buckets = await loop.run_in_executor(None, _list)
        
        artifact = self._create_artifact(
            control_id="CC6.5",
            content={
                "buckets": [
                    {
                        "name": b.get("name"),
                        "location": b.get("location"),
                        "storage_class": b.get("storageClass"),
                        "created": b.get("timeCreated"),
                    }
                    for b in buckets
                ],
                "total_buckets": len(buckets),
            },
            metadata={"evidence_type": "gcs_buckets"}
        )
        return [artifact]
    
    async def _collect_gcs_encryption(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect GCS encryption status evidence."""
        loop = asyncio.get_event_loop()
        
        def _list():
            service = build('storage', 'v1', credentials=self._credentials)
            buckets = service.buckets().list(project=self._project_id).execute()
            
            encryption_status = []
            for bucket in buckets.get('items', []):
                encryption = bucket.get('encryption', {})
                encryption_status.append({
                    "bucket_name": bucket.get("name"),
                    "default_kms_key": encryption.get("defaultKmsKeyName"),
                    "encrypted": bool(encryption.get("defaultKmsKeyName")),
                })
            
            return encryption_status
        
        encryption_status = await loop.run_in_executor(None, _list)
        
        encrypted_count = sum(1 for e in encryption_status if e["encrypted"])
        
        artifact = self._create_artifact(
            control_id="CC6.5",
            content={
                "encryption_status": encryption_status,
                "total_buckets": len(encryption_status),
                "encrypted_buckets": encrypted_count,
                "encryption_coverage_percent": (encrypted_count / len(encryption_status) * 100) if encryption_status else 0,
            },
            metadata={"evidence_type": "gcs_encryption"}
        )
        return [artifact]
    
    async def _collect_kms_keys(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect KMS keys evidence."""
        loop = asyncio.get_event_loop()
        
        def _list():
            service = build('cloudkms', 'v1', credentials=self._credentials)
            key_rings = service.projects().locations().keyRings().list(
                parent=f"projects/{self._project_id}/locations/global"
            ).execute()
            
            all_keys = []
            for ring in key_rings.get('keyRings', []):
                keys = service.projects().locations().keyRings().cryptoKeys().list(
                    parent=ring['name']
                ).execute()
                all_keys.extend(keys.get('cryptoKeys', []))
            
            return all_keys
        
        keys = await loop.run_in_executor(None, _list)
        
        artifact = self._create_artifact(
            control_id="CC6.5",
            content={
                "kms_keys": [
                    {
                        "name": k.get("name"),
                        "purpose": k.get("purpose"),
                        "rotation_period": k.get("rotationPeriod"),
                        "next_rotation_time": k.get("nextRotationTime"),
                    }
                    for k in keys
                ],
                "total_keys": len(keys),
            },
            metadata={"evidence_type": "kms_keys"}
        )
        return [artifact]
    
    async def close(self) -> None:
        """Close the connector."""
        self._credentials = None
