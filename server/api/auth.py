"""Auth API router."""
from fastapi import APIRouter

router = APIRouter()


@router.post("/login")
async def login(credentials: dict):
    """Login and get JWT token."""
    return {"access_token": "token", "token_type": "bearer"}


@router.post("/api-key")
async def create_api_key():
    """Create API key."""
    return {"api_key": "key_123"}
