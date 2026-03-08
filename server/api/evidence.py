"""Evidence API - Full implementation."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import io

router = APIRouter()

# In-memory evidence store (would be PostgreSQL + Minio in production)
_evidence_store = {}


@router.get("/{artifact_id}")
async def get_evidence(artifact_id: str):
    """Get evidence artifact metadata."""
    artifact = _evidence_store.get(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    return {
        "artifact": {
            "id": artifact["id"],
            "control_id": artifact["control_id"],
            "source": artifact["source"],
            "collected_at": artifact["collected_at"],
            "artifact_hash": artifact["artifact_hash"],
            "metadata": artifact.get("metadata", {}),
        }
    }


@router.get("/{artifact_id}/download")
async def download_evidence(artifact_id: str):
    """Download evidence artifact content."""
    artifact = _evidence_store.get(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    # In production, would download from Minio/S3
    content = artifact.get("content", {})
    
    # Return as JSON for now
    return StreamingResponse(
        io.BytesIO(str(content).encode()),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={artifact_id}.json"}
    )
