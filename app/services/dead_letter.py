"""Service for managing dead letter queue."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dead_letter import DeadLetterTask


class DeadLetterService:
    """Service for managing failed tasks in the dead letter queue."""

    @staticmethod
    async def create_dead_letter_task(
        db: AsyncSession,
        task_id: str,
        task_name: str,
        exception: str,
        traceback: str | None = None,
        task_args: list | None = None,
        task_kwargs: dict | None = None,
        retry_count: int = 0,
    ) -> DeadLetterTask:
        """Create a dead letter task record."""
        task = DeadLetterTask(
            task_id=task_id,
            task_name=task_name,
            exception=exception,
            traceback=traceback,
            task_args=task_args,
            task_kwargs=task_kwargs,
            retry_count=retry_count,
            status="failed",
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def get_dead_letter_task(
        db: AsyncSession, task_id: str
    ) -> DeadLetterTask | None:
        """Get a dead letter task by ID."""
        result = await db.execute(
            select(DeadLetterTask).where(DeadLetterTask.task_id == task_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_dead_letter_tasks(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 50,
        status: str | None = None,
    ) -> tuple[list[DeadLetterTask], int]:
        """List dead letter tasks with pagination."""
        query = select(DeadLetterTask)

        if status:
            query = query.where(DeadLetterTask.status == status)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # Get paginated results
        query = query.order_by(DeadLetterTask.failed_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        tasks = list(result.scalars().all())

        return tasks, total

    @staticmethod
    async def resolve_dead_letter_task(
        db: AsyncSession,
        task_id: str,
        resolution_notes: str,
        resolved_by: str,
    ) -> DeadLetterTask:
        """Mark a dead letter task as resolved."""
        task = await DeadLetterService.get_dead_letter_task(db, task_id)
        if not task:
            raise ValueError("Task not found")

        task.status = "resolved"
        task.resolution_notes = resolution_notes
        task.resolved_by = resolved_by
        task.resolved_at = datetime.utcnow()

        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def retry_dead_letter_task(
        db: AsyncSession, task_id: str
    ) -> DeadLetterTask:
        """Mark a dead letter task for retry."""
        task = await DeadLetterService.get_dead_letter_task(db, task_id)
        if not task:
            raise ValueError("Task not found")

        task.status = "retried"
        task.retry_count += 1

        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def ignore_dead_letter_task(
        db: AsyncSession, task_id: str, notes: str | None = None
    ) -> DeadLetterTask:
        """Mark a dead letter task as ignored."""
        task = await DeadLetterService.get_dead_letter_task(db, task_id)
        if not task:
            raise ValueError("Task not found")

        task.status = "ignored"
        if notes:
            task.resolution_notes = notes

        await db.commit()
        await db.refresh(task)
        return task

    @staticmethod
    async def get_statistics(db: AsyncSession) -> dict[str, Any]:
        """Get dead letter queue statistics."""
        # Total tasks
        total_result = await db.execute(select(func.count(DeadLetterTask.id)))
        total = total_result.scalar_one()

        # By status
        status_result = await db.execute(
            select(DeadLetterTask.status, func.count(DeadLetterTask.id))
            .group_by(DeadLetterTask.status)
        )
        by_status = {row[0]: row[1] for row in status_result.all()}

        # Recent failures (last 24 hours)
        from datetime import timedelta
        recent_result = await db.execute(
            select(func.count(DeadLetterTask.id))
            .where(DeadLetterTask.failed_at >= datetime.utcnow() - timedelta(hours=24))
        )
        recent = recent_result.scalar_one()

        return {
            "total": total,
            "by_status": by_status,
            "recent_24h": recent,
        }
