"""Schemas for dead letter queue."""

import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class DeadLetterTaskResponse(BaseModel):
    """Dead letter task response."""

    id: uuid.UUID
    task_id: str
    task_name: str
    task_args: list | None
    task_kwargs: dict | None
    exception: str
    traceback: str | None
    retry_count: int
    status: str
    resolution_notes: str | None
    resolved_at: datetime | None
    resolved_by: str | None
    failed_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeadLetterTaskListResponse(BaseModel):
    """Paginated dead letter task list response."""

    tasks: list[DeadLetterTaskResponse]
    total: int
    page: int
    page_size: int


class ResolveDeadLetterTaskRequest(BaseModel):
    """Request to resolve a dead letter task."""

    resolution_notes: str = Field(..., description="Notes about the resolution")
    resolved_by: str = Field(..., description="User who resolved the task")


class IgnoreDeadLetterTaskRequest(BaseModel):
    """Request to ignore a dead letter task."""

    notes: str | None = Field(None, description="Notes about why task was ignored")


class DeadLetterStatisticsResponse(BaseModel):
    """Dead letter queue statistics."""

    total: int
    by_status: dict[str, int]
    recent_24h: int
