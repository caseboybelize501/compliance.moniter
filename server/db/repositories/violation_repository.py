"""
Violation Repository

Data access for Violation entities.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from server.db.models.violation import Violation
from server.db.repositories.base import BaseRepository


class ViolationRepository(BaseRepository[Violation]):
    """Repository for Violation operations."""
    
    def __init__(self, db_session: AsyncSession):
        super().__init__(Violation, db_session)
    
    async def list_open_by_tenant(self, tenant_id: str, limit: int = 100) -> list[Violation]:
        """List open violations for a tenant."""
        return await self.list_by(
            limit=limit,
            tenant_id=tenant_id,
            status="OPEN"
        )
    
    async def list_by_severity(self, tenant_id: str, severity: str) -> list[Violation]:
        """List violations by severity."""
        return await self.list_by(
            tenant_id=tenant_id,
            severity=severity,
            status="OPEN"
        )
    
    async def list_by_control(self, control_id: str, status: str = None) -> list[Violation]:
        """List violations for a control."""
        if status:
            return await self.list_by(
                control_id=control_id,
                status=status
            )
        return await self.list_by(control_id=control_id)
    
    async def check_dedup_window(self, control_id: str, tenant_id: str, hours: int = 1) -> Violation | None:
        """Check if violation exists within dedup window."""
        window_start = datetime.utcnow() - timedelta(hours=hours)
        result = await self.db_session.execute(
            select(Violation).where(
                Violation.control_id == control_id,
                Violation.tenant_id == tenant_id,
                Violation.status == "OPEN",
                Violation.opened_at >= window_start
            )
        )
        return result.scalar_one_or_none()
    
    async def close_violation(self, violation_id: str, reason: str, evidence_note: str = None) -> Violation | None:
        """Close a violation."""
        violation = await self.update(violation_id, {
            "status": "CLOSED",
            "closed_at": datetime.utcnow(),
            "closure_reason": reason,
            "evidence_note": evidence_note
        })
        return violation
    
    async def get_violation_summary(self, tenant_id: str) -> dict:
        """Get violation summary for a tenant."""
        from sqlalchemy import func
        
        # Total by status
        status_query = await self.db_session.execute(
            select(Violation.status, func.count())
            .where(Violation.tenant_id == tenant_id)
            .group_by(Violation.status)
        )
        by_status = {row[0]: row[1] for row in status_query.all()}
        
        # Total by severity
        severity_query = await self.db_session.execute(
            select(Violation.severity, func.count())
            .where(
                Violation.tenant_id == tenant_id,
                Violation.status == "OPEN"
            )
            .group_by(Violation.severity)
        )
        by_severity = {row[0]: row[1] for row in severity_query.all()}
        
        # Oldest critical violation
        oldest_critical = await self.db_session.execute(
            select(Violation.opened_at)
            .where(
                Violation.tenant_id == tenant_id,
                Violation.severity == "CRITICAL",
                Violation.status == "OPEN"
            )
            .order_by(Violation.opened_at)
            .limit(1)
        )
        oldest = oldest_critical.scalar_one_or_none()
        critical_age_days = 0
        if oldest:
            critical_age_days = (datetime.utcnow() - oldest).days
        
        return {
            "total": sum(by_status.values()),
            "open": by_status.get("OPEN", 0),
            "in_progress": by_status.get("IN_PROGRESS", 0),
            "closed": by_status.get("CLOSED", 0),
            "by_severity": by_severity,
            "critical_age_days": critical_age_days
        }
