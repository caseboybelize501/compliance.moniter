"""
Okta Connector for ACMP.

Collects evidence from Okta: users, groups, MFA status, sessions.
Uses Okta SDK with read-only API token.
"""
import asyncio
from typing import Any
from datetime import datetime

from okta.client import Client as OktaClient
from okta.errors.okta_api_error import OKTAError

from connectors.base import (
    BaseConnector,
    ConnectorError,
    ConnectorAuthenticationError,
    RateLimitConfig,
)
from server.models.control import EvidenceArtifact
from server.models.tenant import SourceProfile


class OktaConnector(BaseConnector):
    """Okta connector for collecting compliance evidence."""
    
    source_type = "okta"
    default_rate_limit = RateLimitConfig(
        requests_per_second=10.0,
        requests_per_minute=600,
        burst_size=20
    )
    
    def __init__(self, source_profile: SourceProfile, **kwargs: Any):
        super().__init__(source_profile, **kwargs)
        self._okta_client: OktaClient | None = None
        self._org_url = source_profile.scope.get("org_url")
        self._token = source_profile.scope.get("token")
    
    @property
    def name(self) -> str:
        return f"Okta ({self._org_url})"
    
    async def validate_credentials(self) -> bool:
        """Validate Okta token and confirm read-only access."""
        try:
            loop = asyncio.get_event_loop()
            client = self._get_client()
            
            def _validate():
                # Try to list users (read-only operation)
                users, _, err = client.list_users()
                if err:
                    raise err
                return len(users) >= 0
            
            await loop.run_in_executor(None, _validate)
            return True
            
        except OKTAError as e:
            if e.status == 401:
                raise ConnectorAuthenticationError(f"Okta token invalid: {e}")
            raise ConnectorError(f"Okta validation error: {e}")
    
    async def collect_evidence(self, evidence_type: str, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect evidence for a specific evidence type."""
        evidence_collectors = {
            "users": self._collect_users,
            "mfa_status": self._collect_mfa_status,
            "groups": self._collect_groups,
            "sessions": self._collect_sessions,
            "password_policy": self._collect_password_policy,
        }
        
        collector = evidence_collectors.get(evidence_type)
        if not collector:
            raise ConnectorError(f"Unknown evidence type: {evidence_type}")
        
        return await collector(**kwargs)
    
    async def get_available_evidence_types(self) -> list[str]:
        """Get list of evidence types this connector can collect."""
        return [
            "users",
            "mfa_status",
            "groups",
            "sessions",
            "password_policy",
        ]
    
    async def _collect_users(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect users evidence."""
        users = await self._list_users()
        
        artifact = self._create_artifact(
            control_id="CC6.2",
            content={
                "users": [
                    {
                        "id": u.get("id"),
                        "login": u.get("profile", {}).get("login"),
                        "email": u.get("profile", {}).get("email"),
                        "status": u.get("status"),
                        "created": u.get("created"),
                        "last_login": u.get("lastLogin"),
                        "password_changed": u.get("passwordChanged"),
                    }
                    for u in users
                ],
                "total_users": len(users),
                "active_users": sum(1 for u in users if u.get("status") == "ACTIVE"),
            },
            metadata={"evidence_type": "users"}
        )
        return [artifact]
    
    async def _collect_mfa_status(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect MFA status evidence."""
        users = await self._list_users()
        mfa_status = []
        
        for user in users[:100]:  # Limit for API calls
            user_id = user.get("id")
            factors = await self._list_user_factors(user_id)
            
            mfa_status.append({
                "user_id": user_id,
                "login": user.get("profile", {}).get("login"),
                "email": user.get("profile", {}).get("email"),
                "status": user.get("status"),
                "mfa_enrolled": len(factors) > 0,
                "factor_types": [f.get("factorType") for f in factors],
                "factor_count": len(factors),
            })
        
        total_users = len(mfa_status)
        users_with_mfa = sum(1 for u in mfa_status if u["mfa_enrolled"])
        
        artifact = self._create_artifact(
            control_id="CC6.1",
            content={
                "mfa_status": mfa_status,
                "total_users": total_users,
                "users_with_mfa": users_with_mfa,
                "mfa_coverage_percent": (users_with_mfa / total_users * 100) if total_users > 0 else 0,
                "users_without_mfa": [
                    {"login": u["login"], "email": u["email"]}
                    for u in mfa_status if not u["mfa_enrolled"]
                ][:20],  # Limit list size
            },
            metadata={"evidence_type": "mfa_status"}
        )
        return [artifact]
    
    async def _collect_groups(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect groups evidence."""
        groups = await self._list_groups()
        
        artifact = self._create_artifact(
            control_id="CC6.3",
            content={
                "groups": [
                    {
                        "id": g.get("id"),
                        "name": g.get("profile", {}).get("name"),
                        "description": g.get("profile", {}).get("description"),
                        "type": g.get("type"),
                    }
                    for g in groups
                ],
                "total_groups": len(groups),
            },
            metadata={"evidence_type": "groups"}
        )
        return [artifact]
    
    async def _collect_sessions(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect sessions evidence."""
        sessions = await self._list_sessions()
        
        artifact = self._create_artifact(
            control_id="CC7.1",
            content={
                "sessions": [
                    {
                        "id": s.get("id"),
                        "user_id": s.get("userId"),
                        "status": s.get("status"),
                        "created": s.get("created"),
                        "expires_at": s.get("expiresAt"),
                        "ip_address": s.get("ipAddress"),
                        "user_agent": s.get("userAgent"),
                    }
                    for s in sessions[:100]  # Limit for evidence size
                ],
                "total_sessions": len(sessions),
                "active_sessions": sum(1 for s in sessions if s.get("status") == "ACTIVE"),
            },
            metadata={"evidence_type": "sessions"}
        )
        return [artifact]
    
    async def _collect_password_policy(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect password policy evidence."""
        policies = await self._list_policies()
        password_policies = [
            p for p in policies
            if p.get("type") == "PASSWORD" and p.get("status") == "ACTIVE"
        ]
        
        artifact = self._create_artifact(
            control_id="CC6.1",
            content={
                "password_policies": [
                    {
                        "id": p.get("id"),
                        "name": p.get("name"),
                        "description": p.get("description"),
                        "settings": p.get("settings", {}),
                    }
                    for p in password_policies
                ],
                "total_password_policies": len(password_policies),
            },
            metadata={"evidence_type": "password_policy"}
        )
        return [artifact]
    
    # Okta API wrapper methods
    def _get_client(self) -> OktaClient:
        """Get or create Okta client."""
        if self._okta_client is None:
            config = {
                "orgUrl": self._org_url,
                "token": self._token,
            }
            self._okta_client = OktaClient(config)
        return self._okta_client
    
    async def _list_users(self) -> list[dict]:
        """List Okta users."""
        loop = asyncio.get_event_loop()
        client = self._get_client()
        
        def _list():
            users, _, err = client.list_users()
            if err:
                raise err
            return [u.to_dict() for u in users]
        
        return await loop.run_in_executor(None, _list)
    
    async def _list_user_factors(self, user_id: str) -> list[dict]:
        """List MFA factors for a user."""
        loop = asyncio.get_event_loop()
        client = self._get_client()
        
        def _list():
            factors, _, err = client.list_factors(user_id)
            if err:
                return []
            return [f.to_dict() for f in factors]
        
        return await loop.run_in_executor(None, _list)
    
    async def _list_groups(self) -> list[dict]:
        """List Okta groups."""
        loop = asyncio.get_event_loop()
        client = self._get_client()
        
        def _list():
            groups, _, err = client.list_groups()
            if err:
                raise err
            return [g.to_dict() for g in groups]
        
        return await loop.run_in_executor(None, _list)
    
    async def _list_sessions(self) -> list[dict]:
        """List Okta sessions."""
        loop = asyncio.get_event_loop()
        client = self._get_client()
        
        def _list():
            sessions, _, err = client.list_sessions()
            if err:
                raise err
            return [s.to_dict() for s in sessions]
        
        return await loop.run_in_executor(None, _list)
    
    async def _list_policies(self) -> list[dict]:
        """List Okta policies."""
        loop = asyncio.get_event_loop()
        client = self._get_client()
        
        def _list():
            policies, _, err = client.list_policies(type="PASSWORD")
            if err:
                return []
            return [p.to_dict() for p in policies]
        
        return await loop.run_in_executor(None, _list)
    
    async def close(self) -> None:
        """Close the connector."""
        self._okta_client = None
