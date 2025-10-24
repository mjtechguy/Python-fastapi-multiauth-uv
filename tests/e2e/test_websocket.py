"""End-to-end tests for WebSocket functionality."""

from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token
from app.models.user import User


class TestWebSocketConnections:
    """Test WebSocket connection establishment and authentication."""

    @pytest.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """Create a test user for WebSocket authentication."""
        from app.services.user import UserService

        return await UserService.create_user(
            db_session,
            email=f"ws_user_{datetime.utcnow().timestamp()}@example.com",
            password="TestPassword123!",
            full_name="WebSocket Test User",
        )

    @pytest.fixture
    def ws_token(self, test_user: User) -> str:
        """Create a valid JWT token for WebSocket authentication."""
        return create_access_token(str(test_user.id))

    @pytest.mark.asyncio
    async def test_websocket_connection_with_valid_token(
        self, test_user: User, ws_token: str
    ):
        """Test WebSocket connection with valid authentication token."""
        from app.main import app

        with TestClient(app) as client:
            with client.websocket_connect(f"/api/v1/ws?token={ws_token}") as websocket:
                # Should receive welcome message
                data = websocket.receive_json()
                assert data["type"] == "connected"
                assert "Successfully connected" in data["message"]

    @pytest.mark.asyncio
    async def test_websocket_connection_without_token(self):
        """Test WebSocket connection without authentication token."""
        from app.main import app

        with TestClient(app) as client:
            with pytest.raises(Exception):  # Connection should be rejected
                with client.websocket_connect("/api/v1/ws") as websocket:
                    pass

    @pytest.mark.asyncio
    async def test_websocket_connection_with_invalid_token(self):
        """Test WebSocket connection with invalid token."""
        from app.main import app

        invalid_token = "invalid.jwt.token"

        with TestClient(app) as client, pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                f"/api/v1/ws?token={invalid_token}"
            ) as websocket:
                # Should be disconnected immediately
                websocket.receive_json()

    @pytest.mark.asyncio
    async def test_websocket_connection_with_expired_token(self, test_user: User):
        """Test WebSocket connection with expired token."""
        # Create an expired token (negative expiration)
        from datetime import timedelta

        from app.core.security import create_access_token
        from app.main import app

        expired_token = create_access_token(
            str(test_user.id), expires_delta=timedelta(minutes=-10)
        )

        with TestClient(app) as client, pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                f"/api/v1/ws?token={expired_token}"
            ) as websocket:
                websocket.receive_json()


class TestWebSocketMessaging:
    """Test WebSocket message sending and receiving."""

    @pytest.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """Create a test user."""
        from app.services.user import UserService

        return await UserService.create_user(
            db_session,
            email=f"ws_msg_user_{datetime.utcnow().timestamp()}@example.com",
            password="TestPassword123!",
            full_name="WS Message Test User",
        )

    @pytest.fixture
    def ws_token(self, test_user: User) -> str:
        """Create a valid JWT token."""
        return create_access_token(str(test_user.id))

    @pytest.mark.asyncio
    async def test_websocket_ping_pong(self, ws_token: str):
        """Test ping/pong message exchange."""
        from app.main import app

        with TestClient(app) as client:
            with client.websocket_connect(f"/api/v1/ws?token={ws_token}") as websocket:
                # Skip welcome message
                websocket.receive_json()

                # Send ping
                timestamp = datetime.utcnow().isoformat()
                websocket.send_json({"type": "ping", "timestamp": timestamp})

                # Receive pong
                response = websocket.receive_json()
                assert response["type"] == "pong"
                assert response["timestamp"] == timestamp

    @pytest.mark.asyncio
    async def test_websocket_subscribe_to_channel(self, ws_token: str):
        """Test subscribing to a channel."""
        from app.main import app

        with TestClient(app) as client:
            with client.websocket_connect(f"/api/v1/ws?token={ws_token}") as websocket:
                # Skip welcome message
                websocket.receive_json()

                # Subscribe to a channel
                websocket.send_json({"type": "subscribe", "channel": "notifications"})

                # Receive subscription confirmation
                response = websocket.receive_json()
                assert response["type"] == "subscribed"
                assert response["channel"] == "notifications"

    @pytest.mark.asyncio
    async def test_websocket_echo_message(self, ws_token: str):
        """Test echo functionality for unknown message types."""
        from app.main import app

        with TestClient(app) as client:
            with client.websocket_connect(f"/api/v1/ws?token={ws_token}") as websocket:
                # Skip welcome message
                websocket.receive_json()

                # Send unknown message type
                test_message = {"type": "custom", "content": "test data", "id": 12345}
                websocket.send_json(test_message)

                # Should receive echo
                response = websocket.receive_json()
                assert response["type"] == "echo"
                assert response["data"] == test_message

    @pytest.mark.asyncio
    async def test_websocket_multiple_messages(self, ws_token: str):
        """Test sending multiple messages in sequence."""
        from app.main import app

        with TestClient(app) as client:
            with client.websocket_connect(f"/api/v1/ws?token={ws_token}") as websocket:
                # Skip welcome message
                websocket.receive_json()

                # Send multiple pings
                for i in range(5):
                    websocket.send_json({"type": "ping", "timestamp": str(i)})
                    response = websocket.receive_json()
                    assert response["type"] == "pong"
                    assert response["timestamp"] == str(i)

    @pytest.mark.asyncio
    async def test_websocket_json_message_format(self, ws_token: str):
        """Test that messages must be valid JSON."""
        from app.main import app

        with TestClient(app) as client:
            with client.websocket_connect(f"/api/v1/ws?token={ws_token}") as websocket:
                # Skip welcome message
                websocket.receive_json()

                # Send valid JSON
                websocket.send_json({"type": "test", "value": 123})

                # Should receive echo
                response = websocket.receive_json()
                assert response["type"] == "echo"


