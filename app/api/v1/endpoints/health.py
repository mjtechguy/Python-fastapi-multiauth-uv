"""Health check endpoints."""

import time
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check() -> dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "healthy", "environment": settings.APP_ENV}


@router.get("/db")
async def database_health(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Database health check endpoint with performance metrics and schema version."""
    try:
        # Test connection with query performance measurement
        start_time = time.perf_counter()
        result = await db.execute(text("SELECT 1"))
        result.scalar_one()
        query_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Get schema version (current Alembic migration)
        schema_version = "unknown"
        try:
            version_result = await db.execute(text("SELECT version_num FROM alembic_version"))
            version_row = version_result.first()
            if version_row:
                schema_version = version_row[0]
        except Exception:
            # Table might not exist in test environments
            schema_version = "not_initialized"

        # Get connection pool stats
        pool_stats = {}
        try:
            # Access the connection pool from the engine
            pool = db.get_bind().pool
            pool_stats = {
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "max_overflow": pool._max_overflow,
            }
        except Exception:
            # Pool stats might not be available in all configurations
            pool_stats = {"available": False}

        return {
            "status": "healthy",
            "database": "connected",
            "type": "postgresql",
            "query_performance_ms": query_time_ms,
            "schema_version": schema_version,
            "connection_pool": pool_stats,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
        }


@router.get("/redis")
async def redis_health() -> dict[str, Any]:
    """Redis health check endpoint with memory usage and performance metrics."""
    from app.services.cache import cache

    try:
        # Test write with performance measurement
        test_key = "health_check_test"
        test_value = "ok"

        start_time = time.perf_counter()
        await cache.set(test_key, test_value, expire=10)
        write_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Test read with performance measurement
        start_time = time.perf_counter()
        result = await cache.get(test_key)
        read_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Cleanup
        await cache.delete(test_key)

        # Get Redis info (memory usage and stats)
        redis_info = {}
        try:
            # Access the underlying Redis client
            redis_client = cache.redis
            info = await redis_client.info("memory")

            # Extract useful memory metrics
            redis_info = {
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "used_memory_peak_human": info.get("used_memory_peak_human", "unknown"),
                "used_memory_rss_human": info.get("used_memory_rss_human", "unknown"),
                "maxmemory_human": info.get("maxmemory_human", "0B") if info.get("maxmemory", 0) > 0 else "unlimited",
                "mem_fragmentation_ratio": round(info.get("mem_fragmentation_ratio", 0), 2),
            }

            # Get server info for additional stats
            server_info = await redis_client.info("server")
            redis_info["version"] = server_info.get("redis_version", "unknown")

            # Get keyspace info
            keyspace_info = await redis_client.info("keyspace")
            total_keys = 0
            for _db_name, db_info in keyspace_info.items():
                if isinstance(db_info, dict):
                    total_keys += db_info.get("keys", 0)
            redis_info["total_keys"] = total_keys

        except Exception as e:
            redis_info = {"error": f"Could not fetch Redis info: {e!s}"}

        if result == test_value:
            return {
                "status": "healthy",
                "redis": "connected",
                "read_write": "ok",
                "performance_ms": {
                    "read": read_time_ms,
                    "write": write_time_ms,
                },
                "memory": redis_info,
            }
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
    """Storage service health check endpoint with performance and space metrics."""
    import os
    from io import BytesIO

    from app.services.storage import storage_service

    try:
        # Test write with performance measurement
        test_content = b"health_check_test"
        test_file = BytesIO(test_content)
        test_filename = "health_check_test.txt"

        start_time = time.perf_counter()
        storage_path, provider, _checksum = await storage_service.upload(
            test_file, test_filename, "text/plain"
        )
        upload_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Test read with performance measurement
        start_time = time.perf_counter()
        downloaded_content = await storage_service.download(storage_path)
        download_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Cleanup
        await storage_service.delete(storage_path)

        # Get storage space information
        space_info = {}
        try:
            if provider == "local":
                # For local storage, get filesystem stats
                storage_path_dir = os.path.dirname(storage_service.storage_path) if hasattr(storage_service, 'storage_path') else "/tmp"
                if os.path.exists(storage_path_dir):
                    stat = os.statvfs(storage_path_dir)
                    total_bytes = stat.f_blocks * stat.f_frsize
                    available_bytes = stat.f_bavail * stat.f_frsize
                    used_bytes = total_bytes - available_bytes

                    space_info = {
                        "total_gb": round(total_bytes / (1024**3), 2),
                        "used_gb": round(used_bytes / (1024**3), 2),
                        "available_gb": round(available_bytes / (1024**3), 2),
                        "usage_percent": round((used_bytes / total_bytes * 100) if total_bytes > 0 else 0, 2),
                    }
            elif provider == "s3":
                # S3 doesn't have space limits, but we can show bucket info
                space_info = {
                    "type": "s3",
                    "available": "unlimited",
                    "note": "S3 storage scales automatically"
                }
            else:
                space_info = {"available": "unknown"}
        except Exception as e:
            space_info = {"error": f"Could not fetch space info: {e!s}"}

        if downloaded_content == test_content:
            return {
                "status": "healthy",
                "storage": "connected",
                "provider": provider,
                "read_write": "ok",
                "performance_ms": {
                    "upload": upload_time_ms,
                    "download": download_time_ms,
                },
                "space": space_info,
            }
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
