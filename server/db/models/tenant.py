"""
Tenant Model

Represents a customer organization (multi-tenant isolation).
"""
from sqlalchemy import Column, String, Boolean, Integer
from sqlalchemy.orm import relationship
from server.db.models.base import Base


class Tenant(Base):
    """
    Tenant represents a customer organization.
    
    All data is scoped to a tenant for isolation.
    """
    
    __tablename__ = "tenants"
    
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    subscription_tier = Column(
        String(50),
        nullable=False,
        default="starter"  # starter, growth, scale
    )
    user_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    settings = Column(String, default="{}")  # JSON settings
    
    # Relationships
    source_profiles = relationship(
        "SourceProfile",
        back_populates="tenant",
        cascade="all, delete-orphan"
    )
    violations = relationship(
        "Violation",
        back_populates="tenant",
        cascade="all, delete-orphan"
    )
    evidence_artifacts = relationship(
        "EvidenceArtifact",
        back_populates="tenant",
        cascade="all, delete-orphan"
    )
    control_results = relationship(
        "ControlResult",
        back_populates="tenant",
        cascade="all, delete-orphan"
    )
    audit_logs = relationship(
        "AuditLog",
        back_populates="tenant",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<Tenant(id={self.id}, name={self.name})>"
