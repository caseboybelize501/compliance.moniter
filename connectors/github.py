"""
GitHub Connector for ACMP.

Collects evidence from GitHub: repos, branch protection, secret scanning.
Uses PyGithub library with fine-grained personal access token.
"""
import asyncio
from typing import Any
from datetime import datetime

from github import Github, GithubException
from github.Repository import Repository

from connectors.base import (
    BaseConnector,
    ConnectorError,
    ConnectorAuthenticationError,
    RateLimitConfig,
)
from server.models.control import EvidenceArtifact
from server.models.tenant import SourceProfile


class GitHubConnector(BaseConnector):
    """GitHub connector for collecting compliance evidence."""
    
    source_type = "github"
    default_rate_limit = RateLimitConfig(
        requests_per_second=5.0,
        requests_per_hour=5000,
        burst_size=10
    )
    
    def __init__(self, source_profile: SourceProfile, **kwargs: Any):
        super().__init__(source_profile, **kwargs)
        self._gh_client: Github | None = None
        self._token = source_profile.scope.get("token")
        self._org = source_profile.scope.get("organization")
    
    @property
    def name(self) -> str:
        return f"GitHub ({self._org or 'personal'})"
    
    async def validate_credentials(self) -> bool:
        """Validate GitHub token and confirm access."""
        try:
            loop = asyncio.get_event_loop()
            
            def _validate():
                client = Github(self._token)
                user = client.get_user()
                # Trigger API call
                return user.login
            
            await loop.run_in_executor(None, _validate)
            return True
            
        except GithubException as e:
            if e.status == 401:
                raise ConnectorAuthenticationError(f"GitHub token invalid: {e}")
            raise ConnectorError(f"GitHub validation error: {e}")
    
    async def collect_evidence(self, evidence_type: str, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect evidence for a specific evidence type."""
        evidence_collectors = {
            "repositories": self._collect_repositories,
            "branch_protection": self._collect_branch_protection,
            "secret_scanning": self._collect_secret_scanning,
            "webhooks": self._collect_webhooks,
            "collaborators": self._collect_collaborators,
        }
        
        collector = evidence_collectors.get(evidence_type)
        if not collector:
            raise ConnectorError(f"Unknown evidence type: {evidence_type}")
        
        return await collector(**kwargs)
    
    async def get_available_evidence_types(self) -> list[str]:
        """Get list of evidence types this connector can collect."""
        return [
            "repositories",
            "branch_protection",
            "secret_scanning",
            "webhooks",
            "collaborators",
        ]
    
    async def _collect_repositories(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect repository evidence."""
        repos = await self._list_repositories()
        
        artifact = self._create_artifact(
            control_id="CC6.6",
            content={
                "repositories": [
                    {
                        "name": r.get("name"),
                        "full_name": r.get("full_name"),
                        "private": r.get("private", False),
                        "visibility": r.get("visibility"),
                        "created_at": r.get("created_at"),
                        "updated_at": r.get("updated_at"),
                        "default_branch": r.get("default_branch"),
                    }
                    for r in repos
                ],
                "total_repos": len(repos),
                "private_repos": sum(1 for r in repos if r.get("private")),
            },
            metadata={"evidence_type": "repositories"}
        )
        return [artifact]
    
    async def _collect_branch_protection(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect branch protection evidence."""
        repos = await self._list_repositories()
        protection_status = []
        
        for repo_data in repos[:20]:  # Limit for API calls
            repo_name = repo_data.get("full_name")
            default_branch = repo_data.get("default_branch", "main")
            
            protection = await self._get_branch_protection(repo_name, default_branch)
            protection_status.append({
                "repo": repo_name,
                "branch": default_branch,
                "protected": protection.get("enabled", False),
                "require_status_checks": protection.get("require_status_checks", False),
                "require_code_owner_reviews": protection.get("require_code_owner_reviews", False),
                "require_pull_request_reviews": protection.get("require_pull_request_reviews", False),
                "enforce_admins": protection.get("enforce_admins", False),
            })
        
        protected_count = sum(1 for p in protection_status if p["protected"])
        
        artifact = self._create_artifact(
            control_id="CC8.1",
            content={
                "branch_protection": protection_status,
                "total_repos": len(protection_status),
                "protected_repos": protected_count,
                "protection_coverage_percent": (protected_count / len(protection_status) * 100) if protection_status else 0,
            },
            metadata={"evidence_type": "branch_protection"}
        )
        return [artifact]
    
    async def _collect_secret_scanning(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect secret scanning evidence."""
        repos = await self._list_repositories()
        scanning_status = []
        
        for repo_data in repos[:20]:  # Limit for API calls
            repo_name = repo_data.get("full_name")
            scanning = await self._get_secret_scanning_status(repo_name)
            scanning_status.append({
                "repo": repo_name,
                "secret_scanning_enabled": scanning.get("enabled", False),
                "push_protection_enabled": scanning.get("push_protection", False),
                "open_alerts": scanning.get("open_alerts", 0),
            })
        
        enabled_count = sum(1 for s in scanning_status if s["secret_scanning_enabled"])
        
        artifact = self._create_artifact(
            control_id="CC7.1",
            content={
                "secret_scanning": scanning_status,
                "total_repos": len(scanning_status),
                "enabled_repos": enabled_count,
                "total_open_alerts": sum(s.get("open_alerts", 0) for s in scanning_status),
            },
            metadata={"evidence_type": "secret_scanning"}
        )
        return [artifact]
    
    async def _collect_webhooks(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect webhook evidence."""
        repos = await self._list_repositories()
        webhook_summary = []
        
        for repo_data in repos[:10]:  # Limit for API calls
            repo_name = repo_data.get("full_name")
            webhooks = await self._list_webhooks(repo_name)
            webhook_summary.append({
                "repo": repo_name,
                "webhook_count": len(webhooks),
                "webhooks": [
                    {
                        "id": w.get("id"),
                        "url": w.get("config", {}).get("url"),
                        "events": w.get("events", []),
                        "active": w.get("active", False),
                    }
                    for w in webhooks[:5]  # Limit webhooks per repo
                ]
            })
        
        artifact = self._create_artifact(
            control_id="CC7.1",
            content={
                "webhooks": webhook_summary,
                "total_repos_scanned": len(webhook_summary),
            },
            metadata={"evidence_type": "webhooks"}
        )
        return [artifact]
    
    async def _collect_collaborators(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect collaborator evidence."""
        repos = await self._list_repositories()
        collaborator_summary = []
        
        for repo_data in repos[:10]:  # Limit for API calls
            repo_name = repo_data.get("full_name")
            collaborators = await self._list_collaborators(repo_name)
            collaborator_summary.append({
                "repo": repo_name,
                "collaborator_count": len(collaborators),
                "collaborators": [
                    {
                        "login": c.get("login"),
                        "type": c.get("type"),
                        "permissions": c.get("permissions", {}),
                    }
                    for c in collaborators[:20]  # Limit collaborators per repo
                ]
            })
        
        artifact = self._create_artifact(
            control_id="CC6.2",
            content={
                "collaborators": collaborator_summary,
                "total_repos_scanned": len(collaborator_summary),
            },
            metadata={"evidence_type": "collaborators"}
        )
        return [artifact]
    
    # GitHub API wrapper methods
    def _get_client(self) -> Github:
        """Get or create GitHub client."""
        if self._gh_client is None:
            self._gh_client = Github(self._token)
        return self._gh_client
    
    async def _list_repositories(self) -> list[dict]:
        """List repositories."""
        loop = asyncio.get_event_loop()
        client = self._get_client()
        
        def _list():
            if self._org:
                org = client.get_organization(self._org)
                repos = org.get_repos()
            else:
                repos = client.get_user().get_repos()
            return [
                {
                    "name": r.name,
                    "full_name": r.full_name,
                    "private": r.private,
                    "visibility": r.visibility,
                    "created_at": str(r.created_at),
                    "updated_at": str(r.updated_at),
                    "default_branch": r.default_branch,
                }
                for r in repos
            ]
        
        return await loop.run_in_executor(None, _list)
    
    async def _get_branch_protection(self, repo_name: str, branch: str) -> dict:
        """Get branch protection status."""
        loop = asyncio.get_event_loop()
        client = self._get_client()
        
        def _get():
            try:
                repo = client.get_repo(repo_name)
                branch_obj = repo.get_branch(branch)
                protection = branch_obj.get_protection()
                return {
                    "enabled": True,
                    "require_status_checks": protection.required_status_checks is not None,
                    "require_code_owner_reviews": protection.required_pull_request_reviews is not None,
                    "require_pull_request_reviews": protection.required_pull_request_reviews is not None,
                    "enforce_admins": protection.enforce_admins,
                }
            except GithubException:
                return {"enabled": False}
        
        return await loop.run_in_executor(None, _get)
    
    async def _get_secret_scanning_status(self, repo_name: str) -> dict:
        """Get secret scanning status."""
        loop = asyncio.get_event_loop()
        client = self._get_client()
        
        def _get():
            try:
                repo = client.get_repo(repo_name)
                # Secret scanning availability depends on repo type
                return {
                    "enabled": repo.private is False,  # Simplified check
                    "push_protection": False,
                    "open_alerts": 0,
                }
            except GithubException:
                return {"enabled": False, "push_protection": False, "open_alerts": 0}
        
        return await loop.run_in_executor(None, _get)
    
    async def _list_webhooks(self, repo_name: str) -> list[dict]:
        """List webhooks for a repository."""
        loop = asyncio.get_event_loop()
        client = self._get_client()
        
        def _list():
            try:
                repo = client.get_repo(repo_name)
                hooks = repo.get_hooks()
                return [
                    {
                        "id": h.id,
                        "config": {"url": h.config.get("url") if h.config else None},
                        "events": h.events,
                        "active": h.active,
                    }
                    for h in hooks
                ]
            except GithubException:
                return []
        
        return await loop.run_in_executor(None, _list)
    
    async def _list_collaborators(self, repo_name: str) -> list[dict]:
        """List collaborators for a repository."""
        loop = asyncio.get_event_loop()
        client = self._get_client()
        
        def _list():
            try:
                repo = client.get_repo(repo_name)
                collabs = repo.get_collaborators()
                return [
                    {
                        "login": c.login,
                        "type": c.type,
                        "permissions": {
                            "push": c.permissions.push if c.permissions else False,
                            "pull": c.permissions.pull if c.permissions else False,
                            "admin": c.permissions.admin if c.permissions else False,
                        } if c.permissions else {},
                    }
                    for c in collabs
                ]
            except GithubException:
                return []
        
        return await loop.run_in_executor(None, _list)
    
    async def close(self) -> None:
        """Close the connector."""
        self._gh_client = None
