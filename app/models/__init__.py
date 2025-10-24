"""Database models."""

# Import all models here to ensure SQLAlchemy can establish relationships
# This must be done before any database operations
from app.models.api_key import APIKey
from app.models.audit_log import AuditLog
from app.models.billing_event import BillingEvent
from app.models.dead_letter import DeadLetterTask
from app.models.feature_flag import FeatureFlag
from app.models.file import File
from app.models.invitation import Invitation
from app.models.invoice import Invoice
from app.models.notification import Notification
from app.models.oauth import OAuthAccount
from app.models.organization import Organization
from app.models.payment_method import PaymentMethod
from app.models.quota import OrganizationQuota, UsageLog
from app.models.role import Permission, Role, RolePermission
from app.models.session import UserSession
from app.models.subscription import Subscription
from app.models.subscription_plan import SubscriptionPlan
from app.models.team import Team
from app.models.token import EmailVerificationToken, PasswordResetToken
from app.models.totp import TOTPSecret
from app.models.user import User, user_organizations, user_roles, user_teams
from app.models.webhook import Webhook, WebhookDelivery

__all__ = [
    "APIKey",
    "AuditLog",
    "BillingEvent",
    "DeadLetterTask",
    "EmailVerificationToken",
    "FeatureFlag",
    "File",
    "Invitation",
    "Invoice",
    "Notification",
    "OAuthAccount",
    "Organization",
    "OrganizationQuota",
    "PasswordResetToken",
    "PaymentMethod",
    "Permission",
    "Role",
    "RolePermission",
    "Subscription",
    "SubscriptionPlan",
    "TOTPSecret",
    "Team",
    "UsageLog",
    "User",
    "UserSession",
    "Webhook",
    "WebhookDelivery",
    "user_organizations",
    "user_roles",
    "user_teams",
]
