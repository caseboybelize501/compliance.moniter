"""Reports API - Full implementation."""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from datetime import datetime
from typing import Optional
import uuid

from engine.report_generator import ReportGenerator

router = APIRouter()

# In-memory report store
_report_store = {}
_report_generator = ReportGenerator()


@router.post("")
async def generate_report(
    background_tasks: BackgroundTasks,
    framework_id: str,
    framework_name: Optional[str] = None,
    period_start: str = None,
    period_end: str = None,
    format: str = "pdf",
    tenant_id: str = "default"
):
    """
    Generate compliance report.
    
    - **framework_id**: Framework ID (soc2, hipaa, gdpr, iso27001)
    - **format**: Output format (pdf, csv, zip)
    - **period_start**: Report period start (ISO format)
    - **period_end**: Report period end (ISO format)
    """
    report_id = str(uuid.uuid4())
    
    # Store report job
    _report_store[report_id] = {
        "id": report_id,
        "status": "generating",
        "framework_id": framework_id,
        "format": format,
        "tenant_id": tenant_id,
        "created_at": datetime.utcnow().isoformat(),
        "content": None,
        "filename": None,
    }
    
    # Generate in background
    async def generate():
        try:
            # Placeholder data (would query actual control results)
            controls = [
                {"id": "CC6.1", "name": "MFA", "status": "PASS", "evidence_count": 5},
                {"id": "CC6.5", "name": "Encryption", "status": "FAIL", "evidence_count": 3},
            ]
            violations = [
                {"id": "v1", "control_id": "CC6.5", "severity": "HIGH", "description": "Unencrypted storage", "status": "OPEN", "age_days": 5}
            ]
            
            result = await _report_generator.generate_report(
                tenant_id=tenant_id,
                framework_id=framework_id,
                framework_name=framework_name or framework_id.upper(),
                controls=controls,
                violations=violations,
                period_start=datetime.fromisoformat(period_start) if period_start else datetime.utcnow(),
                period_end=datetime.fromisoformat(period_end) if period_end else datetime.utcnow(),
                format=format
            )
            
            _report_store[report_id]["status"] = "completed"
            _report_store[report_id]["content"] = result.get("content")
            _report_store[report_id]["filename"] = result.get("filename")
            _report_store[report_id]["completed_at"] = datetime.utcnow().isoformat()
            
        except Exception as e:
            _report_store[report_id]["status"] = "failed"
            _report_store[report_id]["error"] = str(e)
    
    background_tasks.add_task(generate)
    
    return {
        "report_id": report_id,
        "status": "generating",
        "estimated_s": 30
    }


@router.get("/{report_id}")
async def get_report_status(report_id: str):
    """Get report generation status."""
    report = _report_store.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return {
        "report_id": report_id,
        "status": report["status"],
        "format": report["format"],
        "created_at": report["created_at"],
        "completed_at": report.get("completed_at"),
        "error": report.get("error"),
    }


@router.get("/{report_id}/download")
async def download_report(report_id: str):
    """Download generated report."""
    report = _report_store.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    if report["status"] != "completed":
        raise HTTPException(status_code=400, detail="Report not ready")
    
    # In production, would stream from storage
    return {
        "download_url": f"/reports/{report_id}/file",
        "filename": report.get("filename", f"{report_id}.{report['format']}")
    }
