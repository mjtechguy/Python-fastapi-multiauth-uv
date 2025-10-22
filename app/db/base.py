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
from app.models.totp import TOTPSecret
from app.models.session import UserSession
from app.models.notification import Notification
from app.models.invitation import Invitation
from app.models.feature_flag import FeatureFlag
from app.models.file import File
from app.models.token import PasswordResetToken, EmailVerificationToken

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
    "TOTPSecret",
    "UserSession",
    "Notification",
    "Invitation",
    "FeatureFlag",
    "File",
    "PasswordResetToken",
    "EmailVerificationToken",
]
