"""Evaluation worker - Celery tasks for control evaluation."""
from server.celery_app import celery_app


@celery_app.task
def evaluate_all_controls(tenant_id: str, framework_id: str):
    """Evaluate all controls for a tenant."""
    pass


@celery_app.task
def re_evaluate_control(tenant_id: str, control_id: str):
    """Re-evaluate a specific control."""
    pass
