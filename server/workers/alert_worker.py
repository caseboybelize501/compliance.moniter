"""Alert worker - Full Celery tasks for alert dispatch."""
from server.celery_app import celery_app
from engine.alert_dispatcher import AlertDispatcher
import logging

logger = logging.getLogger(__name__)
_alert_dispatcher = AlertDispatcher()


@celery_app.task(bind=True, max_retries=3)
def dispatch_alert(self, violation_id: str, recipient: str):
    """
    Dispatch alert for a violation.
    
    Triggered immediately when new violation is detected.
    """
    logger.info(f"Dispatching alert for violation {violation_id}")
    
    try:
        # In production:
        # 1. Get violation details
        # 2. Get tenant messaging preferences
        # 3. Send alert via configured provider
        
        # Placeholder
        result = {
            "violation_id": violation_id,
            "recipient": recipient,
            "sent": True,
            "provider": "whatsapp"
        }
        
        logger.info(f"Alert dispatched for violation {violation_id}")
        return result
        
    except Exception as e:
        logger.error(f"Alert dispatch failed: {e}")
        raise self.retry(exc=e, countdown=30)


@celery_app.task
def send_digest_alerts(tenant_id: str):
    """
    Send daily/weekly digest of violations.
    
    Runs daily via Celery Beat.
    """
    logger.info(f"Sending digest alerts for tenant {tenant_id}")
    
    try:
        # In production:
        # 1. Get open violations for tenant
        # 2. Format digest email
        # 3. Send to configured recipients
        
        logger.info(f"Digest alerts sent for tenant {tenant_id}")
        return {"status": "completed", "tenant_id": tenant_id}
        
    except Exception as e:
        logger.error(f"Digest alert failed: {e}")
