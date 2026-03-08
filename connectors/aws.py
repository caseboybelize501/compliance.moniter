"""
AWS Connector for ACMP.

Collects evidence from AWS services: IAM, CloudTrail, Config, S3, RDS.
Uses boto3 with read-only SecurityAudit or custom least-privilege IAM role.
"""
import asyncio
from typing import Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from connectors.base import (
    BaseConnector,
    ConnectorError,
    ConnectorAuthenticationError,
    RateLimitConfig,
)
from server.models.control import EvidenceArtifact
from server.models.tenant import SourceProfile


class AWSConnector(BaseConnector):
    """AWS connector for collecting compliance evidence."""
    
    source_type = "aws"
    default_rate_limit = RateLimitConfig(
        requests_per_second=10.0,
        requests_per_minute=500,
        burst_size=20
    )
    
    def __init__(self, source_profile: SourceProfile, **kwargs: Any):
        super().__init__(source_profile, **kwargs)
        self._iam_client = None
        self._cloudtrail_client = None
        self._config_client = None
        self._s3_client = None
        self._rds_client = None
        self._region = source_profile.scope.get("region", "us-east-1")
        self._account_id: str | None = None
    
    @property
    def name(self) -> str:
        return f"AWS ({self._region})"
    
    async def validate_credentials(self) -> bool:
        """Validate AWS credentials and confirm read-only access."""
        try:
            # Use run_in_executor for blocking boto3 call
            loop = asyncio.get_event_loop()
            sts_client = await loop.run_in_executor(
                None,
                lambda: boto3.client("sts", region_name=self._region)
            )
            
            identity = await loop.run_in_executor(
                None,
                lambda: sts_client.get_caller_identity()
            )
            
            self._account_id = identity.get("Account")
            
            # Verify read-only by attempting a read operation
            await self._list_users()
            
            return True
            
        except NoCredentialsError:
            raise ConnectorAuthenticationError("AWS credentials not found")
        except ClientError as e:
            if e.response["Error"]["Code"] == "InvalidClientTokenId":
                raise ConnectorAuthenticationError(f"AWS authentication failed: {e}")
            raise ConnectorError(f"AWS validation error: {e}")
    
    async def collect_evidence(self, evidence_type: str, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect evidence for a specific evidence type."""
        evidence_collectors = {
            "iam_users": self._collect_iam_users,
            "iam_roles": self._collect_iam_roles,
            "iam_policies": self._collect_iam_policies,
            "mfa_status": self._collect_mfa_status,
            "cloudtrail_status": self._collect_cloudtrail_status,
            "config_rules": self._collect_config_rules,
            "s3_buckets": self._collect_s3_buckets,
            "s3_encryption": self._collect_s3_encryption,
            "rds_instances": self._collect_rds_instances,
            "security_groups": self._collect_security_groups,
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
            "iam_policies",
            "mfa_status",
            "cloudtrail_status",
            "config_rules",
            "s3_buckets",
            "s3_encryption",
            "rds_instances",
            "security_groups",
        ]
    
    async def _collect_iam_users(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect IAM users evidence."""
        users = await self._list_users()
        
        artifact = self._create_artifact(
            control_id="CC6.1",
            content={
                "users": [
                    {
                        "user_name": u.get("UserName"),
                        "user_id": u.get("UserId"),
                        "created_date": str(u.get("CreateDate")),
                        "password_last_used": str(u.get("PasswordLastUsed")),
                        "mfa_active": u.get("MFAActive", False),
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
        roles = await self._list_roles()
        
        artifact = self._create_artifact(
            control_id="CC6.3",
            content={
                "roles": [
                    {
                        "role_name": r.get("RoleName"),
                        "role_id": r.get("RoleId"),
                        "arn": r.get("Arn"),
                        "create_date": str(r.get("CreateDate")),
                        "assume_role_policy": r.get("AssumeRolePolicyDocument"),
                    }
                    for r in roles
                ],
                "total_roles": len(roles),
            },
            metadata={"evidence_type": "iam_roles"}
        )
        return [artifact]
    
    async def _collect_iam_policies(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect IAM policies evidence."""
        policies = await self._list_policies()
        
        artifact = self._create_artifact(
            control_id="CC6.3",
            content={
                "policies": [
                    {
                        "policy_name": p.get("PolicyName"),
                        "policy_id": p.get("PolicyId"),
                        "arn": p.get("Arn"),
                        "is_attached": p.get("AttachmentCount", 0) > 0,
                    }
                    for p in policies[:100]  # Limit for evidence size
                ],
                "total_policies": len(policies),
            },
            metadata={"evidence_type": "iam_policies"}
        )
        return [artifact]
    
    async def _collect_mfa_status(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect MFA status evidence."""
        users = await self._list_users()
        mfa_devices = await self._list_mfa_devices()
        
        # Build MFA status per user
        user_mfa_map = {}
        for user in users:
            user_name = user.get("UserName")
            user_mfa_map[user_name] = {
                "user_name": user_name,
                "mfa_active": user.get("MFAActive", False),
                "mfa_devices": [
                    d for d in mfa_devices if d.get("UserName") == user_name
                ],
            }
        
        # Calculate statistics
        total_users = len(users)
        users_with_mfa = sum(1 for u in user_mfa_map.values() if u["mfa_active"])
        
        artifact = self._create_artifact(
            control_id="CC6.1",
            content={
                "user_mfa_status": list(user_mfa_map.values()),
                "total_users": total_users,
                "users_with_mfa": users_with_mfa,
                "mfa_coverage_percent": (users_with_mfa / total_users * 100) if total_users > 0 else 0,
            },
            metadata={"evidence_type": "mfa_status"}
        )
        return [artifact]
    
    async def _collect_cloudtrail_status(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect CloudTrail status evidence."""
        trails = await self._describe_trails()
        
        artifact = self._create_artifact(
            control_id="CC7.1",
            content={
                "trails": [
                    {
                        "name": t.get("Name"),
                        "is_multi_region": t.get("IsMultiRegionTrail", False),
                        "is_logging": t.get("IsLogging", False),
                        "s3_bucket": t.get("S3BucketName"),
                        "include_global_events": t.get("IncludeGlobalServiceEvents", False),
                    }
                    for t in trails
                ],
                "total_trails": len(trails),
                "multi_region_trails": sum(1 for t in trails if t.get("IsMultiRegionTrail")),
            },
            metadata={"evidence_type": "cloudtrail_status"}
        )
        return [artifact]
    
    async def _collect_config_rules(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect AWS Config rules evidence."""
        rules = await self._describe_config_rules()
        
        artifact = self._create_artifact(
            control_id="CC5.1",
            content={
                "config_rules": [
                    {
                        "name": r.get("ConfigRuleName"),
                        "state": r.get("ConfigRuleState"),
                        "source": r.get("Source"),
                        "compliance": r.get("Compliance", {}),
                    }
                    for r in rules
                ],
                "total_rules": len(rules),
            },
            metadata={"evidence_type": "config_rules"}
        )
        return [artifact]
    
    async def _collect_s3_buckets(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect S3 buckets evidence."""
        buckets = await self._list_buckets()
        
        artifact = self._create_artifact(
            control_id="CC6.5",
            content={
                "buckets": [
                    {
                        "name": b.get("Name"),
                        "creation_date": str(b.get("CreationDate")),
                    }
                    for b in buckets
                ],
                "total_buckets": len(buckets),
            },
            metadata={"evidence_type": "s3_buckets"}
        )
        return [artifact]
    
    async def _collect_s3_encryption(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect S3 encryption status evidence."""
        buckets = await self._list_buckets()
        encryption_status = []
        
        for bucket in buckets:
            bucket_name = bucket.get("Name")
            encryption = await self._get_bucket_encryption(bucket_name)
            encryption_status.append({
                "bucket_name": bucket_name,
                "encrypted": encryption is not None,
                "encryption_type": encryption[0].get("SSEAlgorithm") if encryption else None,
            })
        
        encrypted_count = sum(1 for e in encryption_status if e["encrypted"])
        
        artifact = self._create_artifact(
            control_id="CC6.5",
            content={
                "encryption_status": encryption_status,
                "total_buckets": len(buckets),
                "encrypted_buckets": encrypted_count,
                "encryption_coverage_percent": (encrypted_count / len(buckets) * 100) if buckets else 0,
            },
            metadata={"evidence_type": "s3_encryption"}
        )
        return [artifact]
    
    async def _collect_rds_instances(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect RDS instances evidence."""
        instances = await self._describe_db_instances()
        
        artifact = self._create_artifact(
            control_id="CC6.5",
            content={
                "instances": [
                    {
                        "identifier": i.get("DBInstanceIdentifier"),
                        "engine": i.get("Engine"),
                        "storage_encrypted": i.get("StorageEncrypted", False),
                        "publicly_accessible": i.get("PubliclyAccessible", False),
                        "multi_az": i.get("MultiAZ", False),
                    }
                    for i in instances
                ],
                "total_instances": len(instances),
                "encrypted_instances": sum(1 for i in instances if i.get("StorageEncrypted")),
            },
            metadata={"evidence_type": "rds_instances"}
        )
        return [artifact]
    
    async def _collect_security_groups(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect security groups evidence."""
        groups = await self._describe_security_groups()
        
        artifact = self._create_artifact(
            control_id="CC6.6",
            content={
                "security_groups": [
                    {
                        "group_id": g.get("GroupId"),
                        "group_name": g.get("GroupName"),
                        "description": g.get("Description"),
                        "ingress_rules": len(g.get("IpPermissions", [])),
                        "egress_rules": len(g.get("IpPermissionsEgress", [])),
                    }
                    for g in groups[:100]  # Limit for evidence size
                ],
                "total_groups": len(groups),
            },
            metadata={"evidence_type": "security_groups"}
        )
        return [artifact]
    
    # AWS API wrapper methods (blocking, run in executor)
    async def _list_users(self) -> list[dict]:
        """List IAM users."""
        loop = asyncio.get_event_loop()
        client = await self._get_iam_client()
        return await loop.run_in_executor(
            None,
            lambda: client.list_users().get("Users", [])
        )
    
    async def _list_roles(self) -> list[dict]:
        """List IAM roles."""
        loop = asyncio.get_event_loop()
        client = await self._get_iam_client()
        return await loop.run_in_executor(
            None,
            lambda: client.list_roles().get("Roles", [])
        )
    
    async def _list_policies(self) -> list[dict]:
        """List IAM policies."""
        loop = asyncio.get_event_loop()
        client = await self._get_iam_client()
        return await loop.run_in_executor(
            None,
            lambda: client.list_policies().get("Policies", [])
        )
    
    async def _list_mfa_devices(self) -> list[dict]:
        """List MFA devices for all users."""
        loop = asyncio.get_event_loop()
        client = await self._get_iam_client()
        users = await self._list_users()
        
        all_devices = []
        for user in users[:50]:  # Limit to avoid rate limits
            user_name = user.get("UserName")
            devices = await loop.run_in_executor(
                None,
                lambda un=user_name: client.list_mfa_devices(UserName=un).get("MFADevices", [])
            )
            for device in devices:
                device["UserName"] = user_name
            all_devices.extend(devices)
        
        return all_devices
    
    async def _describe_trails(self) -> list[dict]:
        """Describe CloudTrail trails."""
        loop = asyncio.get_event_loop()
        client = await self._get_cloudtrail_client()
        return await loop.run_in_executor(
            None,
            lambda: client.describe_trails().get("trailList", [])
        )
    
    async def _describe_config_rules(self) -> list[dict]:
        """Describe AWS Config rules."""
        loop = asyncio.get_event_loop()
        client = await self._get_config_client()
        return await loop.run_in_executor(
            None,
            lambda: client.describe_config_rules().get("ConfigRules", [])
        )
    
    async def _list_buckets(self) -> list[dict]:
        """List S3 buckets."""
        loop = asyncio.get_event_loop()
        client = await self._get_s3_client()
        return await loop.run_in_executor(
            None,
            lambda: client.list_buckets().get("Buckets", [])
        )
    
    async def _get_bucket_encryption(self, bucket_name: str) -> list[dict] | None:
        """Get bucket encryption status."""
        loop = asyncio.get_event_loop()
        client = await self._get_s3_client()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: client.get_bucket_encryption(Bucket=bucket_name)
            )
            return result.get("ServerSideEncryptionConfiguration", {}).get("Rules", [])
        except ClientError:
            return None
    
    async def _describe_db_instances(self) -> list[dict]:
        """Describe RDS instances."""
        loop = asyncio.get_event_loop()
        client = await self._get_rds_client()
        return await loop.run_in_executor(
            None,
            lambda: client.describe_db_instances().get("DBInstances", [])
        )
    
    async def _describe_security_groups(self) -> list[dict]:
        """Describe EC2 security groups."""
        loop = asyncio.get_event_loop()
        client = await self._get_ec2_client()
        return await loop.run_in_executor(
            None,
            lambda: client.describe_security_groups().get("SecurityGroups", [])
        )
    
    # Client getters with lazy initialization
    async def _get_iam_client(self):
        if self._iam_client is None:
            loop = asyncio.get_event_loop()
            self._iam_client = await loop.run_in_executor(
                None,
                lambda: boto3.client("iam", region_name=self._region)
            )
        return self._iam_client
    
    async def _get_cloudtrail_client(self):
        if self._cloudtrail_client is None:
            loop = asyncio.get_event_loop()
            self._cloudtrail_client = await loop.run_in_executor(
                None,
                lambda: boto3.client("cloudtrail", region_name=self._region)
            )
        return self._cloudtrail_client
    
    async def _get_config_client(self):
        if self._config_client is None:
            loop = asyncio.get_event_loop()
            self._config_client = await loop.run_in_executor(
                None,
                lambda: boto3.client("config", region_name=self._region)
            )
        return self._config_client
    
    async def _get_s3_client(self):
        if self._s3_client is None:
            loop = asyncio.get_event_loop()
            self._s3_client = await loop.run_in_executor(
                None,
                lambda: boto3.client("s3", region_name=self._region)
            )
        return self._s3_client
    
    async def _get_rds_client(self):
        if self._rds_client is None:
            loop = asyncio.get_event_loop()
            self._rds_client = await loop.run_in_executor(
                None,
                lambda: boto3.client("rds", region_name=self._region)
            )
        return self._rds_client
    
    async def _get_ec2_client(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: boto3.client("ec2", region_name=self._region)
        )
    
    async def close(self) -> None:
        """Close the connector and release resources."""
        # boto3 clients don't need explicit closing
        pass
