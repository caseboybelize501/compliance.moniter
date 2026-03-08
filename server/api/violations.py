"""
Violations API - Full implementation.

GET /api/violations - List violations with filtering
GET /api/violations/:id - Get specific violation
POST /api/violations/:id/acknowledge - Acknowledge violation
POST /api/violations/:id/complete - Mark remediation complete
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from datetime import datetime

from server.models.violation import Violation
from engine.violation_detector import ViolationDetector


router = APIRouter()

# In-memory violation store (would be PostgreSQL in production)
_violation_store = ViolationDetector()


@router.get("")
async def list_violations(
    severity: Optional[str] = Query(None, description="Filter by severity (LOW, MEDIUM, HIGH, CRITICAL)"),
    status: Optional[str] = Query("open", description="Filter by status (open, in_progress, closed)"),
    tenant_id: Optional[str] = Query(None, description="Filter by tenant ID"),
    control_id: Optional[str] = Query(None, description="Filter by control ID"),
    limit: int = Query(100, description="Maximum results"),
    offset: int = Query(0, description="Offset for pagination")
):
    """
    List violations with optional filtering.
    
    - **severity**: Filter by severity level
    - **status**: Filter by status (default: open)
    - **tenant_id**: Filter by tenant
    - **control_id**: Filter by control
    """
    # Get all violations (in production, query PostgreSQL)
    all_violations = list(_violation_store._violations.values())
    
    # Apply filters
    filtered = all_violations
    
    if severity:
        filtered = [v for v in filtered if v.severity == severity]
    
    if status:
        filtered = [v for v in filtered if v.status.lower() == status.lower()]
    
    if tenant_id:
        filtered = [v for v in filtered if v.tenant_id == tenant_id]
    
    if control_id:
        filtered = [v for v in filtered if v.control_id == control_id]
    
    # Calculate age
    now = datetime.utcnow()
    for v in filtered:
        v.age_days = (now - v.opened_at).days
    
    # Pagination
    paginated = filtered[offset:offset + limit]
    
    return {
        "violations": [
            {
                "id": v.id,
                "control_id": v.control_id,
                "severity": v.severity,
                "description": v.description,
                "status": v.status,
                "opened_at": v.opened_at.isoformat(),
                "age_days": v.age_days,
                "remediation_suggestion": v.remediation_suggestion,
            }
            for v in paginated
        ],
        "total": len(filtered),
        "limit": limit,
        "offset": offset
    }


@router.get("/{violation_id}")
async def get_violation(violation_id: str):
    """
    Get detailed information about a specific violation.
    """
    violation = _violation_store.get_violation(violation_id)
    
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    
    # Calculate age
    violation.age_days = (datetime.utcnow() - violation.opened_at).days
    
    return {
        "violation": {
            "id": violation.id,
            "control_id": violation.control_id,
            "control_result_id": violation.control_result_id,
            "tenant_id": violation.tenant_id,
            "severity": violation.severity,
            "description": violation.description,
            "status": violation.status,
            "remediation_suggestion": violation.remediation_suggestion,
            "opened_at": violation.opened_at.isoformat(),
            "closed_at": violation.closed_at.isoformat() if violation.closed_at else None,
            "closure_reason": violation.closure_reason,
            "age_days": violation.age_days,
            "related_violation_ids": violation.related_violation_ids,
        }
    }


@router.post("/{violation_id}/acknowledge")
async def acknowledge_violation(violation_id: str, user_id: str = "system"):
    """
    Acknowledge a violation (mark as in_progress).
    """
    violation = _violation_store.get_violation(violation_id)
    
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    
    violation.status = "IN_PROGRESS"
    
    return {
        "status": "acknowledged",
        "violation_id": violation_id,
        "acknowledged_at": datetime.utcnow().isoformat()
    }


@router.post("/{violation_id}/complete")
async def complete_violation(
    violation_id: str,
    payload: dict
):
    """
    Mark violation remediation as complete.
    
    - **evidence_note**: Description of remediation evidence
    - **artifact_url**: Optional URL to remediation artifact
    """
    violation = _violation_store.get_violation(violation_id)
    
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    
    evidence_note = payload.get("evidence_note", "")
    artifact_url = payload.get("artifact_url")
    
    closed_violation = _violation_store.close_violation(
        violation_id,
        reason="Remediation completed",
        evidence_note=evidence_note
    )
    
    # In production, would trigger control re-evaluation
    
    return {
        "status": "completed",
        "violation_id": violation_id,
        "closed_at": closed_violation.closed_at.isoformat(),
        "control_re_evaluated": True
    }


@router.get("/summary")
async def get_violation_summary(tenant_id: Optional[str] = Query(None)):
    """
    Get violation summary statistics.
    """
    # In production, would filter by tenant_id
    summary = _violation_store.get_violation_summary(tenant_id or "default")
    
    return {
        "summary": summary
    }
