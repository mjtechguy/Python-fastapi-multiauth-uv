"""Add missing indexes to user_sessions and dead_letter_tasks

Revision ID: 001_add_missing_indexes
Revises:
Create Date: 2025-10-22 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_add_missing_indexes'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add missing database indexes for performance optimization."""

    # Add index to user_sessions.created_at for faster session queries
    op.create_index(
        'ix_user_sessions_created_at',
        'user_sessions',
        ['created_at'],
        unique=False
    )

    # Add index to dead_letter_tasks.created_at for faster DLQ queries
    op.create_index(
        'ix_dead_letter_tasks_created_at',
        'dead_letter_tasks',
        ['created_at'],
        unique=False
    )


def downgrade() -> None:
    """Remove added indexes."""

    op.drop_index('ix_dead_letter_tasks_created_at', table_name='dead_letter_tasks')
    op.drop_index('ix_user_sessions_created_at', table_name='user_sessions')