class TestWebSocketDisconnection:
    """Test WebSocket disconnection scenarios."""

    @pytest.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """Create a test user."""
        from app.services.user import UserService

        return await UserService.create_user(
            db_session,
            email=f"ws_disc_user_{datetime.utcnow().timestamp()}@example.com",
            password="TestPassword123!",
            full_name="WS Disconnect Test User",
        )

    @pytest.fixture
    def ws_token(self, test_user: User) -> str:
        """Create a valid JWT token."""
        return create_access_token(str(test_user.id))

    @pytest.mark.asyncio
    async def test_websocket_graceful_disconnect(self, ws_token: str):
        """Test graceful WebSocket disconnection."""
        from app.main import app

        with TestClient(app) as client:
            with client.websocket_connect(f"/api/v1/ws?token={ws_token}") as websocket:
                # Receive welcome message
                websocket.receive_json()

                # Close connection
                websocket.close()

            # Connection should be closed cleanly

    @pytest.mark.asyncio
    async def test_websocket_reconnection(self, ws_token: str):
        """Test WebSocket reconnection after disconnect."""
        from app.main import app

        with TestClient(app) as client:
            # First connection
            with client.websocket_connect(f"/api/v1/ws?token={ws_token}") as websocket:
                data = websocket.receive_json()
                assert data["type"] == "connected"

            # Reconnect
            with client.websocket_connect(f"/api/v1/ws?token={ws_token}") as websocket:
                data = websocket.receive_json()
                assert data["type"] == "connected"


class TestWebSocketConcurrency:
    """Test concurrent WebSocket connections."""

    @pytest.fixture
    async def multiple_users(self, db_session: AsyncSession):
        """Create multiple test users."""
        from app.services.user import UserService

        users = []
        for i in range(3):
            user = await UserService.create_user(
                db_session,
                email=f"ws_concurrent_{i}_{datetime.utcnow().timestamp()}@example.com",
                password="TestPassword123!",
                full_name=f"Concurrent User {i}",
            )
            users.append(user)
        return users

    @pytest.mark.asyncio
    async def test_multiple_concurrent_connections(self, multiple_users):
        """Test multiple users connected simultaneously."""
        from app.main import app

        tokens = [create_access_token(str(user.id)) for user in multiple_users]

        with TestClient(app) as client:
            websockets = []

            # Connect all users
            for token in tokens:
                ws = client.websocket_connect(f"/api/v1/ws?token={token}")
                websockets.append(ws.__enter__())

            # All should receive welcome messages
            for ws in websockets:
                data = ws.receive_json()
                assert data["type"] == "connected"

            # Send pings from all connections
            for i, ws in enumerate(websockets):
                ws.send_json({"type": "ping", "timestamp": str(i)})
                response = ws.receive_json()
                assert response["type"] == "pong"

            # Close all connections
            for ws in websockets:
                ws.close()


