"""Helper utilities for Celery tasks with DLQ support."""

from typing import Any, Callable
from functools import wraps
from celery import Task

from app.core.logging_config import get_logger

logger = get_logger(__name__)


def task_with_dlq(max_retries: int = 3, retry_delay: int = 60):
    """
    Decorator for Celery tasks with automatic DLQ logging on final failure.

    Usage:
        @celery_app.task(bind=True)
        @task_with_dlq(max_retries=3, retry_delay=60)
        def my_task(self, arg1, arg2):
            # Task logic here
            if something_fails:
                raise Exception("Task failed")

    Args:
        max_retries: Maximum number of retries before sending to DLQ
        retry_delay: Delay in seconds between retries

    Note:
        The task will automatically be logged to the DeadLetterTask table
        when it fails after all retries. The @signals.task_failure handler
        in celery_app.py handles this automatically.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self: Task, *args: Any, **kwargs: Any) -> Any:
            try:
                return func(self, *args, **kwargs)
            except Exception as exc:
                # Check if we should retry
                if self.request.retries < max_retries:
                    logger.warning(
                        "task_retry",
                        task_id=self.request.id,
                        task_name=self.name,
                        retry_count=self.request.retries + 1,
                        max_retries=max_retries,
                        exception=str(exc)
                    )
                    raise self.retry(exc=exc, countdown=retry_delay, max_retries=max_retries)
                else:
                    # Final failure - will be caught by @signals.task_failure handler
                    logger.error(
                        "task_final_failure",
                        task_id=self.request.id,
                        task_name=self.name,
                        retry_count=self.request.retries,
                        exception=str(exc)
                    )
                    raise

        return wrapper
    return decorator


class BaseTaskWithDLQ(Task):
    """
    Base task class with automatic retry and DLQ support.

    Usage:
        @celery_app.task(base=BaseTaskWithDLQ, max_retries=3, default_retry_delay=60)
        def my_task(arg1, arg2):
            # Task logic here
            pass

    Features:
        - Automatic retry with exponential backoff
        - Logging of retries and failures
        - Automatic DLQ logging on final failure (via signal handler)
    """

    autoretry_for = (Exception,)
    max_retries = 3
    default_retry_delay = 60
    retry_backoff = True  # Exponential backoff
    retry_backoff_max = 600  # Max 10 minutes
    retry_jitter = True  # Add randomness to prevent thundering herd

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called when task is retried."""
        logger.warning(
            "base_task_retry",
            task_id=task_id,
            task_name=self.name,
            retry_count=self.request.retries,
            exception=str(exc),
            task_args=args,
            task_kwargs=kwargs
        )
        super().on_retry(exc, task_id, args, kwargs, einfo)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """
        Called when task fails after all retries.
        The signal handler will log to DLQ automatically.
        """
        logger.error(
            "base_task_failure",
            task_id=task_id,
            task_name=self.name,
            retry_count=self.request.retries,
            exception=str(exc),
            task_args=args,
            task_kwargs=kwargs
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)
