"""
Violation models for ACMP.
These are the interface contracts - immutable during repair.
"""
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class Violation(BaseModel):
    """Represents a compliance violation."""
    id: str = Field(..., description="Unique violation ID")
    control_id: str = Field(..., description="Failed control ID")
    control_result_id: str = Field(..., description="Reference to ControlResult")
    tenant_id: str = Field(..., description="Tenant isolation")
    severity: str = Field(..., description="LOW | MEDIUM | HIGH | CRITICAL")
    description: str = Field(..., description="Violation description")
    status: str = Field(default="OPEN", description="OPEN | IN_PROGRESS | CLOSED")
    remediation_suggestion: str | None = Field(None, description="LLM-generated fix suggestion")
    opened_at: datetime = Field(default_factory=datetime.utcnow, description="When violation was detected")
    closed_at: datetime | None = Field(None, description="When resolved")
    closure_reason: str | None = Field(None, description="Why closed")
    age_days: int = Field(default=0, description="Days since opened")
    related_violation_ids: list[str] = Field(default_factory=list, description="Related violations for escalation")
    evidence_note: str | None = Field(None, description="User-provided remediation evidence")
    artifact_url: str | None = Field(None, description="URL to remediation artifact")


class ViolationSummary(BaseModel):
    """Summary of violations for dashboard."""
    total: int = Field(default=0)
    open: int = Field(default=0)
    in_progress: int = Field(default=0)
    closed: int = Field(default=0)
    by_severity: dict[str, int] = Field(default_factory=dict)
    critical_age_days: int = Field(default=0, description="Age of oldest critical violation")


class RemediationStatus(BaseModel):
    """Status of remediation effort."""
    violation_id: str
    status: str
    suggestion_provided: bool
    user_acknowledged: bool
    completion_target: datetime | None
    actual_completion: datetime | None
