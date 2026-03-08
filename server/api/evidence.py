"""Evidence API router."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/{artifact_id}")
async def get_evidence(artifact_id: str):
    """Get evidence artifact."""
    return {"artifact_id": artifact_id}


@router.get("/{artifact_id}/download")
async def download_evidence(artifact_id: str):
    """Download evidence artifact."""
    return {"download_url": f"/evidence/{artifact_id}"}
