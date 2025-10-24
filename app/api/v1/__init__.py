"""API v1 router configuration."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    api_keys,
    audit_logs,
    auth,
    billing,
    dead_letter,
    feature_flags,
    files,
    health,
    invitations,
    notifications,
    organizations,
    quota,
    sessions,
    stripe_webhooks,
    teams,
    totp,
    users,
    webhooks,
    websocket,
)

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(organizations.router)
api_router.include_router(teams.router)
api_router.include_router(totp.router)
api_router.include_router(files.router)
api_router.include_router(sessions.router)
api_router.include_router(websocket.router)
api_router.include_router(quota.router)
api_router.include_router(webhooks.router)
api_router.include_router(dead_letter.router)
api_router.include_router(billing.router)
api_router.include_router(stripe_webhooks.router)
api_router.include_router(api_keys.router)
api_router.include_router(invitations.router)
api_router.include_router(notifications.router)
api_router.include_router(audit_logs.router)
api_router.include_router(feature_flags.router)
