"""
Framework and Control Models

Compliance framework definitions and control specifications.
"""
from sqlalchemy import Column, String, Boolean, ForeignKey, Text, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from server.db.models.base import Base


class Framework(Base):
    """
    Compliance framework (SOC2, HIPAA, GDPR, ISO27001).
    """
    
    __tablename__ = "frameworks"
    
    id = Column(String(50), primary_key=True)
    name = Column(String(255), nullable=False)
    version = Column(String(20), nullable=False)
    description = Column(Text)
    metadata_ = Column("metadata", JSON, default=dict)
    is_custom = Column(Boolean, default=False)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    
    # Relationships
    controls = relationship(
        "Control",
        back_populates="framework",
        cascade="all, delete-orphan"
    )
    framework_versions = relationship(
        "FrameworkVersion",
        back_populates="framework",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<Framework(id={self.id}, version={self.version})>"


class FrameworkVersion(Base):
    """
    Framework version history for auditing.
    """
    
    __tablename__ = "framework_versions"
    
    id = Column(String(50), primary_key=True)
    framework_id = Column(String(50), ForeignKey("frameworks.id", ondelete="CASCADE"), nullable=False)
    version = Column(String(20), nullable=False)
    change_summary = Column(Text)
    previous_version = Column(String(20))
    created_by = Column(String(36))  # User ID who made the change
    
    # Relationships
    framework = relationship("Framework", back_populates="framework_versions")
    
    def __repr__(self):
        return f"<FrameworkVersion(framework={self.framework_id}, version={self.version})>"


class Control(Base):
    """
    Individual control within a framework.
    """
    
    __tablename__ = "controls"
    
    id = Column(String(50), primary_key=True)
    framework_id = Column(String(50), ForeignKey("frameworks.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(50))  # e.g., "CC6" for SOC2
    evidence_types = Column(JSON, default=list)
    rule_type = Column(String(50))  # existence, percentage, boolean, threshold
    rule_config = Column(JSON, default=dict)
    severity = Column(String(20), default="MEDIUM")  # LOW, MEDIUM, HIGH, CRITICAL
    
    # Relationships
    framework = relationship("Framework", back_populates="controls")
    control_results = relationship(
        "ControlResult",
        back_populates="control",
        cascade="all, delete-orphan"
    )
    violations = relationship(
        "Violation",
        back_populates="control",
        cascade="all, delete-orphan"
    )
    
    # Unique constraint
    __table_args__ = (
        UniqueConstraint('framework_id', 'id', name='uq_framework_control'),
    )
    
    def __repr__(self):
        return f"<Control(id={self.id}, framework={self.framework_id})>"


class ControlResult(Base):
    """
    Result of evaluating a control against evidence.
    """
    
    __tablename__ = "control_results"
    
    id = Column(String(36), primary_key=True)
    control_id = Column(String(50), ForeignKey("controls.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False)  # PASS, FAIL, PARTIAL, NOT_EVALUATED
    evidence_count = Column(Integer, default=0)
    confidence = Column(String(20), default="MEDIUM")  # HIGH, MEDIUM, LOW
    details = Column(JSON, default=dict)
    evaluated_at = Column(String(32), nullable=False)
    failing_items = Column(JSON, default=list)
    passing_items = Column(JSON, default=list)
    
    # Relationships
    control = relationship("Control", back_populates="control_results")
    tenant = relationship("Tenant", back_populates="control_results")
    
    def __repr__(self):
        return f"<ControlResult(control={self.control_id}, status={self.status})>"
