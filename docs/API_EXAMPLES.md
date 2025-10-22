# API Examples

Practical examples for using the SaaS Backend API.

## Authentication

### Register a New User

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "username": "johndoe",
    "password": "SecurePassword123!",
    "full_name": "John Doe"
  }'
```

Response:
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "user@example.com",
  "username": "johndoe",
  "full_name": "John Doe",
  "is_active": true,
  "is_verified": false,
  "is_superuser": false,
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z"
}
```

### Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePassword123!"
  }'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### OAuth Login (Google)

1. Get authorization URL:
```bash
curl http://localhost:8000/api/v1/auth/oauth/google/authorize
```

Response:
```json
{
  "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?..."
}
```

2. Redirect user to URL, they authorize, get code
3. Exchange code for tokens:
```bash
curl -X POST http://localhost:8000/api/v1/auth/oauth/google/callback \
  -H "Content-Type: application/json" \
  -d '{
    "code": "authorization_code_from_google",
    "state": "random_state_string"
  }'
```

### Refresh Access Token

```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "your_refresh_token_here"
  }'
```

## User Management

### Get Current User Profile

```bash
curl http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Update Profile

```bash
curl -X PUT http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "full_name": "John Smith",
    "username": "johnsmith"
  }'
```

### Change Password

```bash
curl -X PUT http://localhost:8000/api/v1/users/me/password \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "current_password": "SecurePassword123!",
    "new_password": "NewSecurePassword456!"
  }'
```

## Organization Management

### Create Organization

```bash
curl -X POST http://localhost:8000/api/v1/organizations \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corporation",
    "slug": "acme-corp",
    "description": "Our awesome company"
  }'
```

### List User's Organizations

```bash
curl "http://localhost:8000/api/v1/organizations?page=1&page_size=10" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Get Organization Details

```bash
curl http://localhost:8000/api/v1/organizations/{org_id} \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Add Member to Organization

```bash
curl -X POST http://localhost:8000/api/v1/organizations/{org_id}/members \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-uuid-here",
    "role_ids": ["role-uuid-1", "role-uuid-2"]
  }'
```

## WebSocket Real-Time Connection

### JavaScript Example

```javascript
const token = "YOUR_ACCESS_TOKEN";
const ws = new WebSocket(`ws://localhost:8000/api/v1/ws?token=${token}`);

ws.onopen = () => {
  console.log("Connected!");

  // Send ping
  ws.send(JSON.stringify({
    type: "ping",
    timestamp: Date.now()
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("Received:", data);

  if (data.type === "connected") {
    console.log("Successfully authenticated");
  } else if (data.type === "pong") {
    console.log("Pong received");
  }
};

ws.onerror = (error) => {
  console.error("WebSocket error:", error);
};

ws.onclose = () => {
  console.log("Disconnected");
};
```

### Python Example

```python
import asyncio
import websockets
import json

async def connect():
    token = "YOUR_ACCESS_TOKEN"
    uri = f"ws://localhost:8000/api/v1/ws?token={token}"

    async with websockets.connect(uri) as websocket:
        # Receive welcome message
        response = await websocket.recv()
        print(f"Connected: {response}")

        # Send ping
        await websocket.send(json.dumps({
            "type": "ping",
            "timestamp": asyncio.get_event_loop().time()
        }))

        # Receive pong
        response = await websocket.recv()
        print(f"Received: {response}")

asyncio.run(connect())
```

## Python SDK Example

```python
import httpx
from typing import Optional

class SaaSBackendClient:
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url
        self.api_key = api_key
        self.access_token: Optional[str] = None

    async def login(self, email: str, password: str) -> dict:
        """Login and get access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/auth/login",
                json={"email": email, "password": password}
            )
            response.raise_for_status()
            data = response.json()
            self.access_token = data["access_token"]
            return data

    async def get_profile(self) -> dict:
        """Get current user profile."""
        headers = {"Authorization": f"Bearer {self.access_token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/users/me",
                headers=headers
            )
            response.raise_for_status()
            return response.json()

    async def create_organization(self, name: str, slug: str) -> dict:
        """Create new organization."""
        headers = {"Authorization": f"Bearer {self.access_token}"}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/organizations",
                headers=headers,
                json={"name": name, "slug": slug}
            )
            response.raise_for_status()
            return response.json()

# Usage
async def main():
    client = SaaSBackendClient("http://localhost:8000")

    # Login
    await client.login("user@example.com", "password")

    # Get profile
    profile = await client.get_profile()
    print(f"Logged in as: {profile['email']}")

    # Create organization
    org = await client.create_organization("My Company", "my-company")
    print(f"Created organization: {org['name']}")

asyncio.run(main())
```

## Pagination Example

```python
async def fetch_all_users():
    """Fetch all users with pagination."""
    page = 1
    all_users = []

    while True:
        response = await client.get(
            f"{base_url}/api/v1/users",
            params={"page": page, "page_size": 100},
            headers={"Authorization": f"Bearer {token}"}
        )

        data = response.json()
        all_users.extend(data["items"])

        if not data["has_next"]:
            break

        page += 1

    return all_users
```

## Error Handling

```python
try:
    response = await client.post(url, json=data)
    response.raise_for_status()
except httpx.HTTPStatusError as e:
    if e.response.status_code == 401:
        # Unauthorized - token expired
        await refresh_token()
    elif e.response.status_code == 403:
        # Forbidden - insufficient permissions
        print("Access denied")
    elif e.response.status_code == 422:
        # Validation error
        print("Validation errors:", e.response.json())
    else:
        print(f"HTTP error: {e}")
```

## Rate Limiting

The API has rate limiting enabled (60 requests/minute by default):

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def api_call_with_retry():
    """API call with automatic retry on rate limit."""
    try:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:  # Rate limited
            raise  # Retry
        raise  # Don't retry other errors
```
