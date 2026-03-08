"""
Tenant and Source Profile models for ACMP.
These are the interface contracts - immutable during repair.
"""
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class Tenant(BaseModel):
    """Represents a tenant (customer organization)."""
    id: str = Field(..., description="Unique tenant ID")
    name: str = Field(..., description="Tenant/organization name")
    subscription_tier: str = Field(default="starter", description="starter | growth | scale")
    active_frameworks: list[str] = Field(default_factory=list, description="Active framework IDs")
    source_profiles: list["SourceProfile"] = Field(default_factory=list, description="Connected sources")
    user_count: int = Field(default=0, description="Number of users")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    settings: dict[str, Any] = Field(default_factory=dict, description="Tenant-specific settings")
    is_active: bool = Field(default=True, description="Whether tenant is active")


class SourceProfile(BaseModel):
    """Represents a connected source system."""
    id: str = Field(..., description="Unique source ID")
    tenant_id: str = Field(..., description="Parent tenant ID")
    source_type: str = Field(..., description="aws | gcp | azure | github | okta | etc.")
    name: str = Field(..., description="Human-readable source name")
    scope: dict[str, Any] = Field(default_factory=dict, description="Source-specific scope (regions, orgs, etc.)")
    read_only: bool = Field(default=True, description="Confirmed read-only access")
    validated: bool = Field(default=False, description="Credentials validated")
    last_sync: datetime | None = Field(None, description="Last successful sync")
    sync_status: str = Field(default="pending", description="pending | syncing | success | error")
    last_error: str | None = Field(None, description="Last error message if any")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    rate_limit_config: dict[str, Any] = Field(default_factory=dict, description="Rate limiting settings")


class SourceValidationResult(BaseModel):
    """Result of source credential validation."""
    source_id: str
    validated: bool
    error_message: str | None
    read_only_confirmed: bool
    scope_discovered: dict[str, Any]
    validated_at: datetime = Field(default_factory=datetime.utcnow)


class TenantSummary(BaseModel):
    """Summary of tenant for dashboard."""
    id: str
    name: str
    subscription_tier: str
    source_count: int
    framework_count: int
    violation_count: int
    last_sync: datetime | None
    is_active: bool
