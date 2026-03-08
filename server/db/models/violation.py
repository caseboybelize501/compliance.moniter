"""
Violation Model

Compliance violations detected from control failures.
"""
from sqlalchemy import Column, String, ForeignKey, Text, JSON, DateTime, Integer, Index
from sqlalchemy.orm import relationship
from server.db.models.base import Base


class Violation(Base):
    """
    Compliance violation detected from control evaluation.
    """
    
    __tablename__ = "violations"
    
    id = Column(String(36), primary_key=True)
    control_id = Column(String(50), ForeignKey("controls.id", ondelete="CASCADE"), nullable=False)
    control_result_id = Column(String(36), ForeignKey("control_results.id", ondelete="SET NULL"), nullable=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    severity = Column(String(20), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    description = Column(Text)
    status = Column(String(20), default="OPEN", index=True)  # OPEN, IN_PROGRESS, CLOSED
    remediation_suggestion = Column(Text)
    opened_at = Column(DateTime, nullable=False, index=True)
    closed_at = Column(DateTime)
    closure_reason = Column(Text)
    age_days = Column(Integer, default=0)
    related_violation_ids = Column(JSON, default=list)  # For escalation tracking
    evidence_note = Column(Text)  # User-provided remediation evidence
    artifact_url = Column(String(500))  # URL to remediation artifact
    
    # Relationships
    control = relationship("Control", back_populates="violations")
    tenant = relationship("Tenant", back_populates="violations")
    
    # Indexes
    __table_args__ = (
        Index('idx_violations_tenant_status', 'tenant_id', 'status'),
        Index('idx_violations_severity', 'severity'),
        Index('idx_violations_control', 'control_id'),
    )
    
    def __repr__(self):
        return f"<Violation(id={self.id}, control={self.control_id}, severity={self.severity})>"
