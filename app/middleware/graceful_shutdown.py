"""Middleware for graceful shutdown handling."""

import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.graceful_shutdown import shutdown_handler

logger = logging.getLogger(__name__)


class GracefulShutdownMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track active requests and reject new requests during shutdown.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        """
        Track active requests and handle shutdown state.

        Args:
            request: Incoming request
            call_next: Next middleware/endpoint handler

        Returns:
            Response from the endpoint or 503 if shutting down
        """
        # Reject new requests during shutdown
        if shutdown_handler.is_shutting_down:
            logger.warning(f"Rejecting new request to {request.url.path} - server is shutting down")
            return Response(
                content="Server is shutting down, please try again later",
                status_code=503,
                headers={"Retry-After": "30"}
            )

        # Track active requests
        shutdown_handler.active_requests += 1
        logger.debug(f"Request started: {request.url.path} (active: {shutdown_handler.active_requests})")

        try:
            response = await call_next(request)
            return response
        finally:
            # Decrement active request counter
            shutdown_handler.active_requests -= 1
            logger.debug(
                f"Request completed: {request.url.path} (active: {shutdown_handler.active_requests})"
            )
