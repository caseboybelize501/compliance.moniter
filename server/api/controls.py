"""Controls API router."""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

router = APIRouter()


@router.get("")
async def list_controls(
    framework: str = Query(..., description="Framework ID"),
    status: Optional[str] = Query(None, description="Filter by status")
):
    """List controls for a framework."""
    return {"controls": [], "framework": framework}


@router.get("/{control_id}")
async def get_control(control_id: str):
    """Get a specific control."""
    return {"control_id": control_id, "name": control_id}
