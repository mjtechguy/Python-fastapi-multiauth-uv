"""Celery application configuration."""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "saas_backend",
    broker=str(settings.CELERY_BROKER_URL),
    backend=str(settings.CELERY_RESULT_BACKEND),
    include=["app.tasks.email", "app.tasks.pypi_check", "app.tasks.webhook"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    # Dead Letter Queue configuration
    task_reject_on_worker_lost=True,  # Send to DLQ if worker is lost
    task_acks_late=True,  # Acknowledge task after it completes
    task_reject_on_rate_limit=False,
    # Retry policy
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    # Error handling
    task_send_error_emails=False,  # Disable email errors (we'll use our own monitoring)
)

# Define dead letter exchange and queue
# Tasks that fail all retries will be sent here
celery_app.conf.task_routes = {
    "*": {
        "queue": "default",
        "routing_key": "default",
    },
}

# Configure default queue with DLX (Dead Letter Exchange)
celery_app.conf.task_queues = {
    "default": {
        "exchange": "default",
        "exchange_type": "direct",
        "routing_key": "default",
        "queue_arguments": {
            "x-dead-letter-exchange": "dlx",
            "x-dead-letter-routing-key": "dead_letter",
        },
    },
}


# Error handlers
@celery_app.task(bind=True, name="handle_task_failure")
def handle_task_failure(self, task_id: str, exception: Exception, traceback: str):
    """
    Handler for task failures. This is called when a task fails after all retries.

    Args:
        task_id: ID of the failed task
        exception: Exception that caused the failure
        traceback: Traceback of the exception
    """
    import logging
    logger = logging.getLogger(__name__)

    logger.error(
        f"Task {task_id} failed after all retries: {exception}",
        extra={
            "task_id": task_id,
            "exception": str(exception),
            "traceback": traceback,
        }
    )

    # Here you could:
    # - Send notification to monitoring system (e.g., Sentry)
    # - Store failure in database for admin review
    # - Send alert to ops team
    # - Trigger webhook for failure notification

# Periodic tasks schedule
celery_app.conf.beat_schedule = {
    "check-pypi-versions": {
        "task": "app.tasks.pypi_check.check_package_versions",
        "schedule": settings.PYPI_CHECK_INTERVAL_HOURS * 3600.0,
    },
    "retry-failed-webhooks": {
        "task": "retry_failed_webhooks",
        "schedule": 300.0,  # Every 5 minutes
    },
}
