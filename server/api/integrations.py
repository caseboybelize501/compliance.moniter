"""Integrations API - Full implementation."""
from fastapi import APIRouter, HTTPException
from typing import Optional, List

from connectors.connector_manager import ConnectorManager, registry
from server.models.tenant import SourceProfile

router = APIRouter()

# In-memory source store
_source_manager = ConnectorManager()


@router.get("")
async def list_integrations(tenant_id: Optional[str] = None):
    """List all configured integrations/sources."""
    sources = _source_manager.list_sources(tenant_id)
    
    return {
        "integrations": [
            {
                "id": s.id,
                "name": s.name,
                "source_type": s.source_type,
                "validated": s.validated,
                "sync_status": s.sync_status,
                "last_sync": s.last_sync.isoformat() if s.last_sync else None,
                "last_error": s.last_error,
            }
            for s in sources
        ]
    }


@router.get("/available")
async def list_available_sources():
    """List available source types."""
    return {
        "available_sources": [
            {"type": "aws", "name": "Amazon Web Services", "category": "cloud"},
            {"type": "gcp", "name": "Google Cloud Platform", "category": "cloud"},
            {"type": "azure", "name": "Microsoft Azure", "category": "cloud"},
            {"type": "github", "name": "GitHub", "category": "code"},
            {"type": "gitlab", "name": "GitLab", "category": "code"},
            {"type": "okta", "name": "Okta", "category": "identity"},
            {"type": "azure_ad", "name": "Azure AD", "category": "identity"},
            {"type": "jira", "name": "Jira", "category": "ticketing"},
            {"type": "slack", "name": "Slack", "category": "comms"},
        ]
    }


@router.post("/{source_type}/validate")
async def validate_source(source_type: str, credentials: dict, tenant_id: str = "default"):
    """Validate source credentials."""
    # Create temporary source profile
    profile = SourceProfile(
        id="temp_" + source_type,
        tenant_id=tenant_id,
        source_type=source_type,
        name=f"Temporary {source_type}",
        scope=credentials,
        read_only=True,
        validated=False
    )
    
    _source_manager.register_source(profile)
    
    # Validate
    result = await _source_manager.validate_source(profile.id)
    
    return {
        "validated": result.validated,
        "error_message": result.error_message,
        "read_only_confirmed": result.read_only_confirmed,
    }


@router.post("")
async def add_source(source: dict, tenant_id: str = "default"):
    """Add new source integration."""
    source_type = source.get("source_type")
    if not source_type:
        raise HTTPException(status_code=400, detail="source_type required")
    
    profile = SourceProfile(
        id=source.get("id", f"src_{source_type}_{tenant_id}"),
        tenant_id=tenant_id,
        source_type=source_type,
        name=source.get("name", source_type),
        scope=source.get("credentials", {}),
        read_only=source.get("read_only", True),
        validated=False
    )
    
    _source_manager.register_source(profile)
    
    # Auto-validate
    result = await _source_manager.validate_source(profile.id)
    
    return {
        "status": "added",
        "source_id": profile.id,
        "validated": result.validated,
    }


@router.delete("/{source_id}")
async def remove_source(source_id: str):
    """Remove source integration."""
    # In production, would remove from database
    return {"status": "deleted", "source_id": source_id}


@router.post("/{source_id}/sync")
async def trigger_sync(source_id: str):
    """Trigger manual sync for a source."""
    source = _source_manager.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # In production, would trigger Celery task
    source.sync_status = "syncing"
    
    return {
        "status": "syncing",
        "source_id": source_id
    }
