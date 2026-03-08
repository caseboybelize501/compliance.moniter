"""Jira Connector for ACMP - collects ticketing evidence."""
import asyncio
from typing import Any

from jira import JIRA
from jira.exceptions import JIRAError

from connectors.base import BaseConnector, ConnectorError, ConnectorAuthenticationError, RateLimitConfig
from server.models.control import EvidenceArtifact
from server.models.tenant import SourceProfile


class JiraConnector(BaseConnector):
    """Jira connector for collecting ticketing evidence."""
    
    source_type = "jira"
    default_rate_limit = RateLimitConfig(requests_per_second=5.0, requests_per_10s=50)
    
    def __init__(self, source_profile: SourceProfile, **kwargs: Any):
        super().__init__(source_profile, **kwargs)
        self._server = source_profile.scope.get("server")
        self._token = source_profile.scope.get("token")
        self._email = source_profile.scope.get("email")
        self._jira: JIRA | None = None
    
    @property
    def name(self) -> str:
        return f"Jira ({self._server})"
    
    async def validate_credentials(self) -> bool:
        """Validate Jira credentials."""
        try:
            loop = asyncio.get_event_loop()
            
            def _validate():
                jira = JIRA(
                    server=self._server,
                    basic_auth=(self._email, self._token)
                )
                # Test connection
                jira.myself()
                return True
            
            await loop.run_in_executor(None, _validate)
            return True
            
        except JIRAError as e:
            if e.status_code == 401:
                raise ConnectorAuthenticationError(f"Jira authentication failed: {e}")
            raise ConnectorError(f"Jira validation error: {e}")
        except Exception as e:
            raise ConnectorError(f"Jira validation error: {e}")
    
    async def collect_evidence(self, evidence_type: str, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect evidence for a specific evidence type."""
        evidence_collectors = {
            "issues": self._collect_issues,
            "change_tickets": self._collect_change_tickets,
            "incident_records": self._collect_incident_records,
        }
        
        collector = evidence_collectors.get(evidence_type)
        if not collector:
            raise ConnectorError(f"Unknown evidence type: {evidence_type}")
        
        return await collector(**kwargs)
    
    async def get_available_evidence_types(self) -> list[str]:
        """Get list of evidence types this connector can collect."""
        return ["issues", "change_tickets", "incident_records"]
    
    async def _collect_issues(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect Jira issues evidence."""
        loop = asyncio.get_event_loop()
        
        def _list():
            jira = JIRA(server=self._server, basic_auth=(self._email, self._token))
            # Search for issues from last 90 days
            issues = jira.search_issues(
                jql_str="created >= -90d ORDER BY created DESC",
                maxResults=100
            )
            return [
                {
                    "key": i.key,
                    "summary": i.fields.summary,
                    "status": i.fields.status.name if i.fields.status else None,
                    "type": i.fields.issuetype.name if i.fields.issuetype else None,
                    "created": str(i.fields.created),
                    "updated": str(i.fields.updated),
                }
                for i in issues
            ]
        
        issues = await loop.run_in_executor(None, _list)
        
        artifact = self._create_artifact(
            control_id="CC8.1",
            content={
                "issues": issues,
                "total_issues": len(issues),
            },
            metadata={"evidence_type": "issues"}
        )
        return [artifact]
    
    async def _collect_change_tickets(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect change tickets evidence."""
        loop = asyncio.get_event_loop()
        
        def _list():
            jira = JIRA(server=self._server, basic_auth=(self._email, self._token))
            # Search for change tickets (assumes 'Change' type or 'CHG' prefix)
            issues = jira.search_issues(
                jql_str="issuetype = 'Change' OR key ~ 'CHG%' ORDER BY created DESC",
                maxResults=100
            )
            return [
                {
                    "key": i.key,
                    "summary": i.fields.summary,
                    "status": i.fields.status.name if i.fields.status else None,
                    "created": str(i.fields.created),
                    "resolution": i.fields.resolution.name if i.fields.resolution else None,
                }
                for i in issues
            ]
        
        tickets = await loop.run_in_executor(None, _list)
        
        artifact = self._create_artifact(
            control_id="CC8.1",
            content={
                "change_tickets": tickets,
                "total_changes": len(tickets),
            },
            metadata={"evidence_type": "change_tickets"}
        )
        return [artifact]
    
    async def _collect_incident_records(self, **kwargs: Any) -> list[EvidenceArtifact]:
        """Collect incident records evidence."""
        loop = asyncio.get_event_loop()
        
        def _list():
            jira = JIRA(server=self._server, basic_auth=(self._email, self._token))
            # Search for incidents (assumes 'Incident' type or 'INC' prefix)
            issues = jira.search_issues(
                jql_str="issuetype = 'Incident' OR key ~ 'INC%' ORDER BY created DESC",
                maxResults=100
            )
            return [
                {
                    "key": i.key,
                    "summary": i.fields.summary,
                    "status": i.fields.status.name if i.fields.status else None,
                    "priority": i.fields.priority.name if i.fields.priority else None,
                    "created": str(i.fields.created),
                    "resolved": str(i.fields.resolutiondate) if i.fields.resolutiondate else None,
                }
                for i in issues
            ]
        
        incidents = await loop.run_in_executor(None, _list)
        
        artifact = self._create_artifact(
            control_id="CC7.2",
            content={
                "incidents": incidents,
                "total_incidents": len(incidents),
            },
            metadata={"evidence_type": "incident_records"}
        )
        return [artifact]
