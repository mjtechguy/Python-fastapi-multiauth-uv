"""E2E test fixtures and configuration."""

import asyncio
from collections.abc import AsyncGenerator, Generator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.session import Base, get_db
from app.main import app

# Test database URL (use a separate test database)
TEST_DATABASE_URL = str(settings.DATABASE_URL).replace("/saas_backend", "/saas_backend_test")


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="session")
async def test_session_maker(test_engine):
    """Create test session maker."""
    return async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest.fixture
async def db_session(test_session_maker) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    async with test_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with database override."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(client: AsyncClient) -> dict:
    """Create a test user and return credentials."""
    user_data = {
        "email": "testuser@example.com",
        "password": "TestPassword123!",
        "full_name": "Test User"
    }

    response = await client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code == 201

    # Login to get tokens
    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": user_data["email"],
            "password": user_data["password"]
        }
    )
    assert login_response.status_code == 200

    tokens = login_response.json()

    return {
        **user_data,
        "id": response.json()["id"],
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"]
    }


@pytest.fixture
async def authenticated_client(client: AsyncClient, test_user: dict) -> AsyncClient:
    """Create authenticated client with test user."""
    client.headers.update({
        "Authorization": f"Bearer {test_user['access_token']}"
    })
    return client


@pytest.fixture
async def test_organization(authenticated_client: AsyncClient) -> dict:
    """Create a test organization."""
    org_data = {
        "name": "Test Organization",
        "slug": "test-org",
        "description": "Test organization for E2E tests"
    }

    response = await authenticated_client.post("/api/v1/organizations", json=org_data)
    assert response.status_code == 201

    return response.json()


@pytest.fixture
def sample_file_data() -> bytes:
    """Sample file content for upload tests."""
    return b"Test file content for E2E testing"
