"""Collection worker - Celery tasks for evidence collection."""
from server.celery_app import celery_app


@celery_app.task
def collect_evidence_delta(tenant_id: str):
    """Collect delta evidence for all sources."""
    pass


@celery_app.task
def scan_iam_permissions(tenant_id: str):
    """Scan IAM permissions."""
    pass


@celery_app.task
def scan_encryption_config(tenant_id: str):
    """Scan encryption configuration."""
    pass


@celery_app.task
def scan_mfa_compliance(tenant_id: str):
    """Scan MFA compliance."""
    pass
