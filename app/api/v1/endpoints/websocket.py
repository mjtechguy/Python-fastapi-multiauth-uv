"""WebSocket endpoints for real-time features."""

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_token
from app.db.session import get_db
from app.services.user import UserService
from app.services.websocket_manager import ws_manager

router = APIRouter(prefix="/ws", tags=["websocket"])


async def get_user_from_token(token: str, db: AsyncSession):
    """Authenticate WebSocket connection via token."""
    user_id = verify_token(token, token_type="access")
    if not user_id:
        return None

    from uuid import UUID

    return await UserService.get_by_id(db, UUID(user_id))


@router.websocket("")
async def websocket_endpoint(
    websocket: WebSocket, token: str, db: AsyncSession = Depends(get_db)
):
    """
    WebSocket endpoint for real-time updates.

    Query params:
        token: JWT access token for authentication

    Example:
        ws://localhost:8000/api/v1/ws?token=your_jwt_token
    """
    # Authenticate user
    user = await get_user_from_token(token, db)

    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Accept connection
    await ws_manager.connect(websocket, str(user.id))

    try:
        # Send welcome message
        await ws_manager.send_personal_message(
            {"type": "connected", "message": "Successfully connected to WebSocket"},
            str(user.id),
        )

        # Listen for messages
        while True:
            data = await websocket.receive_json()

            # Handle different message types
            message_type = data.get("type")

            if message_type == "ping":
                await ws_manager.send_personal_message(
                    {"type": "pong", "timestamp": data.get("timestamp")}, str(user.id)
                )

            elif message_type == "subscribe":
                # Subscribe to specific channels
                channel = data.get("channel")
                await ws_manager.send_personal_message(
                    {"type": "subscribed", "channel": channel}, str(user.id)
                )

            else:
                # Echo unknown messages
                await ws_manager.send_personal_message(
                    {"type": "echo", "data": data}, str(user.id)
                )

    except WebSocketDisconnect:
        ws_manager.disconnect(str(user.id))
