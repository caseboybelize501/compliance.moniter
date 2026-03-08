"""
Azure Connector for ACMP.

Collects evidence from Azure: RBAC, policy, key vault, storage.
Uses azure-identity and azure-mgmt libraries.
"""
import asyncio
from typing import Any
from datetime import datetime

from azure.identity import ClientSecretCredential
from azure.mgmt.resource import SubscriptionClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.keyvault import KeyVaultManagementClient
from azure.mgmt.authorization import AuthorizationManagementClient
from azure.core.exceptions import AzureError

from connectors.base import (
    BaseConnector,
    ConnectorError,
    ConnectorAuthenticationError,
    RateLimitConfig,
)
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
        self._client_secret = source_profile.scope.get("client_secret")
        self._subscription_id = source_profile.scope.get("subscription_id")
        self._credentials: ClientSecretCredential | None = None
    
    @property
    def name(self) -> str:
        return f"Azure ({self._subscription_id})"
    
    async def validate_credentials(self) -> bool:
        """Validate Azure service principal credentials."""
        try:
            loop = asyncio.get_event_loop()
            
            def _validate():
                if not all([self._tenant_id, self._client_id, self._client_secret]):
                    raise ConnectorAuthenticationError("Missing Azure credentials")
                
                credentials = ClientSecretCredential(
                    tenant_id=self._tenant_id,
                    client_id=self._client_id,
                    client_secret=self._client_secret
                )
                
                # Test by listing subscriptions
                subscription_client = SubscriptionClient(credentials)
                subscriptions = list(subscription_client.subscriptions.list())
                
                # Check if our subscription is accessible
                if self._subscription_id:
                    subscription_ids = [str(s.subscription_id) for s in subscriptions]
                    if self._subscription_id not in subscription_ids:
                        raise ConnectorAuthenticationError(f"Subscription {self._subscription_id} not accessible")
                
                self._credentials = credentials
                return True
            
            return await loop.run_in_executor(None, _validate)
            
        except AzureError as e:
            if "invalid" in str(e).lower():
                raise ConnectorAuthenticationError(f"Azure authentication failed: {e}")
            raise ConnectorError(f"Azure validation error: {e}")
        except Exception as e:
            raise ConnectorError(f"Azure validation error: {e}")
    
    async def collect_evidence(self, evidence_type: str, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect evidence for a specific evidence type."""
        evidence_collectors = {
            "rbac_users": self._collect_rbac_users,
            "rbac_roles": self._collect_rbac_roles,
            "policy_assignments": self._collect_policy_assignments,
            "key_vault_keys": self._collect_key_vault_keys,
            "storage_accounts": self._collect_storage_accounts,
            "storage_encryption": self._collect_storage_encryption,
        }
        
        collector = evidence_collectors.get(evidence_type)
        if not collector:
            raise ConnectorError(f"Unknown evidence type: {evidence_type}")
        
        return await collector(**kwargs)
    
    async def get_available_evidence_types(self) -> list[str]:
        """Get list of evidence types this connector can collect."""
        return [
            "rbac_users",
            "rbac_roles",
            "policy_assignments",
            "key_vault_keys",
            "storage_accounts",
            "storage_encryption",
        ]
    
    async def _collect_rbac_users(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect RBAC users evidence."""
        loop = asyncio.get_event_loop()
        
        def _list():
            auth_client = AuthorizationManagementClient(self._credentials, self._subscription_id)
            # Get role assignments
            assignments = list(auth_client.role_assignments.list_for_subscription())
            
            users = {}
            for assignment in assignments:
                principal_id = assignment.principal_id
                if principal_id not in users:
                    users[principal_id] = {
                        "principal_id": principal_id,
                        "roles": []
                    }
                # Extract role name from scope
                role_name = assignment.role_definition_id.split('/')[-1] if assignment.role_definition_id else "Unknown"
                users[principal_id]["roles"].append(role_name)
            
            return list(users.values())
        
        users = await loop.run_in_executor(None, _list)
        
        artifact = self._create_artifact(
            control_id="CC6.3",
            content={
                "users": users,
                "total_users": len(users),
            },
            metadata={"evidence_type": "rbac_users"}
        )
        return [artifact]
    
    async def _collect_rbac_roles(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect RBAC roles evidence."""
        loop = asyncio.get_event_loop()
        
        def _list():
            auth_client = AuthorizationManagementClient(self._credentials, self._subscription_id)
            roles = list(auth_client.role_definitions.list(scope=f"/subscriptions/{self._subscription_id}"))
            return [
                {
                    "name": r.role_name,
                    "id": r.name,
                    "description": r.description,
                    "is_custom": r.is_custom,
                }
                for r in roles
            ]
        
        roles = await loop.run_in_executor(None, _list)
        
        artifact = self._create_artifact(
            control_id="CC6.3",
            content={
                "roles": roles,
                "total_roles": len(roles),
                "custom_roles": sum(1 for r in roles if r["is_custom"]),
            },
            metadata={"evidence_type": "rbac_roles"}
        )
        return [artifact]
    
    async def _collect_policy_assignments(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect Azure Policy assignments evidence."""
        loop = asyncio.get_event_loop()
        
        def _list():
            from azure.mgmt.resource import PolicyClient
            policy_client = PolicyClient(self._credentials, self._subscription_id)
            assignments = list(policy_client.policy_assignments.list())
            return [
                {
                    "name": a.name,
                    "display_name": a.display_name,
                    "scope": a.scope,
                    "enforcement_mode": a.enforcement_mode.value if a.enforcement_mode else "Default",
                }
                for a in assignments
            ]
        
        assignments = await loop.run_in_executor(None, _list)
        
        artifact = self._create_artifact(
            control_id="CC5.1",
            content={
                "policy_assignments": assignments,
                "total_assignments": len(assignments),
            },
            metadata={"evidence_type": "policy_assignments"}
        )
        return [artifact]
    
    async def _collect_key_vault_keys(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect Key Vault keys evidence."""
        loop = asyncio.get_event_loop()
        
        def _list():
            kv_client = KeyVaultManagementClient(self._credentials, self._subscription_id)
            vaults = list(kv_client.vaults.list_by_subscription())
            
            all_keys = []
            for vault in vaults:
                # Parse vault name and resource group from ID
                parts = vault.id.split('/')
                resource_group = parts[4]
                vault_name = vault.name
                
                try:
                    keys = list(kv_client.keys.list_by_vault(resource_group, vault_name))
                    for key in keys:
                        all_keys.append({
                            "vault_name": vault_name,
                            "key_name": key.name,
                            "key_type": key.attributes.key_type if key.attributes else None,
                            "enabled": key.attributes.enabled if key.attributes else False,
                            "expires": str(key.attributes.expires) if key.attributes and key.attributes.expires else None,
                        })
                except Exception:
                    # Skip vaults we can't access
                    continue
            
            return all_keys
        
        keys = await loop.run_in_executor(None, _list)
        
        artifact = self._create_artifact(
            control_id="CC6.5",
            content={
                "keys": keys,
                "total_keys": len(keys),
                "vaults": len(set(k["vault_name"] for k in keys)),
            },
            metadata={"evidence_type": "key_vault_keys"}
        )
        return [artifact]
    
    async def _collect_storage_accounts(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect storage accounts evidence."""
        loop = asyncio.get_event_loop()
        
        def _list():
            storage_client = StorageManagementClient(self._credentials, self._subscription_id)
            accounts = list(storage_client.storage_accounts.list())
            return [
                {
                    "name": a.name,
                    "location": a.location,
                    "sku": a.sku.name.value if a.sku else None,
                    "kind": a.kind,
                    "creation_time": str(a.creation_time) if a.creation_time else None,
                }
                for a in accounts
            ]
        
        accounts = await loop.run_in_executor(None, _list)
        
        artifact = self._create_artifact(
            control_id="CC6.5",
            content={
                "storage_accounts": accounts,
                "total_accounts": len(accounts),
            },
            metadata={"evidence_type": "storage_accounts"}
        )
        return [artifact]
    
    async def _collect_storage_encryption(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect storage encryption status evidence."""
        loop = asyncio.get_event_loop()
        
        def _list():
            storage_client = StorageManagementClient(self._credentials, self._subscription_id)
            accounts = list(storage_client.storage_accounts.list())
            
            encryption_status = []
            for account in accounts:
                encryption = account.encryption
                encryption_status.append({
                    "name": account.name,
                    "services": {
                        "blob": {
                            "enabled": encryption.services.blob.enabled if encryption.services and encryption.services.blob else False,
                        },
                        "file": {
                            "enabled": encryption.services.file.enabled if encryption.services and encryption.services.file else False,
                        },
                    },
                    "key_source": encryption.key_source if encryption else "Unknown",
                })
            
            return encryption_status
        
        encryption_status = await loop.run_in_executor(None, _list)
        
        # Calculate encryption coverage
        encrypted = sum(
            1 for e in encryption_status
            if e["services"]["blob"]["enabled"] and e["services"]["file"]["enabled"]
        )
        
        artifact = self._create_artifact(
            control_id="CC6.5",
            content={
                "encryption_status": encryption_status,
                "total_accounts": len(encryption_status),
                "fully_encrypted": encrypted,
                "encryption_coverage_percent": (encrypted / len(encryption_status) * 100) if encryption_status else 0,
            },
            metadata={"evidence_type": "storage_encryption"}
        )
        return [artifact]
    
    async def close(self) -> None:
        """Close the connector."""
        self._credentials = None
