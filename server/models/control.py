"""
Control and Evidence models for ACMP.
These are the interface contracts - immutable during repair.
"""
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class Control(BaseModel):
    """Represents a compliance control definition."""
    id: str = Field(..., description="Control ID (e.g., 'CC6.1')")
    name: str = Field(..., description="Human-readable name")
    framework_id: str = Field(..., description="Parent framework ID")
    description: str = Field(..., description="Control description")
    evidence_types: list[str] = Field(default_factory=list, description="Expected evidence artifact types")
    rule_type: str = Field(..., description="Rule type for evaluation")
    rule_config: dict[str, Any] = Field(default_factory=dict, description="Rule-specific configuration")
    category: str | None = Field(None, description="Control category (e.g., 'CC6' for SOC2)")
    severity: str = Field(default="MEDIUM", description="Default severity if control fails")


class EvidenceArtifact(BaseModel):
    """Represents collected evidence from a source."""
    id: str = Field(..., description="Unique artifact ID")
    control_id: str = Field(..., description="Associated control ID")
    source: str = Field(..., description="Source connector (aws, okta, etc.)")
    source_id: str | None = Field(None, description="Source profile ID")
    artifact_hash: str = Field(..., description="SHA256 of artifact content")
    content: dict[str, Any] = Field(..., description="Artifact data")
    collected_at: datetime = Field(default_factory=datetime.utcnow, description="Collection timestamp")
    tenant_id: str = Field(..., description="Tenant isolation")
    s3_key: str | None = Field(None, description="S3 storage key")
    encryption_key_id: str | None = Field(None, description="Key used for encryption")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ControlResult(BaseModel):
    """Result of evaluating a control against evidence."""
    id: str = Field(..., description="Unique result ID")
    control_id: str = Field(..., description="Evaluated control ID")
    tenant_id: str = Field(..., description="Tenant isolation")
    status: str = Field(..., description="PASS | FAIL | PARTIAL | NOT_EVALUATED")
    evidence_count: int = Field(default=0, description="Number of evidence artifacts evaluated")
    confidence: str = Field(default="MEDIUM", description="HIGH | MEDIUM | LOW")
    details: dict[str, Any] = Field(default_factory=dict, description="Evaluation details")
    evaluated_at: datetime = Field(default_factory=datetime.utcnow, description="Evaluation timestamp")
    failing_items: list[dict[str, Any]] = Field(default_factory=list, description="Items that failed evaluation")
    passing_items: list[dict[str, Any]] = Field(default_factory=list, description="Items that passed evaluation")
