"""Logging middleware for request context and correlation."""

import time
from typing import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add request context to logs and log HTTP requests.

    This middleware:
    - Binds request_id to structlog context (from RequestIDMiddleware)
    - Binds user_id to context for authenticated requests
    - Logs HTTP requests with timing information
    - Binds trace_id for OpenTelemetry integration (if available)
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request and add logging context."""
        # Get logger
        logger = structlog.get_logger(__name__)

        # Get request ID (added by RequestIDMiddleware)
        request_id = request.headers.get("X-Request-ID", "unknown")

        # Bind request context to all logs in this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_host=request.client.host if request.client else None,
        )

        # Try to get user_id from request state (set by auth dependency)
        if hasattr(request.state, "user"):
            user = request.state.user
            if user:
                user_id = str(getattr(user, "id", None))
                structlog.contextvars.bind_contextvars(user_id=user_id)

        # Try to get trace context from OpenTelemetry (if available)
        try:
            from opentelemetry import trace

            span = trace.get_current_span()
            if span.is_recording():
                trace_id = format(span.get_span_context().trace_id, "032x")
                span_id = format(span.get_span_context().span_id, "016x")
                structlog.contextvars.bind_contextvars(
                    trace_id=trace_id,
                    span_id=span_id,
                )
        except ImportError:
            # OpenTelemetry not installed, skip
            pass

        # Record start time
        start_time = time.time()

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Log successful request
            logger.info(
                "http_request",
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

            return response

        except Exception as exc:
            # Calculate duration even on error
            duration_ms = (time.time() - start_time) * 1000

            # Log failed request
            logger.error(
                "http_request_failed",
                status_code=500,
                duration_ms=round(duration_ms, 2),
                exception=str(exc),
                exc_info=True,
            )

            # Re-raise exception to be handled by exception handlers
            raise

        finally:
            # Clear context variables after request
            structlog.contextvars.clear_contextvars()
