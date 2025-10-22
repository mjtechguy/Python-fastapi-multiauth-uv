"""Main FastAPI application."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1 import api_router
from app.core.config import settings
from app.core.exceptions import BaseAPIException
from app.core.logging_config import configure_logging, get_logger
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.rate_limit import limiter
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.logging import LoggingMiddleware
from app.middleware.graceful_shutdown import GracefulShutdownMiddleware
from app.core.graceful_shutdown import shutdown_handler

# Configure structured logging FIRST (before any logging occurs)
configure_logging()

# Get structlog logger
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifespan context manager for startup and shutdown events.

    Args:
        app: FastAPI application instance

    Yields:
        None
    """
    # Startup
    logger.info(
        "application_starting",
        app_name=settings.APP_NAME,
        environment=settings.APP_ENV,
        debug=settings.DEBUG
    )

    # Setup graceful shutdown signal handlers (only in production)
    if settings.APP_ENV == "production":
        shutdown_handler.setup_signal_handlers()
        logger.info("graceful_shutdown_handlers_registered")

    # Initialize cache
    from app.services.cache import cache

    await cache.connect()
    logger.info("cache_connected")

    # Register cache cleanup callback (only in production)
    if settings.APP_ENV == "production":
        shutdown_handler.add_cleanup_callback(cache.disconnect)

    # Initialize database tables
    from app.db.session import Base, async_engine
    import app.models  # Import all models to register them with Base

    async with async_engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database_tables_created")

    # Initialize database (create default roles/permissions)
    from app.db.session import AsyncSessionLocal
    from app.services.rbac import RBACService

    async with AsyncSessionLocal() as db:
        try:
            await RBACService.initialize_default_permissions(db)
            await RBACService.initialize_default_roles(db)
            await db.commit()
            logger.info("database_initialized")
        except Exception as e:
            logger.error(
                "database_initialization_failed",
                error=str(e),
                exc_info=True
            )

    yield

    # Shutdown
    logger.info("application_shutting_down", app_name=settings.APP_NAME)

    # Graceful shutdown only in production (skip in dev to allow hot reload)
    if settings.APP_ENV == "production":
        # Wait for active requests to complete
        await shutdown_handler.wait_for_active_requests()
        # Run cleanup callbacks
        await shutdown_handler.run_cleanup_callbacks()
    else:
        # In development, just disconnect cache directly
        await cache.disconnect()


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="Production-grade FastAPI backend framework for scalable SaaS applications",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add graceful shutdown middleware (only in production, causes issues with hot reload in dev)
if settings.APP_ENV == "production":
    app.add_middleware(GracefulShutdownMiddleware)

# Add request ID middleware (before logging middleware)
app.add_middleware(RequestIDMiddleware)

# Add logging middleware (after request ID, before others)
app.add_middleware(LoggingMiddleware)

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Custom exception handler for BaseAPIException
@app.exception_handler(BaseAPIException)
async def api_exception_handler(request: Request, exc: BaseAPIException):
    """Handle custom API exceptions."""
    logger.warning(
        "api_exception",
        message=exc.message,
        status_code=exc.status_code,
        path=str(request.url.path),
        exception_type=type(exc).__name__
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message}
    )


# Include API router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# Setup Prometheus metrics
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": "0.1.0",
        "docs": "/docs",
        "metrics": "/metrics",
        "environment": settings.APP_ENV,
    }


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
