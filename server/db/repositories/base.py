"""
Base Repository

Generic repository pattern implementation.
"""
from typing import Generic, TypeVar, Type, Optional, List, Dict, Any
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from server.db.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Generic repository with CRUD operations.
    
    Usage:
        class TenantRepository(BaseRepository[Tenant]):
            pass
        
        repo = TenantRepository(Tenant, db_session)
    """
    
    def __init__(self, model: Type[ModelType], db_session: AsyncSession):
        self.model = model
        self.db_session = db_session
    
    async def get(self, id: str) -> Optional[ModelType]:
        """Get by ID."""
        result = await self.db_session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_by(self, **kwargs) -> Optional[ModelType]:
        """Get by field values."""
        filters = [getattr(self.model, k) == v for k, v in kwargs.items()]
        result = await self.db_session.execute(
            select(self.model).where(*filters)
        )
        return result.scalar_one_or_none()
    
    async def list(self, limit: int = 100, offset: int = 0) -> List[ModelType]:
        """List all with pagination."""
        result = await self.db_session.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return list(result.scalars().all())
    
    async def list_by(self, limit: int = 100, offset: int = 0, **kwargs) -> List[ModelType]:
        """List by field values with pagination."""
        filters = [getattr(self.model, k) == v for k, v in kwargs.items()]
        result = await self.db_session.execute(
            select(self.model).where(*filters).limit(limit).offset(offset)
        )
        return list(result.scalars().all())
    
    async def count(self, **kwargs) -> int:
        """Count records."""
        from sqlalchemy import func
        if kwargs:
            filters = [getattr(self.model, k) == v for k, v in kwargs.items()]
            result = await self.db_session.execute(
                select(func.count()).select_from(self.model).where(*filters)
            )
        else:
            result = await self.db_session.execute(
                select(func.count()).select_from(self.model)
            )
        return result.scalar()
    
    async def create(self, obj: ModelType) -> ModelType:
        """Create new record."""
        self.db_session.add(obj)
        await self.db_session.flush()
        await self.db_session.refresh(obj)
        return obj
    
    async def create_from_dict(self, data: Dict[str, Any]) -> ModelType:
        """Create from dictionary."""
        obj = self.model(**data)
        return await self.create(obj)
    
    async def update(self, id: str, data: Dict[str, Any]) -> Optional[ModelType]:
        """Update by ID."""
        await self.db_session.execute(
            update(self.model)
            .where(self.model.id == id)
            .values(**data)
        )
        return await self.get(id)
    
    async def delete(self, id: str) -> bool:
        """Delete by ID."""
        result = await self.db_session.execute(
            delete(self.model).where(self.model.id == id)
        )
        return result.rowcount > 0
    
    async def exists(self, id: str) -> bool:
        """Check if record exists."""
        result = await self.db_session.execute(
            select(self.model.id).where(self.model.id == id)
        )
        return result.scalar_one_or_none() is not None
