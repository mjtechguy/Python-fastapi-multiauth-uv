"""Graceful shutdown handler for production deployments."""

import asyncio
import signal
from collections.abc import Callable

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class GracefulShutdown:
    """
    Graceful shutdown handler that ensures in-flight requests complete before shutdown.

    Features:
    - Catches SIGTERM and SIGINT signals
    - Waits for in-flight requests to complete
    - Configurable shutdown timeout
    - Prevents new requests during shutdown
    """

    def __init__(self, timeout: int = 30):
        """
        Initialize graceful shutdown handler.

        Args:
            timeout: Maximum time to wait for in-flight requests (seconds)
        """
        self.timeout = timeout
        self.is_shutting_down = False
        self.active_requests = 0
        self._shutdown_event = asyncio.Event()
        self._cleanup_callbacks: list[Callable] = []

    def add_cleanup_callback(self, callback: Callable) -> None:
        """
        Add a cleanup callback to be called during shutdown.

        Args:
            callback: Async or sync function to call during shutdown
        """
        self._cleanup_callbacks.append(callback)

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()

    def trigger_shutdown(self) -> None:
        """Trigger shutdown process."""
        if not self.is_shutting_down:
            logger.info("graceful_shutdown_triggered")
            self.is_shutting_down = True
            self._shutdown_event.set()

    async def wait_for_active_requests(self) -> None:
        """
        Wait for active requests to complete.

        Waits up to self.timeout seconds for all active requests to finish.
        """
        if self.active_requests == 0:
            logger.info("no_active_requests")
            return

        logger.info("waiting_for_active_requests", count=self.active_requests)

        start_time = asyncio.get_event_loop().time()
        while self.active_requests > 0:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= self.timeout:
                logger.warning(
                    "shutdown_timeout_reached",
                    active_requests=self.active_requests,
                    timeout=self.timeout
                )
                break

            logger.debug(
                "waiting_for_requests",
                active_requests=self.active_requests,
                elapsed_seconds=round(elapsed, 1)
            )
            await asyncio.sleep(1)

        logger.info("active_requests_complete")

    async def run_cleanup_callbacks(self) -> None:
        """Run all registered cleanup callbacks."""
        logger.info("running_cleanup_callbacks", count=len(self._cleanup_callbacks))

        for callback in self._cleanup_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                logger.error(
                    "cleanup_callback_error",
                    callback_name=callback.__name__,
                    error=str(e),
                    exc_info=True
                )

    def setup_signal_handlers(self) -> None:
        """
        Setup signal handlers for graceful shutdown.

        Handles SIGTERM (from Kubernetes, Docker, etc.) and SIGINT (Ctrl+C).
        """
        def handle_signal(sig, frame):
            """Signal handler that triggers graceful shutdown."""
            signal_name = signal.Signals(sig).name
            logger.info("shutdown_signal_received", signal=signal_name)
            self.trigger_shutdown()

        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)

        logger.info("shutdown_signal_handlers_registered")


# Global instance
shutdown_handler = GracefulShutdown(timeout=30)
