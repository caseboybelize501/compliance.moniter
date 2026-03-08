"""
Framework models for ACMP.
These are the interface contracts - immutable during repair.
"""
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class Framework(BaseModel):
    """Represents a compliance framework."""
    id: str = Field(..., description="Framework ID (soc2, hipaa, etc.)")
    name: str = Field(..., description="Human-readable name")
    version: str = Field(..., description="Version string (semver)")
    description: str | None = Field(None, description="Framework description")
    controls: list[Any] = Field(default_factory=list, description="Control definitions (dict form)")
    is_custom: bool = Field(default=False, description="True if tenant-defined")
    tenant_id: str | None = Field(None, description="Owning tenant (None for seed frameworks)")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional framework metadata")


class FrameworkVersion(BaseModel):
    """Tracks framework version history."""
    id: str = Field(..., description="Unique version ID")
    framework_id: str = Field(..., description="Parent framework ID")
    version: str = Field(..., description="Version string")
    change_summary: str = Field(..., description="What changed in this version")
    previous_version: str | None = Field(None, description="Previous version string")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str | None = Field(None, description="User who made the change")
    snapshot_data: dict[str, Any] = Field(default_factory=dict, description="Full framework snapshot")


class FrameworkSummary(BaseModel):
    """Summary of framework for dashboard."""
    id: str
    name: str
    version: str
    total_controls: int
    active: bool
    is_custom: bool
    last_updated: datetime
