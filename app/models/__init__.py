"""Database models."""

# Import all models here to ensure SQLAlchemy can establish relationships
# This must be done before any database operations
from app.models.user import User, user_organizations, user_roles, user_teams
from app.models.organization import Organization
from app.models.team import Team
from app.models.role import Role, Permission, RolePermission
from app.models.api_key import APIKey
from app.models.oauth import OAuthAccount
from app.models.totp import TOTPSecret
from app.models.session import UserSession
from app.models.token import PasswordResetToken, EmailVerificationToken
from app.models.file import File
from app.models.invitation import Invitation
from app.models.notification import Notification
from app.models.audit_log import AuditLog
from app.models.feature_flag import FeatureFlag
from app.models.webhook import Webhook, WebhookDelivery
from app.models.quota import OrganizationQuota, UsageLog
from app.models.dead_letter import DeadLetterTask

__all__ = [
    "User",
    "user_organizations",
    "user_roles",
    "user_teams",
    "Organization",
    "Team",
    "Role",
    "Permission",
    "RolePermission",
    "APIKey",
    "OAuthAccount",
    "TOTPSecret",
    "UserSession",
    "PasswordResetToken",
    "EmailVerificationToken",
    "File",
    "Invitation",
    "Notification",
    "AuditLog",
    "FeatureFlag",
    "Webhook",
    "WebhookDelivery",
    "OrganizationQuota",
    "UsageLog",
    "DeadLetterTask",
]
