"""RBAC (Role-Based Access Control) dependencies."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.rbac import RBACService


def require_permission(resource: str, action: str):
    """
    Dependency factory for checking permissions.

    Args:
        resource: Resource name (e.g., 'users', 'organizations')
        action: Action name (e.g., 'create', 'read', 'update', 'delete')

    Returns:
        Dependency function that checks permission
    """

    async def permission_checker(
        current_user: Annotated[User, Depends(get_current_user)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> User:
        """Check if user has required permission."""
        has_permission = await RBACService.check_permission(
            db, current_user, resource, action
        )

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {resource}:{action}",
            )

        return current_user

    return permission_checker


def require_organization_permission(resource: str, action: str):
    """
    Dependency factory for checking organization-scoped permissions.

    Args:
        resource: Resource name
        action: Action name

    Returns:
        Dependency function that checks permission with organization context
    """

    async def permission_checker(
        organization_id: UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> User:
        """Check if user has required permission in organization."""
        has_permission = await RBACService.check_permission(
            db, current_user, resource, action, organization_id=organization_id
        )

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {resource}:{action} in organization",
            )

        return current_user

    return permission_checker
