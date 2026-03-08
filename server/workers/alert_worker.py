"""Alert worker - Celery tasks for alert dispatch."""
from server.celery_app import celery_app


@celery_app.task
def dispatch_alert(violation_id: str):
    """Dispatch alert for a violation."""
    return {"sent": True}
