"""Base database model and imports."""

from app.db.session import Base

# Import all models here for Alembic to detect them
from app.models.user import User
from app.models.organization import Organization
from app.models.team import Team
from app.models.role import Role, Permission, RolePermission
from app.models.oauth import OAuthAccount
from app.models.api_key import APIKey
from app.models.audit_log import AuditLog

__all__ = [
    "Base",
    "User",
    "Organization",
    "Team",
    "Role",
    "Permission",
    "RolePermission",
    "OAuthAccount",
    "APIKey",
    "AuditLog",
]
