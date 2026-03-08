"""Violations API router."""
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter()


@router.get("")
async def list_violations(
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None, default="open")
):
    """List violations."""
    return {"violations": []}


@router.get("/{violation_id}")
async def get_violation(violation_id: str):
    """Get a specific violation."""
    return {"violation_id": violation_id}
