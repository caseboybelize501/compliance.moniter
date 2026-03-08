"""Report worker - Celery tasks for report generation."""
from server.celery_app import celery_app


@celery_app.task
def generate_report(tenant_id: str, framework_id: str, format: str = "pdf"):
    """Generate compliance report."""
    return {"report_id": "rpt_123", "status": "completed"}


@celery_app.task
def generate_scheduled_reports():
    """Generate scheduled reports."""
    pass
