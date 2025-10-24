"""Helper functions for organization access patterns."""

import uuid

from fastapi import HTTPException

from app.models.user import User


def get_user_organization_id(user: User) -> uuid.UUID:
    """
    Get organization ID from user's first organization.

    For the single-org membership model, returns the user's only organization.
    For global admins (who can belong to multiple orgs), returns their first organization.

    Args:
        user: User object with organizations relationship loaded

    Returns:
        UUID of the user's (first) organization

    Raises:
        HTTPException: If user doesn't belong to any organization (400)

    Example:
        ```python
        from app.core.organization_helpers import get_user_organization_id

        organization_id = get_user_organization_id(current_user)
        # Use organization_id for queries...
        ```
    """
    if not user.organizations:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to an organization. "
                   "Please contact support to be added to an organization."
        )
    return user.organizations[0].id


def check_user_in_organization(user: User, organization_id: uuid.UUID) -> bool:
    """
    Check if user belongs to a specific organization.

    Args:
        user: User object with organizations relationship loaded
        organization_id: Organization UUID to check

    Returns:
        True if user belongs to the organization, False otherwise

    Example:
        ```python
        if not check_user_in_organization(current_user, org_id):
            raise HTTPException(status_code=403, detail="Access denied")
        ```
    """
    return any(org.id == organization_id for org in user.organizations)
