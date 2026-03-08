"""
Audit Log Model

Tamper-evident audit trail for compliance.
"""
from sqlalchemy import Column, String, ForeignKey, Text, JSON, DateTime, Index
from sqlalchemy.orm import relationship
from server.db.models.base import Base


class AuditLog(Base):
    """
    Audit log entry for compliance tracking.
    
    All sensitive actions are logged for audit trails.
    """
    
    __tablename__ = "audit_logs"
    
    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)  # login, evidence_collected, violation_created, etc.
    actor_id = Column(String(36))  # User or system that triggered the event
    actor_type = Column(String(20))  # user, system, api_key
    resource_type = Column(String(50))  # control, violation, evidence, etc.
    resource_id = Column(String(36))  # ID of affected resource
    action = Column(String(50), nullable=False)  # create, update, delete, read
    event_data = Column(JSON, default=dict)  # Event details
    ip_address = Column(String(45))  # IPv4 or IPv6
    user_agent = Column(String(500))
    created_at = Column(DateTime, nullable=False, index=True)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="audit_logs")
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_audit_tenant_created', 'tenant_id', 'created_at'),
        Index('idx_audit_event_type', 'event_type'),
        Index('idx_audit_actor', 'actor_id'),
    )
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, event={self.event_type}, action={self.action})>"
