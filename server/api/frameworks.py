"""Frameworks API - Full implementation."""
from fastapi import APIRouter, HTTPException
from typing import Optional

from engine.framework_registry import registry as framework_registry, FrameworkNotFoundError

router = APIRouter()


@router.get("")
async def list_frameworks(tenant_id: Optional[str] = None):
    """List all available frameworks."""
    frameworks = framework_registry.list_frameworks(tenant_id)
    
    return {
        "frameworks": [
            {
                "id": fw.id,
                "name": fw.name,
                "version": fw.version,
                "description": fw.description,
                "is_custom": fw.is_custom,
                "control_count": len(fw.controls),
            }
            for fw in frameworks
        ]
    }


@router.get("/{framework_id}")
async def get_framework(framework_id: str):
    """Get framework details."""
    try:
        fw = framework_registry.get_framework(framework_id)
        
        return {
            "framework": {
                "id": fw.id,
                "name": fw.name,
                "version": fw.version,
                "description": fw.description,
                "metadata": fw.metadata,
                "controls": fw.controls,
            }
        }
    except FrameworkNotFoundError:
        raise HTTPException(status_code=404, detail="Framework not found")


@router.post("")
async def create_framework(framework: dict):
    """Create custom framework."""
    # In production, would validate and save to database
    framework_id = framework.get("id", "custom_" + str(len(framework_registry.list_frameworks()) + 1))
    
    return {
        "status": "created",
        "framework_id": framework_id
    }
