"""Celery application configuration."""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "saas_backend",
    broker=str(settings.CELERY_BROKER_URL),
    backend=str(settings.CELERY_RESULT_BACKEND),
    include=["app.tasks.email", "app.tasks.pypi_check"],
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
)

# Periodic tasks schedule
celery_app.conf.beat_schedule = {
    "check-pypi-versions": {
        "task": "app.tasks.pypi_check.check_package_versions",
        "schedule": settings.PYPI_CHECK_INTERVAL_HOURS * 3600.0,
    },
}
