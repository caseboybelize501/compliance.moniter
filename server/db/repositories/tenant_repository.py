"""
Tenant Repository

Data access for Tenant entities.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from server.db.models.tenant import Tenant
from server.db.repositories.base import BaseRepository


class TenantRepository(BaseRepository[Tenant]):
    """Repository for Tenant operations."""
    
    def __init__(self, db_session: AsyncSession):
        super().__init__(Tenant, db_session)
    
    async def get_by_name(self, name: str) -> Tenant | None:
        """Get tenant by name."""
        return await self.get_by(name=name)
    
    async def get_active_tenants(self) -> list[Tenant]:
        """Get all active tenants."""
        return await self.list_by(is_active=True)
    
    async def create_tenant(self, id: str, name: str, subscription_tier: str = "starter") -> Tenant:
        """Create a new tenant."""
        tenant = Tenant(
            id=id,
            name=name,
            subscription_tier=subscription_tier
        )
        return await self.create(tenant)
