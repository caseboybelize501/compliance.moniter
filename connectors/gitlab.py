"""GitLab Connector for ACMP - collects repository evidence."""
import asyncio
from typing import Any

import gitlab

from connectors.base import BaseConnector, ConnectorError, ConnectorAuthenticationError, RateLimitConfig
from server.models.control import EvidenceArtifact
from server.models.tenant import SourceProfile


class GitLabConnector(BaseConnector):
    """GitLab connector for collecting repository evidence."""
    
    source_type = "gitlab"
    default_rate_limit = RateLimitConfig(requests_per_second=5.0, requests_per_hour=2000)
    
    def __init__(self, source_profile: SourceProfile, **kwargs: Any):
        super().__init__(source_profile, **kwargs)
        self._token = source_profile.scope.get("token")
        self._url = source_profile.scope.get("url", "https://gitlab.com")
        self._gl: gitlab.Gitlab | None = None
    
    @property
    def name(self) -> str:
        return "GitLab"
    
    async def validate_credentials(self) -> bool:
        """Validate GitLab token."""
        try:
            loop = asyncio.get_event_loop()
            
            def _validate():
                gl = gitlab.Gitlab(self._url, private_token=self._token)
                gl.auth()
                return True
            
            await loop.run_in_executor(None, _validate)
            return True
            
        except gitlab.exceptions.GitlabAuthenticationError as e:
            raise ConnectorAuthenticationError(f"GitLab authentication failed: {e}")
        except Exception as e:
            raise ConnectorError(f"GitLab validation error: {e}")
    
    async def collect_evidence(self, evidence_type: str, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect evidence for a specific evidence type."""
        evidence_collectors = {
            "projects": self._collect_projects,
            "branch_protection": self._collect_branch_protection,
            "ci_config": self._collect_ci_config,
        }
        
        collector = evidence_collectors.get(evidence_type)
        if not collector:
            raise ConnectorError(f"Unknown evidence type: {evidence_type}")
        
        return await collector(**kwargs)
    
    async def get_available_evidence_types(self) -> list[str]:
        """Get list of evidence types this connector can collect."""
        return ["projects", "branch_protection", "ci_config"]
    
    async def _collect_projects(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect GitLab projects evidence."""
        loop = asyncio.get_event_loop()
        
        def _list():
            gl = gitlab.Gitlab(self._url, private_token=self._token)
            projects = gl.projects.list(all=True)
            return [
                {
                    "id": p.id,
                    "name": p.name,
                    "path_with_namespace": p.path_with_namespace,
                    "visibility": p.visibility,
                    "default_branch": p.default_branch,
                    "created_at": p.created_at,
                }
                for p in projects
            ]
        
        projects = await loop.run_in_executor(None, _list)
        
        artifact = self._create_artifact(
            control_id="CC6.6",
            content={
                "projects": projects,
                "total_projects": len(projects),
            },
            metadata={"evidence_type": "projects"}
        )
        return [artifact]
    
    async def _collect_branch_protection(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect branch protection evidence."""
        loop = asyncio.get_event_loop()
        
        def _list():
            gl = gitlab.Gitlab(self._url, private_token=self._token)
            projects = gl.projects.list(all=True)
            
            protection_status = []
            for project in projects[:50]:  # Limit for API calls
                try:
                    protected = project.protectedbranches.list(all=True)
                    protection_status.append({
                        "project": project.path_with_namespace,
                        "protected_branches": [
                            {
                                "name": pb.name,
                                "merge_access_levels": pb.merge_access_levels,
                                "push_access_levels": pb.push_access_levels,
                            }
                            for pb in protected
                        ],
                    })
                except Exception:
                    continue
            
            return protection_status
        
        protection_status = await loop.run_in_executor(None, _list)
        
        protected_count = sum(1 for p in protection_status if p["protected_branches"])
        
        artifact = self._create_artifact(
            control_id="CC8.1",
            content={
                "branch_protection": protection_status,
                "total_projects": len(protection_status),
                "protected_projects": protected_count,
            },
            metadata={"evidence_type": "branch_protection"}
        )
        return [artifact]
    
    async def _collect_ci_config(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect CI/CD configuration evidence."""
        loop = asyncio.get_event_loop()
        
        def _list():
            gl = gitlab.Gitlab(self._url, private_token=self._token)
            projects = gl.projects.list(all=True)
            
            ci_status = []
            for project in projects[:50]:
                try:
                    # Check if .gitlab-ci.yml exists
                    ci_file = project.files.get(file_path='.gitlab-ci.yml', ref='HEAD')
                    ci_status.append({
                        "project": project.path_with_namespace,
                        "has_ci_config": True,
                    })
                except Exception:
                    ci_status.append({
                        "project": project.path_with_namespace,
                        "has_ci_config": False,
                    })
            
            return ci_status
        
        ci_status = await loop.run_in_executor(None, _list)
        
        artifact = self._create_artifact(
            control_id="CC8.2",
            content={
                "ci_config": ci_status,
                "total_projects": len(ci_status),
                "projects_with_ci": sum(1 for p in ci_status if p["has_ci_config"]),
            },
            metadata={"evidence_type": "ci_config"}
        )
        return [artifact]
