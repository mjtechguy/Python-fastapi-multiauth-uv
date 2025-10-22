"""Main FastAPI application."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1 import api_router
from app.core.config import settings
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.rate_limit import limiter
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.graceful_shutdown import GracefulShutdownMiddleware
from app.core.graceful_shutdown import shutdown_handler


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
    print(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode")

    # Setup graceful shutdown signal handlers
    shutdown_handler.setup_signal_handlers()
    print("Graceful shutdown handlers registered")

    # Initialize cache
    from app.services.cache import cache

    await cache.connect()
    print("Cache service connected")

    # Register cache cleanup callback
    shutdown_handler.add_cleanup_callback(cache.disconnect)

    # Initialize database (create default roles/permissions)
    from app.db.session import AsyncSessionLocal
    from app.services.rbac import RBACService

    async with AsyncSessionLocal() as db:
        try:
            await RBACService.initialize_default_permissions(db)
            await RBACService.initialize_default_roles(db)
            await db.commit()
            print("Database initialized with default roles and permissions")
        except Exception as e:
            print(f"Error initializing database: {e}")

    yield

    # Shutdown
    print(f"Shutting down {settings.APP_NAME}")

    # Wait for active requests to complete
    await shutdown_handler.wait_for_active_requests()

    # Run cleanup callbacks
    await shutdown_handler.run_cleanup_callbacks()


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

# Add graceful shutdown middleware (first, to track all requests)
app.add_middleware(GracefulShutdownMiddleware)

# Add request ID middleware
app.add_middleware(RequestIDMiddleware)

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
