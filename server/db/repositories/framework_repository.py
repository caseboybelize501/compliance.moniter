"""
Framework Repository

Data access for Framework and Control entities.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from server.db.models.framework import Framework, FrameworkVersion, Control, ControlResult
from server.db.repositories.base import BaseRepository


class FrameworkRepository(BaseRepository[Framework]):
    """Repository for Framework operations."""
    
    def __init__(self, db_session: AsyncSession):
        super().__init__(Framework, db_session)
    
    async def get_framework_with_controls(self, framework_id: str) -> Framework | None:
        """Get framework with all controls."""
        result = await self.db_session.execute(
            select(Framework)
            .where(Framework.id == framework_id)
        )
        framework = result.scalar_one_or_none()
        return framework
    
    async def get_control(self, framework_id: str, control_id: str) -> Control | None:
        """Get control by framework and control ID."""
        result = await self.db_session.execute(
            select(Control).where(
                Control.id == control_id,
                Control.framework_id == framework_id
            )
        )
        return result.scalar_one_or_none()
    
    async def get_controls_by_category(self, framework_id: str, category: str) -> list[Control]:
        """Get all controls in a category."""
        result = await self.db_session.execute(
            select(Control).where(
                Control.framework_id == framework_id,
                Control.category == category
            )
        )
        return list(result.scalars().all())
    
    async def create_framework_version(self, data: dict) -> FrameworkVersion:
        """Create a new framework version."""
        version = FrameworkVersion(**data)
        self.db_session.add(version)
        await self.db_session.flush()
        return version
    
    async def save_control_result(self, data: dict) -> ControlResult:
        """Save control evaluation result."""
        result = ControlResult(**data)
        self.db_session.add(result)
        await self.db_session.flush()
        return result
