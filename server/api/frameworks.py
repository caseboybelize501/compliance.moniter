"""Frameworks API router."""
from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_frameworks():
    """List all frameworks."""
    return {"frameworks": ["soc2", "hipaa", "gdpr", "iso27001"]}


@router.post("")
async def create_framework(framework: dict):
    """Create custom framework."""
    return {"status": "created"}
