"""Structured logging configuration with structlog."""

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from app.core.config import settings


def add_app_context(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add application context to log events."""
    event_dict["app_name"] = settings.APP_NAME
    event_dict["environment"] = settings.APP_ENV
    return event_dict


def configure_logging() -> None:
    """
    Configure structlog for production-grade structured logging.

    This sets up a processor pipeline optimized for:
    - JSON output in production
    - Human-readable console output in development
    - Async context propagation
    - OpenTelemetry integration readiness
    - Performance optimization
    """
    # Determine if we're in development mode
    is_dev = settings.APP_ENV in ("development", "dev", "local")

    # Configure standard library logging (structlog integrates with it)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if settings.DEBUG else logging.INFO,
    )

    # Shared processors for both dev and prod
    shared_processors: list[Processor] = [
        # Add log level to event dict
        structlog.stdlib.add_log_level,
        # Add logger name
        structlog.stdlib.add_logger_name,
        # Add timestamp in ISO format with timezone
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # Merge context variables (request ID, user ID, etc.)
        structlog.contextvars.merge_contextvars,
        # Add application context
        add_app_context,
        # Add stack info for exceptions
        structlog.processors.StackInfoRenderer(),
        # Format exceptions properly
        structlog.processors.format_exc_info,
        # Decode unicode
        structlog.processors.UnicodeDecoder(),
    ]

    if is_dev:
        # Development: beautiful console output with colors
        processors = shared_processors + [
            # Add colors and pretty formatting
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            )
        ]
    else:
        # Production: JSON output for log aggregation
        processors = shared_processors + [
            # Render as JSON for parsing by log collectors
            structlog.processors.JSONRenderer(serializer=orjson.dumps)
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        # Use LoggerFactory to integrate with stdlib logging
        logger_factory=structlog.stdlib.LoggerFactory(),
        # Wrap logger for better typing
        wrapper_class=structlog.stdlib.BoundLogger,
        # Cache loggers for performance (major speedup)
        cache_logger_on_first_use=True,
        # Context class for thread-local context
        context_class=dict,
    )

    # Configure structlog's integration with stdlib
    structlog.stdlib.recreate_defaults()

    # Get root logger and set level
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)


def get_logger(name: str | None = None) -> Any:
    """
    Get a structlog logger instance.

    Args:
        name: Logger name (usually __name__). If None, returns root logger.

    Returns:
        Configured structlog logger

    Example:
        ```python
        logger = get_logger(__name__)
        logger.info("user_logged_in", user_id=user.id, ip=request.client.host)
        ```
    """
    return structlog.get_logger(name)


# Import orjson for JSON rendering (only in production)
try:
    import orjson
except ImportError:
    # Fallback to standard json if orjson not available
    import json

    class OrjsonFallback:
        """Fallback to standard json if orjson not installed."""

        @staticmethod
        def dumps(obj: Any) -> bytes:
            return json.dumps(obj).encode()

    orjson = OrjsonFallback()  # type: ignore
