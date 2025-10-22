"""WebSocket connection manager."""

from typing import Dict
from fastapi import WebSocket


class WebSocketManager:
    """Manage WebSocket connections."""

    def __init__(self):
        """Initialize WebSocket manager."""
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        """
        Accept and store WebSocket connection.

        Args:
            websocket: WebSocket connection
            user_id: User ID to associate with connection
        """
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str) -> None:
        """
        Remove WebSocket connection.

        Args:
            user_id: User ID to disconnect
        """
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_personal_message(self, message: dict, user_id: str) -> None:
        """
        Send message to specific user.

        Args:
            message: Message data to send
            user_id: Target user ID
        """
        if user_id in self.active_connections:
            websocket = self.active_connections[user_id]
            try:
                await websocket.send_json(message)
            except Exception:
                # Connection closed, remove it
                self.disconnect(user_id)

    async def broadcast(self, message: dict) -> None:
        """
        Broadcast message to all connected users.

        Args:
            message: Message data to broadcast
        """
        disconnected_users = []

        for user_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected_users.append(user_id)

        # Clean up disconnected users
        for user_id in disconnected_users:
            self.disconnect(user_id)

    async def send_to_users(self, message: dict, user_ids: list[str]) -> None:
        """
        Send message to specific list of users.

        Args:
            message: Message data to send
            user_ids: List of user IDs to send to
        """
        for user_id in user_ids:
            await self.send_personal_message(message, user_id)

    def is_connected(self, user_id: str) -> bool:
        """
        Check if user is connected.

        Args:
            user_id: User ID to check

        Returns:
            True if user is connected
        """
        return user_id in self.active_connections

    @property
    def connection_count(self) -> int:
        """Get total number of active connections."""
        return len(self.active_connections)


# Global WebSocket manager instance
ws_manager = WebSocketManager()
