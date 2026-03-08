"""Integrations API router."""
from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_integrations():
    """List all integrations."""
    return {"integrations": []}


@router.post("/{source_type}/validate")
async def validate_source(source_type: str, credentials: dict):
    """Validate source credentials."""
    return {"validated": True}
