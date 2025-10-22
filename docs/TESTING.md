# Testing Guide

Complete guide for testing the SaaS Backend Framework using both automated tests and the CLI tool.

## Table of Contents

- [Quick Start](#quick-start)
- [E2E Test Suite](#e2e-test-suite)
- [CLI Testing Tool](#cli-testing-tool)
- [Test Coverage](#test-coverage)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### 1. Setup Test Environment

```bash
# Install dependencies
uv pip install -e ".[dev,cli]"

# Start services (Docker Compose)
docker-compose up -d

# Wait for services to be ready (30 seconds)
sleep 30

# Run database migrations
docker-compose exec api alembic upgrade head
```

### 2. Run E2E Tests

```bash
# Run all E2E tests
pytest tests/e2e/ -v

# Run specific test file
pytest tests/e2e/test_auth_flow.py -v

# Run with coverage
pytest tests/e2e/ --cov=app --cov-report=html
```

### 3. Use CLI Tool

```bash
# Make CLI executable
chmod +x cli.py

# Get help
python cli.py --help

# Test authentication
python cli.py auth register
python cli.py auth login
python cli.py auth me
```

---

## E2E Test Suite

### Overview

The E2E test suite provides comprehensive coverage of all API endpoints and workflows.

### Test Files

| File | Coverage |
|------|----------|
| `test_auth_flow.py` | Authentication, email verification, password reset |
| `test_organizations.py` | Organization CRUD, quota management |
| `test_files_and_storage.py` | File uploads, storage operations |
| `test_sessions_and_webhooks.py` | Sessions, webhooks, DLQ |
| `test_health_and_monitoring.py` | Health checks, metrics, docs |

### Running Tests

#### Run All Tests

```bash
pytest tests/e2e/ -v
```

#### Run Specific Test Class

```bash
pytest tests/e2e/test_auth_flow.py::TestAuthenticationFlow -v
```

#### Run Single Test

```bash
pytest tests/e2e/test_auth_flow.py::TestAuthenticationFlow::test_register_and_login -v
```

#### Run with Coverage

```bash
pytest tests/e2e/ --cov=app --cov-report=html --cov-report=term
open htmlcov/index.html  # View coverage report
```

#### Run in Parallel

```bash
pytest tests/e2e/ -n auto  # Requires pytest-xdist
```

### Test Fixtures

The test suite uses several fixtures defined in `tests/e2e/conftest.py`:

- **`client`** - Async HTTP client for API calls
- **`db_session`** - Fresh database session for each test
- **`test_user`** - Pre-registered user with tokens
- **`authenticated_client`** - HTTP client with auth headers
- **`test_organization`** - Pre-created organization
- **`sample_file_data`** - Sample file content

### Example Test

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_my_feature(authenticated_client: AsyncClient):
    """Test my new feature."""
    response = await authenticated_client.get("/api/v1/my-endpoint")
    assert response.status_code == 200
    data = response.json()
    assert data["expected_field"] == "expected_value"
```

### Test Database

Tests use a separate test database: `saas_backend_test`

The database is:
- Created at test session start
- Cleaned between tests
- Dropped at test session end

**Important:** Never run tests against your production database!

---

## CLI Testing Tool

### Overview

The CLI tool (`cli.py`) provides an interactive way to test all API endpoints manually.

### Installation

```bash
# Install CLI dependencies
uv pip install -e ".[cli]"

# Make executable (optional)
chmod +x cli.py
```

### Basic Usage

```bash
# Get help
python cli.py --help

# Get help for specific command
python cli.py auth --help
python cli.py auth login --help
```

### Commands Reference

#### Authentication

```bash
# Register new user
python cli.py auth register
# Or with options:
python cli.py auth register --email user@example.com --password "Pass123!" --name "User Name"

# Login (saves token)
python cli.py auth login
python cli.py auth login --email user@example.com --password "Pass123!"

# Get current user info
python cli.py auth me

# Refresh token
python cli.py auth refresh

# Logout (clear tokens)
python cli.py auth logout
```

#### Organizations

```bash
# Create organization
python cli.py org create --name "My Company" --slug "my-company"

# List organizations
python cli.py org list

# Get organization details
python cli.py org get <organization-id>
```

#### Files

```bash
# Upload file
python cli.py files upload /path/to/file.pdf

# List files
python cli.py files list
```

#### Sessions

```bash
# List active sessions
python cli.py sessions list

# Get session statistics
python cli.py sessions stats
```

#### Webhooks

```bash
# List available events
python cli.py webhooks events

# Create webhook
python cli.py webhooks create \
  --url-endpoint "https://webhook.site/xxx" \
  --events "user.created,file.uploaded"

# List webhooks
python cli.py webhooks list
```

#### Quotas

```bash
# Get quota status
python cli.py quota status

# Get usage logs
python cli.py quota logs --page 1 --size 20
```

#### Health Checks

```bash
# Check all services
python cli.py health check-all

# Check individual services
python cli.py health database
python cli.py health redis
python cli.py health celery
python cli.py health storage
```

#### Dead Letter Queue

```bash
# Get DLQ statistics
python cli.py dlq stats

# List failed tasks
python cli.py dlq list
python cli.py dlq list --status failed
```

### Token Management

The CLI automatically manages authentication tokens:

- **Location:** `~/.saas_cli_tokens.json`
- **Saved on:** Successful login
- **Used for:** All authenticated requests
- **Cleared on:** Logout

### Custom Base URL

```bash
# Use different API URL
python cli.py --url http://staging.example.com auth login

# Or set environment variable
export API_BASE_URL=http://staging.example.com
python cli.py auth login
```

### Pretty Output

The CLI uses Rich library for beautiful output:

- ✅ Colored status codes
- 📊 Formatted JSON
- 🎨 Syntax highlighting
- 📋 Progress indicators

---

## Complete Test Workflow

### End-to-End Testing Scenario

Here's a complete workflow to test all major features:

```bash
# 1. Start services
docker-compose up -d
sleep 30

# 2. Run automated tests
pytest tests/e2e/ -v

# 3. Manual testing with CLI

# Authentication
python cli.py auth register \
  --email "test@example.com" \
  --password "SecurePass123!" \
  --name "Test User"

python cli.py auth login \
  --email "test@example.com" \
  --password "SecurePass123!"

python cli.py auth me

# Organization
python cli.py org create \
  --name "Test Company" \
  --slug "test-company" \
  --description "My test organization"

python cli.py org list

# File Upload
echo "Test file content" > test.txt
python cli.py files upload test.txt
python cli.py files list

# Webhooks
python cli.py webhooks events
python cli.py webhooks create \
  --url-endpoint "https://webhook.site/your-unique-id" \
  --events "user.created,file.uploaded"

python cli.py webhooks list

# Quotas
python cli.py quota status
python cli.py quota logs

# Health Checks
python cli.py health check-all
python cli.py health redis
python cli.py health celery

# Sessions
python cli.py sessions list
python cli.py sessions stats

# DLQ
python cli.py dlq stats
python cli.py dlq list

# 4. Check logs
docker-compose logs -f api
```

---

## Test Coverage

### Current Coverage

Run coverage report:

```bash
pytest tests/e2e/ --cov=app --cov-report=term-missing
```

### Target Coverage

- **Overall:** 80%+
- **Critical paths:** 95%+
  - Authentication
  - Authorization
  - Payment/Quotas
  - Data access

### Coverage Report

```bash
# Generate HTML report
pytest tests/e2e/ --cov=app --cov-report=html

# Open in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

---

## Troubleshooting

### Common Issues

#### 1. Connection Refused

**Problem:** `ConnectionRefusedError` or `Connection refused`

**Solution:**
```bash
# Check if services are running
docker-compose ps

# Check API logs
docker-compose logs api

# Restart services
docker-compose restart
```

#### 2. Database Errors

**Problem:** Database connection errors in tests

**Solution:**
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Run migrations
docker-compose exec api alembic upgrade head

# Check database exists
docker-compose exec postgres psql -U postgres -l
```

#### 3. Authentication Errors in CLI

**Problem:** `401 Unauthorized` errors

**Solution:**
```bash
# Clear old tokens
python cli.py auth logout

# Login again
python cli.py auth login

# Check token file
cat ~/.saas_cli_tokens.json
```

#### 4. Import Errors

**Problem:** `ModuleNotFoundError`

**Solution:**
```bash
# Install dependencies
uv pip install -e ".[dev,cli]"

# Check installation
python -c "import typer; import rich; print('OK')"
```

#### 5. Test Database Not Found

**Problem:** `database "saas_backend_test" does not exist`

**Solution:**
```bash
# Create test database
docker-compose exec postgres createdb -U postgres saas_backend_test

# Or let the tests create it automatically
pytest tests/e2e/conftest.py -v
```

### Debug Mode

#### Enable Detailed Logging

```bash
# Set log level
export LOG_LEVEL=DEBUG

# Run tests with output
pytest tests/e2e/ -v -s

# Run CLI with verbose httpx logging
python cli.py auth login --help
```

#### Inspect Test Database

```bash
# Connect to test database
docker-compose exec postgres psql -U postgres saas_backend_test

# List tables
\dt

# Check data
SELECT * FROM users;
```

### Performance Issues

#### Slow Tests

```bash
# Run tests in parallel
pytest tests/e2e/ -n auto

# Run only fast tests
pytest tests/e2e/ -m "not slow"

# Profile tests
pytest tests/e2e/ --durations=10
```

---

## Best Practices

### 1. Test Isolation

- Each test should be independent
- Use fixtures for setup/teardown
- Don't rely on test execution order

### 2. Test Data

- Use meaningful test data
- Clean up after tests
- Don't use production data

### 3. Assertions

- Be specific in assertions
- Test both success and failure cases
- Verify error messages

### 4. Coverage

- Aim for high coverage, not 100%
- Focus on critical paths
- Don't test framework code

### 5. Documentation

- Document complex test scenarios
- Add comments for non-obvious assertions
- Keep test names descriptive

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install uv
          uv pip install -e ".[dev]"

      - name: Run tests
        run: pytest tests/e2e/ -v --cov=app
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/saas_backend_test
          REDIS_URL: redis://localhost:6379/0

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## Next Steps

1. ✅ Run the E2E test suite
2. ✅ Try the CLI tool
3. ✅ Check test coverage
4. ✅ Add your own tests
5. ✅ Integrate with CI/CD

**Happy Testing! 🧪**
