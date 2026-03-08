"""Reports API router."""
from fastapi import APIRouter

router = APIRouter()


@router.post("")
async def generate_report(report_data: dict):
    """Generate audit report."""
    return {"report_id": "rpt_123", "status": "generating"}


@router.get("/{report_id}/download")
async def download_report(report_id: str):
    """Download report."""
    return {"download_url": f"/reports/{report_id}"}
