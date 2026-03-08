"""
Evidence and Source Profile Models

Evidence artifacts collected from sources and source configurations.
"""
from sqlalchemy import Column, String, Boolean, ForeignKey, Text, JSON, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from server.db.models.base import Base


class SourceProfile(Base):
    """
    Connected source system (AWS, GCP, Azure, GitHub, etc.).
    """
    
    __tablename__ = "source_profiles"
    
    id = Column(String(36), primary_key=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    source_type = Column(String(50), nullable=False)  # aws, gcp, azure, github, etc.
    name = Column(String(255), nullable=False)
    scope = Column(JSON, default=dict)  # Source-specific configuration
    read_only = Column(Boolean, default=True)
    validated = Column(Boolean, default=False)
    last_sync = Column(DateTime)
    sync_status = Column(String(20), default="pending")  # pending, syncing, success, error
    last_error = Column(Text)
    rate_limit_config = Column(JSON, default=dict)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="source_profiles")
    evidence_artifacts = relationship(
        "EvidenceArtifact",
        back_populates="source",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<SourceProfile(id={self.id}, type={self.source_type})>"


class EvidenceArtifact(Base):
    """
    Collected evidence artifact from a source.
    
    Stored with dedup key: (control_id + source_id + artifact_hash)
    """
    
    __tablename__ = "evidence_artifacts"
    
    id = Column(String(36), primary_key=True)
    control_id = Column(String(50), ForeignKey("controls.id", ondelete="CASCADE"), nullable=False)
    source_id = Column(String(36), ForeignKey("source_profiles.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    artifact_hash = Column(String(64), nullable=False, index=True)  # SHA256
    s3_key = Column(String(500))  # Minio/S3 storage key
    s3_bucket = Column(String(255), default="acmp-evidence")
    encryption_key_id = Column(String(36))  # Key used for encryption
    content_metadata = Column("metadata", JSON, default=dict)  # Non-sensitive metadata
    content_size = Column(Integer, default=0)  # Size in bytes
    collected_at = Column(DateTime, nullable=False, index=True)
    last_seen_at = Column(DateTime)  # For dedup tracking
    
    # Relationships
    source = relationship("SourceProfile", back_populates="evidence_artifacts")
    tenant = relationship("Tenant", back_populates="evidence_artifacts")
    
    # Unique constraint for dedup
    __table_args__ = (
        UniqueConstraint(
            'control_id', 'source_id', 'artifact_hash',
            name='uq_evidence_dedup'
        ),
        Index('idx_evidence_tenant_control', 'tenant_id', 'control_id'),
        Index('idx_evidence_collected', 'collected_at'),
    )
    
    def __repr__(self):
        return f"<EvidenceArtifact(id={self.id}, control={self.control_id})>"
