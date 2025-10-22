"""Dead letter queue model for failed tasks."""

import uuid
from datetime import datetime

from sqlalchemy import String, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class DeadLetterTask(Base):
    """Record of tasks that failed after all retries."""

    __tablename__ = "dead_letter_tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Task details
    task_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    task_name: Mapped[str] = mapped_column(String(255), index=True)
    task_args: Mapped[list | None] = mapped_column(default=None, nullable=True)
    task_kwargs: Mapped[dict | None] = mapped_column(default=None, nullable=True)

    # Failure details
    exception: Mapped[str] = mapped_column(Text)
    traceback: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    # Status
    status: Mapped[str] = mapped_column(
        String(50), default="failed", index=True
    )  # failed, retried, resolved, ignored

    # Resolution
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timestamps
    failed_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )
