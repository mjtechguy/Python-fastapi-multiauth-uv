"""Celery application configuration."""

from celery import Celery
from celery.signals import worker_process_init

from app.core.config import settings
from app.core.logging_config import configure_logging

celery_app = Celery(
    "saas_backend",
    broker=str(settings.CELERY_BROKER_URL),
    backend=str(settings.CELERY_RESULT_BACKEND),
    include=["app.tasks.email", "app.tasks.pypi_check", "app.tasks.webhook"],
)


@worker_process_init.connect
def configure_worker_logging(**kwargs):
    """Configure structlog for Celery workers."""
    configure_logging()

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
    # Redis-compatible DLQ configuration (application-level)
    task_acks_late=True,  # Acknowledge task after it completes (prevents message loss)
    task_reject_on_worker_lost=True,  # Requeue if worker crashes
    task_reject_on_rate_limit=False,
    # Retry policy
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
    # Error handling
    task_send_error_emails=False,  # We use our own monitoring
)


# Celery signal handlers for application-level DLQ
from celery import signals

from app.core.logging_config import get_logger

logger = get_logger(__name__)


@signals.task_failure.connect
def handle_task_failure(sender=None, task_id=None, exception=None, args=None, kwargs=None,
                        traceback=None, einfo=None, **kw):
    """
    Signal handler for task failures.
    Logs failed tasks to database after all retries are exhausted.

    This is triggered when a task fails completely (after max retries).

    NOTE: Uses synchronous database connection to avoid asyncio.run() issues
    in signal handlers (creating new event loops can cause crashes).
    """
    from datetime import datetime, timezone
    from app.db.session import SyncSessionLocal
    from app.models.dead_letter import DeadLetterTask

    # Get retry count from task state
    task = sender
    retry_count = getattr(task.request, 'retries', 0) if hasattr(task, 'request') else 0

    logger.error(
        "task_failed_after_retries",
        task_id=task_id,
        task_name=sender.name if sender else "unknown",
        retry_count=retry_count,
        exception_type=type(exception).__name__,
        exception_message=str(exception),
        task_args=args,
        task_kwargs=kwargs,
    )

    # Store in database for admin review (synchronous to avoid asyncio.run() issues)
    try:
        with SyncSessionLocal() as db:
            dead_letter = DeadLetterTask(
                task_id=task_id,
                task_name=sender.name if sender else "unknown",
                exception=str(exception),
                traceback=str(einfo) if einfo else str(traceback),
                task_args=list(args) if args else None,
                task_kwargs=dict(kwargs) if kwargs else None,
                retry_count=retry_count,
                status="failed",
                failed_at=datetime.now(timezone.utc),
            )
            db.add(dead_letter)
            db.commit()
            logger.info(
                "task_logged_to_dlq",
                task_id=task_id,
                dlq_id=str(dead_letter.id)
            )
    except Exception as e:
        logger.error(
            "dlq_storage_failed",
            task_id=task_id,
            error=str(e),
            exc_info=True
        )

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
