# E2E Test Suite

End-to-end tests for the SaaS Backend Framework.

## Quick Start

```bash
# Run all E2E tests
pytest tests/e2e/ -v

# Or use the test runner script
./run_tests.sh
```

## Test Files

| File | Description |
|------|-------------|
| `conftest.py` | Test fixtures and configuration |
| `test_auth_flow.py` | Authentication, email verification, password reset |
| `test_organizations.py` | Organization CRUD, quota management |
| `test_files_and_storage.py` | File uploads, downloads, storage |
| `test_sessions_and_webhooks.py` | Sessions, webhooks, DLQ |
| `test_health_and_monitoring.py` | Health checks, metrics, documentation |

## Running Tests

### All Tests
```bash
pytest tests/e2e/ -v
```

### Specific File
```bash
pytest tests/e2e/test_auth_flow.py -v
```

### Specific Class
```bash
pytest tests/e2e/test_auth_flow.py::TestAuthenticationFlow -v
```

### Single Test
```bash
pytest tests/e2e/test_auth_flow.py::TestAuthenticationFlow::test_register_and_login -v
```

### With Coverage
```bash
pytest tests/e2e/ --cov=app --cov-report=html
```

## Fixtures

Available test fixtures (defined in `conftest.py`):

- **`client`** - Async HTTP client
- **`db_session`** - Database session
- **`test_user`** - Pre-registered user with tokens
- **`authenticated_client`** - Client with auth headers
- **`test_organization`** - Pre-created organization
- **`sample_file_data`** - Sample file content

## Test Database

Tests use a separate database: `saas_backend_test`

**Important:** Never run tests against production database!

## Writing New Tests

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_my_feature(authenticated_client: AsyncClient):
    """Test description."""
    response = await authenticated_client.get("/api/v1/my-endpoint")
    assert response.status_code == 200
    data = response.json()
    assert "expected_field" in data
```

## More Information

See [docs/TESTING.md](../../docs/TESTING.md) for complete documentation.
