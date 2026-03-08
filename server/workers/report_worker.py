"""Report worker - Full Celery tasks for report generation."""
from server.celery_app import celery_app
from engine.report_generator import ReportGenerator
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
_report_generator = ReportGenerator()


@celery_app.task(bind=True, max_retries=3)
def generate_report(
    self,
    tenant_id: str,
    framework_id: str,
    framework_name: str,
    period_start: str,
    period_end: str,
    format: str = "pdf"
):
    """
    Generate compliance report.
    
    Called via API when user requests report generation.
    """
    logger.info(f"Starting report generation: {framework_id} for {tenant_id}")
    
    try:
        # In production:
        # 1. Query control results for period
        # 2. Query violations for period
        # 3. Generate report in requested format
        
        # Placeholder data
        controls = [
            {"id": "CC6.1", "name": "MFA", "status": "PASS", "evidence_count": 5, "confidence": "HIGH"},
            {"id": "CC6.5", "name": "Encryption", "status": "FAIL", "evidence_count": 3, "confidence": "MEDIUM"},
        ]
        violations = [
            {"id": "v1", "control_id": "CC6.5", "severity": "HIGH", "description": "Unencrypted storage", "status": "OPEN", "age_days": 5}
        ]
        
        result = _report_generator.generate_report(
            tenant_id=tenant_id,
            framework_id=framework_id,
            framework_name=framework_name,
            controls=controls,
            violations=violations,
            period_start=datetime.fromisoformat(period_start),
            period_end=datetime.fromisoformat(period_end),
            format=format
        )
        
        logger.info(f"Report generation completed: {result.get('report_id')}")
        return result
        
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task
def generate_scheduled_reports():
    """
    Generate scheduled reports for tenants with auto-report enabled.
    
    Runs weekly via Celery Beat.
    """
    logger.info("Starting scheduled report generation")
    
    try:
        # In production:
        # 1. Get tenants with auto-report enabled
        # 2. For each tenant, generate report for their active frameworks
        # 3. Store/deliver reports
        
        logger.info("Scheduled report generation completed")
        return {"status": "completed", "reports_generated": 0}
        
    except Exception as e:
        logger.error(f"Scheduled report generation failed: {e}")
