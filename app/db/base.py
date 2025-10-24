"""Base database model and imports."""

from app.db.session import Base
from app.models.api_key import APIKey
from app.models.audit_log import AuditLog
from app.models.dead_letter import DeadLetterTask
from app.models.feature_flag import FeatureFlag
from app.models.file import File
from app.models.invitation import Invitation
from app.models.notification import Notification
from app.models.oauth import OAuthAccount
from app.models.organization import Organization
from app.models.quota import OrganizationQuota, UsageLog
from app.models.role import Permission, Role, RolePermission
from app.models.session import UserSession
from app.models.team import Team
from app.models.token import EmailVerificationToken, PasswordResetToken
from app.models.totp import TOTPSecret

# Import all models here for Alembic to detect them
from app.models.user import User
from app.models.webhook import Webhook, WebhookDelivery

__all__ = [
    "APIKey",
    "AuditLog",
    "Base",
    "DeadLetterTask",
    "EmailVerificationToken",
    "FeatureFlag",
    "File",
    "Invitation",
    "Notification",
    "OAuthAccount",
    "Organization",
    "OrganizationQuota",
    "PasswordResetToken",
    "Permission",
    "Role",
    "RolePermission",
    "TOTPSecret",
    "Team",
    "UsageLog",
    "User",
    "UserSession",
    "Webhook",
    "WebhookDelivery",
]
