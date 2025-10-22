"""API v1 router configuration."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, organizations, teams, health, websocket, totp, files, sessions, quota, webhooks, dead_letter

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