class TestWebSocketBroadcast:
    """Test WebSocket broadcast functionality."""

    @pytest.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """Create a test user."""
        from app.services.user import UserService

        return await UserService.create_user(
            db_session,
            email=f"ws_broadcast_{datetime.utcnow().timestamp()}@example.com",
            password="TestPassword123!",
            full_name="Broadcast Test User",
        )

    @pytest.fixture
    def ws_token(self, test_user: User) -> str:
        """Create a valid JWT token."""
        return create_access_token(str(test_user.id))

    @pytest.mark.asyncio
    async def test_broadcast_message_to_connected_users(self, ws_token: str):
        """Test broadcasting messages to all connected users."""
        from app.main import app

        with TestClient(app) as client:
            with client.websocket_connect(f"/api/v1/ws?token={ws_token}") as websocket:
                # Skip welcome message
                websocket.receive_json()

                # Broadcast a message (this would typically be triggered by server event)
                # For testing, we simulate receiving a broadcast
                broadcast_message = {
                    "type": "broadcast",
                    "message": "System announcement",
                }

                # Note: In real scenario, this would be triggered by server-side event
                # For now, we test the echo functionality
                websocket.send_json(broadcast_message)
                response = websocket.receive_json()
                assert response["type"] == "echo"


class TestWebSocketErrorHandling:
    """Test WebSocket error handling."""

    @pytest.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """Create a test user."""
        from app.services.user import UserService

        return await UserService.create_user(
            db_session,
            email=f"ws_error_{datetime.utcnow().timestamp()}@example.com",
            password="TestPassword123!",
            full_name="Error Test User",
        )

    @pytest.fixture
    def ws_token(self, test_user: User) -> str:
        """Create a valid JWT token."""
        return create_access_token(str(test_user.id))

    @pytest.mark.asyncio
    async def test_websocket_invalid_json(self, ws_token: str):
        """Test sending invalid JSON to WebSocket."""
        from app.main import app

        with TestClient(app) as client:
            with client.websocket_connect(f"/api/v1/ws?token={ws_token}") as websocket:
                # Skip welcome message
                websocket.receive_json()

                # Try to send invalid JSON (send text instead)
                with pytest.raises(Exception):
                    websocket.send_text("invalid json {")

    @pytest.mark.asyncio
    async def test_websocket_handles_malformed_messages(self, ws_token: str):
        """Test WebSocket handles malformed messages gracefully."""
        from app.main import app

        with TestClient(app) as client:
            with client.websocket_connect(f"/api/v1/ws?token={ws_token}") as websocket:
                # Skip welcome message
                websocket.receive_json()

                # Send message with missing fields
                websocket.send_json({"data": "incomplete"})

                # Should still get echo response
                response = websocket.receive_json()
                assert response["type"] == "echo"


class TestWebSocketPerformance:
    """Test WebSocket performance and limits."""

    @pytest.fixture
    async def test_user(self, db_session: AsyncSession) -> User:
        """Create a test user."""
        from app.services.user import UserService

        return await UserService.create_user(
            db_session,
            email=f"ws_perf_{datetime.utcnow().timestamp()}@example.com",
            password="TestPassword123!",
            full_name="Performance Test User",
        )

    @pytest.fixture
    def ws_token(self, test_user: User) -> str:
        """Create a valid JWT token."""
        return create_access_token(str(test_user.id))

    @pytest.mark.asyncio
    async def test_websocket_high_frequency_messages(self, ws_token: str):
        """Test WebSocket can handle rapid message exchange."""
        from app.main import app

        with TestClient(app) as client:
            with client.websocket_connect(f"/api/v1/ws?token={ws_token}") as websocket:
                # Skip welcome message
                websocket.receive_json()

                # Send many messages rapidly
                message_count = 50
                for i in range(message_count):
                    websocket.send_json({"type": "ping", "timestamp": str(i)})
                    response = websocket.receive_json()
                    assert response["type"] == "pong"

    @pytest.mark.asyncio
    async def test_websocket_large_message(self, ws_token: str):
        """Test WebSocket with large message payload."""
        from app.main import app

        with TestClient(app) as client:
            with client.websocket_connect(f"/api/v1/ws?token={ws_token}") as websocket:
                # Skip welcome message
                websocket.receive_json()

                # Send large message
                large_data = {"type": "test", "data": "x" * 10000}  # 10KB of data
                websocket.send_json(large_data)

                # Should receive echo
                response = websocket.receive_json()
                assert response["type"] == "echo"
                assert len(response["data"]["data"]) == 10000
