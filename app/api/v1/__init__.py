"""API v1 router configuration."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, organizations, health, websocket

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(organizations.router)
api_router.include_router(websocket.router)
