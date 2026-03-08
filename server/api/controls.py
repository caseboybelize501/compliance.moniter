"""
Controls API - Full implementation.

GET /api/controls - List controls with status
GET /api/controls/:id - Get specific control details
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
from datetime import datetime

from server.models.control import ControlResult
from engine.framework_registry import registry as framework_registry
from engine.control_engine import ControlEngine
from engine.evidence_store import EvidenceStore, StorageConfig


router = APIRouter()


def get_control_engine() -> ControlEngine:
    """Get control engine instance."""
    # In production, use dependency injection with proper config
    evidence_store = EvidenceStore(StorageConfig(
        s3_endpoint="http://minio:9000",
        s3_access_key="acmp_admin",
        s3_secret_key="acmp_secret_key"
    ))
    
    return ControlEngine(
        framework_registry=framework_registry,
        rules_engine=None,  # Would be injected
        evidence_store=evidence_store
    )


@router.get("")
async def list_controls(
    framework: str = Query(..., description="Framework ID (soc2, hipaa, gdpr, iso27001)"),
    status: Optional[str] = Query(None, description="Filter by status (PASS, FAIL, PARTIAL, NOT_EVALUATED)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    engine: ControlEngine = Depends(get_control_engine)
):
    """
    List controls for a framework with optional filtering.
    
    - **framework**: Framework ID (required)
    - **status**: Filter by evaluation status
    - **category**: Filter by control category
    """
    try:
        # Get framework
        fw = framework_registry.get_framework(framework)
        
        # Get controls
        controls = fw.controls
        
        # Filter by category
        if category:
            controls = [c for c in controls if c.get("category") == category]
        
        # In production, would get actual evaluation results
        # For now, return control definitions with placeholder status
        result = []
        for control in controls:
            control_data = {
                "id": control.get("id"),
                "name": control.get("name"),
                "description": control.get("description"),
                "category": control.get("category"),
                "severity": control.get("severity", "MEDIUM"),
                "status": "NOT_EVALUATED",  # Would come from evaluation
                "evidence_count": 0,
                "last_evaluated_at": None,
            }
            
            # Filter by status
            if status and control_data["status"] != status:
                continue
            
            result.append(control_data)
        
        return {
            "framework": framework,
            "framework_name": fw.name,
            "total_controls": len(result),
            "controls": result
        }
        
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Framework not found: {framework}")


@router.get("/{control_id}")
async def get_control(
    control_id: str,
    framework: Optional[str] = Query(None, description="Framework ID (optional, auto-detect if not provided)"),
    engine: ControlEngine = Depends(get_control_engine)
):
    """
    Get detailed information about a specific control.
    
    - **control_id**: Control ID (e.g., CC6.1)
    - **framework**: Optional framework ID
    """
    try:
        # Find control in framework
        if framework:
            control_def = framework_registry.get_control(framework, control_id)
        else:
            # Search across all frameworks
            control_def = None
            for fw_id in ["soc2", "hipaa", "gdpr", "iso27001"]:
                try:
                    control_def = framework_registry.get_control(fw_id, control_id)
                    framework = fw_id
                    break
                except:
                    continue
        
        if not control_def:
            raise HTTPException(status_code=404, detail=f"Control not found: {control_id}")
        
        # Get evaluation results (placeholder)
        return {
            "control": control_def,
            "framework": framework,
            "evaluation": {
                "status": "NOT_EVALUATED",
                "evidence_count": 0,
                "last_evaluated_at": None,
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{control_id}/evaluate")
async def evaluate_control(
    control_id: str,
    framework: str = Query(..., description="Framework ID"),
    tenant_id: str = Query(..., description="Tenant ID"),
    engine: ControlEngine = Depends(get_control_engine)
):
    """
    Trigger evaluation of a specific control.
    
    - **control_id**: Control ID to evaluate
    - **framework**: Framework ID
    - **tenant_id**: Tenant ID
    """
    try:
        # In production, would trigger async evaluation
        result = await engine.evaluate_control(
            control_id=control_id,
            tenant_id=tenant_id,
            framework_id=framework
        )
        
        return {
            "control_id": control_id,
            "result": result,
            "evaluated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
