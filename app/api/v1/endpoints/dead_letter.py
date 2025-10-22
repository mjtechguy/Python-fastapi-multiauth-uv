"""Dead letter queue management endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.dead_letter import (
    DeadLetterTaskResponse,
    DeadLetterTaskListResponse,
    ResolveDeadLetterTaskRequest,
    IgnoreDeadLetterTaskRequest,
    DeadLetterStatisticsResponse,
)
from app.services.dead_letter import DeadLetterService

router = APIRouter(prefix="/dead-letter", tags=["dead-letter-queue"])


@router.get("/statistics", response_model=DeadLetterStatisticsResponse)
async def get_dead_letter_statistics(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DeadLetterStatisticsResponse:
    """Get dead letter queue statistics."""
    # TODO: Add admin permission check
    stats = await DeadLetterService.get_statistics(db)
    return DeadLetterStatisticsResponse(**stats)


@router.get("", response_model=DeadLetterTaskListResponse)
async def list_dead_letter_tasks(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    status: str | None = Query(None, description="Filter by status"),
) -> DeadLetterTaskListResponse:
    """List dead letter tasks."""
    # TODO: Add admin permission check
    tasks, total = await DeadLetterService.list_dead_letter_tasks(
        db, page=page, page_size=page_size, status=status
    )

    return DeadLetterTaskListResponse(
        tasks=tasks,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{task_id}", response_model=DeadLetterTaskResponse)
async def get_dead_letter_task(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DeadLetterTaskResponse:
    """Get a specific dead letter task."""
    # TODO: Add admin permission check
    task = await DeadLetterService.get_dead_letter_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@router.post("/{task_id}/resolve", response_model=DeadLetterTaskResponse)
async def resolve_dead_letter_task(
    task_id: str,
    request: ResolveDeadLetterTaskRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DeadLetterTaskResponse:
    """Mark a dead letter task as resolved."""
    # TODO: Add admin permission check
    try:
        task = await DeadLetterService.resolve_dead_letter_task(
            db, task_id, request.resolution_notes, request.resolved_by
        )
        return task
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{task_id}/retry", response_model=DeadLetterTaskResponse)
async def retry_dead_letter_task(
    task_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DeadLetterTaskResponse:
    """Retry a dead letter task."""
    # TODO: Add admin permission check
    try:
        task = await DeadLetterService.retry_dead_letter_task(db, task_id)
        # TODO: Re-queue the task to Celery
        return task
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{task_id}/ignore", response_model=DeadLetterTaskResponse)
async def ignore_dead_letter_task(
    task_id: str,
    request: IgnoreDeadLetterTaskRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DeadLetterTaskResponse:
    """Mark a dead letter task as ignored."""
    # TODO: Add admin permission check
    try:
        task = await DeadLetterService.ignore_dead_letter_task(db, task_id, request.notes)
        return task
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
