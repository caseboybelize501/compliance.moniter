"""
SQLAlchemy Base Model

Common mixins and base class for all models.
"""
from datetime import datetime
from sqlalchemy import Column, DateTime, String
from sqlalchemy.orm import declared_attr


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""
    
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )


class TenantMixin:
    """Mixin for multi-tenant isolation."""
    
    @declared_attr
    def tenant_id(cls):
        from sqlalchemy import Column, String, ForeignKey, Index
        return Column(
            String(36),
            ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True
        )


class Base(TimestampMixin):
    """
    Base class for all SQLAlchemy models.
    
    Provides:
    - Automatic primary key (id)
    - Timestamps (created_at, updated_at)
    - Table name generation
    """
    
    @declared_attr
    def __tablename__(cls):
        """Generate table name from class name."""
        # Convert CamelCase to snake_case
        name = cls.__name__
        return ''.join(['_' + i.lower() if i.isupper() else i for i in name]).lstrip('_') + 's'
    
    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    def __repr__(self):
        """String representation."""
        if hasattr(self, 'id'):
            return f"<{self.__class__.__name__}(id={self.id})>"
        return f"<{self.__class__.__name__}>"
