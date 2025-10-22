"""Health check endpoints."""

from typing import Any
from fastapi import APIRouter, Depends, status as http_status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.config import settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check() -> dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "healthy", "environment": settings.APP_ENV}


@router.get("/db")
async def database_health(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Database health check endpoint."""
    try:
        result = await db.execute(text("SELECT 1"))
        result.scalar_one()
        return {
            "status": "healthy",
            "database": "connected",
            "type": "postgresql",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
        }


@router.get("/redis")
async def redis_health() -> dict[str, Any]:
    """Redis health check endpoint."""
    from app.services.cache import cache

    try:
        # Test write
        test_key = "health_check_test"
        test_value = "ok"
        await cache.set(test_key, test_value, expire=10)

        # Test read
        result = await cache.get(test_key)

        # Cleanup
        await cache.delete(test_key)

        if result == test_value:
            return {
                "status": "healthy",
                "redis": "connected",
                "read_write": "ok",
            }
        else:
            return {
                "status": "unhealthy",
                "redis": "connected",
                "read_write": "failed",
                "error": "Read/write test failed",
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "redis": "disconnected",
            "error": str(e),
        }


@router.get("/celery")
async def celery_health() -> dict[str, Any]:
    """Celery workers health check endpoint."""
    from app.tasks.celery_app import celery_app

    try:
        # Get worker stats
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        active = inspect.active()
        registered = inspect.registered()

        if not stats:
            return {
                "status": "unhealthy",
                "celery": "no_workers",
                "workers": 0,
                "error": "No Celery workers are running",
            }

        worker_count = len(stats)
        worker_names = list(stats.keys())

        # Count active tasks
        active_tasks = 0
        if active:
            for worker_tasks in active.values():
                active_tasks += len(worker_tasks)

        # Count registered tasks
        registered_tasks = 0
        if registered:
            for worker_tasks in registered.values():
                registered_tasks += len(worker_tasks)

        return {
            "status": "healthy",
            "celery": "connected",
            "workers": worker_count,
            "worker_names": worker_names,
            "active_tasks": active_tasks,
            "registered_tasks": registered_tasks,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "celery": "disconnected",
            "error": str(e),
        }


@router.get("/storage")
async def storage_health() -> dict[str, Any]:
    """Storage service health check endpoint."""
    from app.services.storage import storage_service
    from io import BytesIO

    try:
        # Test write
        test_content = b"health_check_test"
        test_file = BytesIO(test_content)
        test_filename = "health_check_test.txt"

        storage_path, provider, checksum = await storage_service.upload(
            test_file, test_filename, "text/plain"
        )

        # Test read
        downloaded_content = await storage_service.download(storage_path)

        # Cleanup
        await storage_service.delete(storage_path)

        if downloaded_content == test_content:
            return {
                "status": "healthy",
                "storage": "connected",
                "provider": provider,
                "read_write": "ok",
            }
        else:
            return {
                "status": "unhealthy",
                "storage": "connected",
                "provider": provider,
                "read_write": "failed",
                "error": "Read/write test failed",
            }
    except Exception as e:
        return {
            "status": "unhealthy",
            "storage": "disconnected",
            "error": str(e),
        }


@router.get("/all")
async def all_health_checks(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """
    Comprehensive health check for all services.

    Returns status for database, redis, celery, and storage.
    """
    checks = {
        "database": await database_health(db),
        "redis": await redis_health(),
        "celery": await celery_health(),
        "storage": await storage_health(),
    }

    # Determine overall status
    all_healthy = all(
        check.get("status") == "healthy" for check in checks.values()
    )

    return {
        "status": "healthy" if all_healthy else "unhealthy",
        "environment": settings.APP_ENV,
        "checks": checks,
    }
