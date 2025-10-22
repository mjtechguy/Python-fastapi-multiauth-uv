# SaaS Backend Framework

A **production-grade**, **enterprise-ready** FastAPI backend framework designed for scalable SaaS applications with comprehensive authentication, multi-tenancy, real-time features, and cloud-native deployment support.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-blue.svg)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## ✨ Features

### 🔐 Authentication & Security

- **Multiple Authentication Strategies**:
  - Local email/password authentication with email verification
  - OAuth2 (Google, GitHub, Microsoft)
  - Keycloak integration for enterprise SSO
  - API key authentication for programmatic access
  - **Two-Factor Authentication (2FA/TOTP)** with QR code generation and backup codes
- **Email Verification & Password Reset** - Secure token-based flows with expiration
- **Session Management** - Device tracking, IP address logging, "logout from all devices"
- **JWT Tokens** - Secure access and refresh tokens with automatic rotation
- **Password Security** - Bcrypt hashing with strength validation and configurable policies
- **Account Protection** - Failed login tracking, automatic lockout, and session timeout

### 👥 Multi-Tenancy & RBAC

- **Organizations** - Top-level tenant isolation with member management
- **Teams** - Sub-groups within organizations for fine-grained access control
- **Role-Based Access Control (RBAC)** - Dynamic permissions system
- **Invitation System** - Secure organization invites with expiration
- **Scoped Resources** - Complete data isolation per tenant
- **Usage Quotas** - Per-organization limits for users, storage, API calls, and file uploads
  - Automatic quota tracking and enforcement
  - Monthly/daily quota resets
  - Usage analytics and reporting
  - Prevent abuse with configurable limits

### 📁 File Storage & Management

- **Flexible Storage** - S3-compatible storage (AWS S3, MinIO, DigitalOcean Spaces)
- **File Upload** - Configurable size limits (default 50MB, adjustable via `.env`)
- **Image Optimization** - Automatic resizing and compression
- **Presigned URLs** - Secure, temporary download links
- **Checksum Validation** - SHA256 integrity verification
- **Metadata Tracking** - File size, type, owner, upload timestamp

### ⚡ Real-Time & Background Processing

- **WebSocket Support** - Real-time bi-directional communication with JWT authentication
- **Webhooks System** - Event-driven integrations with external services
  - 13 event types (user.*, file.*, organization.*, api_key.*, session.*)
  - HMAC signature verification (SHA256)
  - Automatic retry with exponential backoff
  - Delivery tracking and analytics
- **Celery Workers** - Distributed task queue for async operations
- **Dead Letter Queue (DLQ)** - Failed task management with retry/resolve workflows
- **Celery Beat** - Scheduled task execution (cron-like)
- **Flower Dashboard** - Real-time task monitoring and management
- **Redis Caching** - High-performance caching with decorator pattern
- **Feature Flags** - Gradual rollout and A/B testing capabilities

### 🚀 Cloud-Native Deployment

- **Docker & Docker Compose** - Complete containerized development environment
  - PostgreSQL with Adminer UI
  - Redis for caching and message broker
  - MinIO for S3-compatible local storage
  - All application services (API, workers, beat, flower)
- **Kubernetes Ready** - Production-grade K8s manifests with:
  - Horizontal Pod Autoscaler (HPA)
  - Health checks and readiness probes
  - Resource limits and requests
  - ConfigMaps and Secrets management
- **Helm Charts** - Flexible deployment with optional subcharts:
  - PostgreSQL (Bitnami)
  - Redis (Bitnami)
  - MinIO (Bitnami)
- **TLS/SSL Support** - Automated certificate management with cert-manager and Let's Encrypt
- **Graceful Shutdown** - Production-safe deployments with:
  - SIGTERM/SIGINT signal handling
  - Active request tracking
  - Configurable timeout (default 30s)
  - Automatic cleanup callbacks

### 🔧 Developer Experience

- **Type Safety** - Full type hints with Pydantic 2.9+
- **Code Quality** - Black formatting, Ruff linting
- **Testing** - Pytest with async support and fixtures
- **Database Migrations** - Alembic with auto-generation
- **API Documentation** - Auto-generated OpenAPI/Swagger docs
- **Structured Logging** - JSON logs for aggregation and analysis
- **Repository Pattern** - Clean separation of data access and business logic
- **Pagination Utilities** - Standardized cursor and offset pagination
- **Request Tracing** - X-Request-ID for distributed tracing
- **Database Optimization** - Strategic indexes on frequently queried fields

### 🔌 Integrations & Monitoring

- **Prometheus Metrics** - Production-grade observability with `/metrics` endpoint
- **Enhanced Health Checks** - Comprehensive service monitoring:
  - Database connectivity and query performance
  - Redis connection and read/write operations
  - Celery worker status and task counts
  - Storage service availability
  - Aggregate health status endpoint
- **OpenAI API** - LLM provider abstraction (OpenAI, Azure OpenAI, custom endpoints)
- **Email System** - Async email with templates (verification, password reset, notifications)
- **Notification System** - In-app notifications with read/unread tracking
- **PyPI Version Checking** - Automated dependency update monitoring
- **Audit Logging** - Comprehensive security and compliance logging

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- UV package manager

### Option 1: Docker Compose (Recommended for Development)

The fastest way to get started - includes **all services** (PostgreSQL, Redis, MinIO, Adminer):

```bash
# 1. Clone the repository
git clone <repository-url>
cd Python-fastapi-multiauth-uv

# 2. Copy environment file
cp .env.example .env
# Edit .env if needed (defaults work for local development)

# 3. Start all services
docker-compose up -d

# 4. Run database migrations
docker-compose exec api alembic upgrade head

# 5. Access the services
# API: http://localhost:8000
# API Docs: http://localhost:8000/docs
# Adminer (DB UI): http://localhost:8080
# MinIO Console: http://localhost:9001
# Flower (Tasks): http://localhost:5555
```

**That's it!** You now have a complete development environment running.

See [DOCKER_COMPOSE.md](DOCKER_COMPOSE.md) for detailed documentation.

### Option 2: Local Development

```bash
# 1. Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install dependencies
uv pip install -e ".[dev]"

# 3. Start infrastructure services
docker-compose up -d postgres redis

# 4. Set up environment
cp .env.example .env
# Edit .env with your configuration

# 5. Run migrations
alembic upgrade head

# 6. Start the API
uvicorn app.main:app --reload

# 7. Start Celery worker (in another terminal)
celery -A app.tasks.celery_app worker --loglevel=info

# 8. Start Celery beat (in another terminal)
celery -A app.tasks.celery_app beat --loglevel=info

# 9. Start Flower (optional, for monitoring)
celery -A app.tasks.celery_app flower
```

## 📁 Project Structure

```
.
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── dependencies/        # Dependency injection
│   │       └── endpoints/           # API routes
│   │           ├── auth.py          # Authentication
│   │           ├── totp.py          # 2FA/TOTP
│   │           ├── sessions.py      # Session management
│   │           ├── files.py         # File upload/management
│   │           ├── users.py         # User management
│   │           ├── organizations.py # Multi-tenancy
│   │           ├── quota.py         # Usage quotas
│   │           ├── webhooks.py      # Webhook management
│   │           ├── dead_letter.py   # DLQ monitoring
│   │           ├── health.py        # Health checks
│   │           └── websocket.py     # Real-time connections
│   ├── core/                        # Core configuration
│   │   ├── config.py               # Settings management
│   │   └── security.py             # Security utilities
│   ├── db/                          # Database configuration
│   │   ├── base.py                 # Model registry
│   │   └── session.py              # Async session
│   ├── middleware/                  # Custom middleware
│   │   ├── request_id.py           # Request tracing
│   │   ├── security.py             # Security headers
│   │   ├── rate_limit.py           # Rate limiting
│   │   └── graceful_shutdown.py    # Graceful shutdown tracking
│   ├── models/                      # SQLAlchemy models
│   │   ├── user.py                 # User model
│   │   ├── totp.py                 # 2FA secrets
│   │   ├── session.py              # User sessions
│   │   ├── file.py                 # File metadata
│   │   ├── organization.py         # Organizations
│   │   ├── role.py                 # RBAC
│   │   ├── notification.py         # Notifications
│   │   ├── invitation.py           # Invitations
│   │   ├── feature_flag.py         # Feature flags
│   │   ├── token.py                # Email/password reset tokens
│   │   ├── quota.py                # Usage quotas
│   │   ├── webhook.py              # Webhooks
│   │   └── dead_letter.py          # DLQ tasks
│   ├── repositories/                # Data access layer
│   │   ├── base.py                 # Generic CRUD
│   │   └── user_repository.py      # User-specific queries
│   ├── schemas/                     # Pydantic schemas
│   ├── services/                    # Business logic
│   │   ├── auth.py                 # Authentication
│   │   ├── totp.py                 # 2FA operations
│   │   ├── session.py              # Session management
│   │   ├── storage.py              # File storage (S3/local)
│   │   ├── cache.py                # Redis caching
│   │   ├── rbac.py                 # Permissions
│   │   ├── feature_flag.py         # Feature flags
│   │   ├── quota.py                # Usage quota management
│   │   ├── webhook.py              # Webhook delivery
│   │   ├── dead_letter.py          # DLQ management
│   │   └── websocket_manager.py    # WebSocket connections
│   ├── tasks/                       # Celery tasks
│   │   ├── celery_app.py           # Celery config + DLQ
│   │   ├── task_utils.py           # Task base classes
│   │   ├── email.py                # Email tasks
│   │   ├── webhook.py              # Webhook delivery tasks
│   │   └── pypi_check.py           # Dependency monitoring
│   ├── utils/                       # Utilities
│   │   ├── pagination.py           # Pagination helpers
│   │   └── filtering.py            # Query filtering
│   └── main.py                      # Application entry point
├── alembic/                         # Database migrations
├── docs/                            # Documentation
│   ├── ARCHITECTURE.md             # System architecture
│   ├── API_EXAMPLES.md             # API usage examples
│   └── TLS_SETUP.md                # TLS configuration
├── helm/                            # Kubernetes Helm charts
│   └── saas-backend/
│       ├── Chart.yaml              # Chart metadata
│       ├── values.yaml             # Configuration
│       ├── templates/              # K8s manifests
│       └── README.md               # Deployment guide
├── k8s/                             # Kubernetes manifests
│   ├── namespace.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── hpa.yaml                    # Autoscaling
│   ├── cert-issuer.yaml            # TLS certs
│   └── README.md
├── tests/                           # Test suite
│   ├── unit/                       # Unit tests
│   ├── integration/                # Integration tests
│   └── conftest.py                 # Test fixtures
├── docker-compose.yml               # Complete dev environment
├── Dockerfile                       # Container definition
├── pyproject.toml                  # Dependencies (UV)
├── .env.example                    # Environment template
├── DOCKER_COMPOSE.md               # Docker Compose guide
├── PRODUCTION_READY.md             # Production checklist
└── README.md                       # This file
```

## 📡 API Endpoints

### Authentication & Security

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/register` | Register new user (sends verification email) |
| `POST` | `/api/v1/auth/login` | Login with credentials |
| `POST` | `/api/v1/auth/refresh` | Refresh access token |
| `GET` | `/api/v1/auth/me` | Get current user |
| `POST` | `/api/v1/auth/verify-email` | Verify email address with token |
| `POST` | `/api/v1/auth/resend-verification` | Resend verification email |
| `POST` | `/api/v1/auth/request-password-reset` | Request password reset email |
| `POST` | `/api/v1/auth/reset-password` | Reset password with token |
| `GET` | `/api/v1/auth/oauth/{provider}/authorize` | OAuth authorization |
| `POST` | `/api/v1/auth/oauth/{provider}/callback` | OAuth callback |
| `POST` | `/api/v1/auth/keycloak/callback` | Keycloak authentication |

### Two-Factor Authentication (2FA)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/totp/setup` | Set up 2FA (returns QR code) |
| `POST` | `/api/v1/totp/enable` | Enable 2FA after verification |
| `POST` | `/api/v1/totp/verify` | Verify TOTP token during login |
| `POST` | `/api/v1/totp/disable` | Disable 2FA |
| `GET` | `/api/v1/totp/status` | Get 2FA status |
| `POST` | `/api/v1/totp/backup-codes` | Regenerate backup codes |

### Session Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/sessions` | List all active sessions |
| `GET` | `/api/v1/sessions/stats` | Get session statistics |
| `DELETE` | `/api/v1/sessions/{id}` | Revoke specific session |
| `DELETE` | `/api/v1/sessions/all` | Logout from all devices |

### File Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/files/upload` | Upload file (images, documents) |
| `GET` | `/api/v1/files` | List user's files (paginated) |
| `GET` | `/api/v1/files/{id}` | Get file metadata |
| `GET` | `/api/v1/files/{id}/download` | Get presigned download URL |
| `DELETE` | `/api/v1/files/{id}` | Delete file (soft delete) |

### Users

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/users/me` | Get current user profile |
| `PUT` | `/api/v1/users/me` | Update current user |
| `PUT` | `/api/v1/users/me/password` | Change password |
| `GET` | `/api/v1/users` | List users (admin) |
| `GET` | `/api/v1/users/{user_id}` | Get user by ID |
| `DELETE` | `/api/v1/users/{user_id}` | Delete user (admin) |

### Organizations (Multi-Tenancy)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/organizations` | Create organization |
| `GET` | `/api/v1/organizations` | List user's organizations |
| `GET` | `/api/v1/organizations/{org_id}` | Get organization details |
| `PUT` | `/api/v1/organizations/{org_id}` | Update organization |
| `DELETE` | `/api/v1/organizations/{org_id}` | Delete organization |
| `POST` | `/api/v1/organizations/{org_id}/members` | Add member |
| `DELETE` | `/api/v1/organizations/{org_id}/members/{user_id}` | Remove member |

### Real-Time (WebSocket)

| Protocol | Endpoint | Description |
|----------|----------|-------------|
| `WS` | `/api/v1/ws` | WebSocket connection (JWT auth) |

### Usage Quotas

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/quota/status` | Get organization quota status |
| `PUT` | `/api/v1/quota/limits` | Update quota limits (admin) |
| `GET` | `/api/v1/quota/usage-logs` | Get usage history (paginated) |

### Webhooks

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/webhooks/events` | List available event types |
| `POST` | `/api/v1/webhooks` | Create webhook |
| `GET` | `/api/v1/webhooks` | List webhooks |
| `GET` | `/api/v1/webhooks/{id}` | Get webhook details |
| `PUT` | `/api/v1/webhooks/{id}` | Update webhook |
| `DELETE` | `/api/v1/webhooks/{id}` | Delete webhook |
| `POST` | `/api/v1/webhooks/{id}/test` | Test webhook delivery |
| `GET` | `/api/v1/webhooks/{id}/deliveries` | Get delivery history |

### Dead Letter Queue (DLQ)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/dead-letter/statistics` | Get DLQ statistics |
| `GET` | `/api/v1/dead-letter` | List failed tasks |
| `GET` | `/api/v1/dead-letter/{task_id}` | Get task details |
| `POST` | `/api/v1/dead-letter/{task_id}/resolve` | Mark task as resolved |
| `POST` | `/api/v1/dead-letter/{task_id}/retry` | Retry failed task |
| `POST` | `/api/v1/dead-letter/{task_id}/ignore` | Ignore task |

### Health & Monitoring

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Basic health check |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/api/v1/health` | Detailed health check |
| `GET` | `/api/v1/health/db` | Database health check |
| `GET` | `/api/v1/health/redis` | Redis health check |
| `GET` | `/api/v1/health/celery` | Celery workers health check |
| `GET` | `/api/v1/health/storage` | Storage service health check |
| `GET` | `/api/v1/health/all` | Aggregate health check |

Full API documentation available at: `http://localhost:8000/docs`

## ⚙️ Configuration

### Environment Variables

Key configuration options (see `.env.example` for complete list):

```env
# Application
APP_NAME=SaaS Backend Framework
APP_ENV=development
SECRET_KEY=your-secret-key-min-32-chars

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db
DATABASE_POOL_SIZE=20

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_DB=1

# Celery
CELERY_BROKER_URL=redis://localhost:6379/2
CELERY_RESULT_BACKEND=redis://localhost:6379/3

# File Storage
FILE_STORAGE_PROVIDER=s3  # or 'local'
MAX_FILE_SIZE_MB=50
AWS_S3_BUCKET=your-bucket
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_REGION=us-east-1
AWS_ENDPOINT_URL=http://minio:9000  # For MinIO

# OAuth Providers
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GITHUB_CLIENT_ID=your-client-id
GITHUB_CLIENT_SECRET=your-client-secret

# OpenAI
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=gpt-4-turbo-preview

# Security
BCRYPT_ROUNDS=12
PASSWORD_MIN_LENGTH=8
MAX_LOGIN_ATTEMPTS=5
RATE_LIMIT_PER_MINUTE=60
```

### Configurable Features

- **File Upload Size**: Adjust `MAX_FILE_SIZE_MB` in `.env` (no code changes needed)
- **Rate Limiting**: Configure limits per minute via environment variables
- **Session Timeout**: Adjustable session expiration
- **Password Policy**: Minimum length, complexity requirements
- **CORS Origins**: Comma-separated list of allowed origins

## 🐳 Deployment

### Development (Docker Compose)

Complete local environment with all services:

```bash
docker-compose up -d
```

**Services included:**
- API (FastAPI)
- PostgreSQL + Adminer UI
- Redis
- MinIO + Console
- Celery Worker
- Celery Beat
- Flower

See [DOCKER_COMPOSE.md](DOCKER_COMPOSE.md) for detailed guide.

### Production (Kubernetes)

#### Option 1: Direct Kubernetes Manifests

```bash
# Create namespace
kubectl apply -f k8s/namespace.yaml

# Apply configurations
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml  # Edit first!

# Deploy services
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/hpa.yaml

# Set up TLS (cert-manager)
kubectl apply -f k8s/cert-issuer.yaml
```

See [k8s/README.md](k8s/README.md) for detailed guide.

#### Option 2: Helm Chart (Recommended)

**With External Services (Production):**

```bash
helm install saas-backend helm/saas-backend \
  --namespace saas-prod \
  --create-namespace \
  --set secrets.databaseUrl="postgresql://..." \
  --set secrets.redisUrl="redis://..." \
  --set secrets.awsS3Bucket="prod-bucket" \
  --values production-values.yaml
```

**With Optional Subcharts (Development/Staging):**

```bash
# Update dependencies (downloads PostgreSQL, Redis, MinIO charts)
cd helm/saas-backend
helm dependency update

# Install with all subcharts enabled
helm install saas-dev . \
  --namespace saas-dev \
  --create-namespace \
  --set postgresql.enabled=true \
  --set redis.enabled=true \
  --set minio.enabled=true
```

See [helm/saas-backend/README.md](helm/saas-backend/README.md) for detailed deployment guide.

### Production Checklist

Before deploying to production:

- [ ] Generate strong `SECRET_KEY` (min 32 characters)
- [ ] Configure production database (RDS, Cloud SQL, etc.)
- [ ] Set up managed Redis (ElastiCache, Cloud Memorystore)
- [ ] Configure S3 or object storage
- [ ] Set up TLS/SSL certificates (Let's Encrypt via cert-manager)
- [ ] Configure proper CORS origins
- [ ] Set `APP_ENV=production` and `DEBUG=false`
- [ ] Set up monitoring (Sentry, Datadog, etc.)
- [ ] Configure email service (SendGrid, SES, etc.)
- [ ] Set up backup strategy (automated DB backups)
- [ ] Configure rate limiting for production traffic
- [ ] Review and configure security headers
- [ ] Set up centralized logging (ELK, CloudWatch, etc.)
- [ ] Configure OAuth providers (production credentials)
- [ ] Set up alerts and on-call rotation
- [ ] Document runbooks for common issues
- [ ] Load test the application
- [ ] Set up CI/CD pipeline

See [PRODUCTION_READY.md](PRODUCTION_READY.md) for complete production guide.

## 🧪 Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_security.py -v

# Run integration tests
pytest tests/integration/ -v
```

### Code Formatting

```bash
# Format code
black app/ tests/

# Sort imports
ruff check --select I --fix app/ tests/

# Auto-fix linting issues
ruff check --fix app/ tests/
```

### Linting

```bash
# Lint code
ruff check app/ tests/

# Type checking
mypy app/
```

### Security Checks

```bash
# Security scanning
bandit -r app/ -ll

# Dependency vulnerabilities
safety check
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Add new feature"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1

# View migration history
alembic history
```

### Working with WebSockets

```python
# Example: Connect to WebSocket with authentication
import asyncio
import websockets
import json

async def test_websocket():
    # Get JWT token first
    token = "your-jwt-token"

    uri = f"ws://localhost:8000/api/v1/ws?token={token}"
    async with websockets.connect(uri) as websocket:
        # Receive messages
        message = await websocket.recv()
        print(f"Received: {message}")

        # Send message
        await websocket.send(json.dumps({
            "type": "chat",
            "message": "Hello!"
        }))

asyncio.run(test_websocket())
```

## 🏗️ Architecture

### Core Technologies

- **FastAPI** - Modern async web framework
- **SQLAlchemy 2.0** - Async ORM with declarative models
- **Pydantic 2.9+** - Data validation and settings
- **PostgreSQL 16** - Primary database
- **Redis 7** - Caching and message broker
- **Celery** - Distributed task queue
- **Boto3** - AWS S3 integration
- **PyOTP** - TOTP 2FA implementation

### Database Models

- `User` - User accounts with multi-auth support
- `TOTPSecret` - Two-factor authentication secrets and backup codes
- `UserSession` - Session tracking with device fingerprinting
- `PasswordResetToken` & `EmailVerificationToken` - Token-based email flows
- `File` - File metadata and storage references
- `Organization` - Top-level tenants with quota relationships
- `OrganizationQuota` - Usage limits and tracking (users, storage, API calls, uploads)
- `UsageLog` - Detailed usage analytics per organization
- `Team` - Sub-groups within organizations
- `Role` & `Permission` - RBAC implementation
- `OAuthAccount` - Social authentication linkage
- `APIKey` - Programmatic access tokens
- `Webhook` & `WebhookDelivery` - Event notification system
- `DeadLetterTask` - Failed task tracking and management
- `AuditLog` - Security and compliance logging
- `Notification` - In-app notification system
- `Invitation` - Organization invitation system
- `FeatureFlag` - Gradual rollout and A/B testing

### Service Layer

- `AuthService` - Authentication strategies (local, OAuth, Keycloak)
- `TOTPService` - 2FA operations (setup, verification, backup codes)
- `SessionService` - Session management and device tracking
- `FileStorageService` - File upload/download with S3/local providers
- `CacheService` - Redis caching with decorator pattern
- `RBACService` - Role and permission management
- `QuotaService` - Usage quota management and enforcement
- `WebhookService` - Webhook delivery with HMAC signatures
- `DeadLetterService` - Failed task management
- `WebSocketManager` - Real-time connection management
- `FeatureFlagService` - Feature flag evaluation
- `LLMService` - OpenAI/LLM integration

### Background Tasks (Celery)

- Email sending (verification, password reset, notifications)
- Webhook delivery with retry logic
- PyPI version checking
- Session cleanup
- File processing
- Failed task DLQ management
- Custom async operations

### Deployment Targets

- **Development**: Docker Compose (all-in-one)
- **Staging**: Kubernetes with Helm subcharts
- **Production**: Kubernetes with external managed services

## 📚 Documentation

- [Architecture Overview](docs/ARCHITECTURE.md) - System design and patterns
- [API Examples](docs/API_EXAMPLES.md) - Practical usage examples
- [TLS Setup Guide](docs/TLS_SETUP.md) - Certificate configuration
- [Docker Compose Guide](DOCKER_COMPOSE.md) - Local development setup
- [Kubernetes Guide](k8s/README.md) - K8s deployment
- [Helm Chart Guide](helm/saas-backend/README.md) - Helm deployment
- [Production Ready Guide](PRODUCTION_READY.md) - Production checklist

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest`)
5. Run linting (`ruff check app/ && mypy app/`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: See `/docs` directory
- **API Docs**: http://localhost:8000/docs (when running)
- **Issues**: [Create an issue](https://github.com/yourusername/saas-backend/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/saas-backend/discussions)

## 🎯 Use Cases

This framework is perfect for:

- **SaaS Applications** - Multi-tenant with organization/team structure
- **API Backends** - RESTful + WebSocket real-time APIs
- **Mobile Backends** - Secure authentication with file uploads
- **Enterprise Applications** - SSO, RBAC, audit logging
- **Microservices** - Containerized, cloud-native deployment
- **Startups** - Production-ready foundation to build on

## ⭐ Star History

If you find this project helpful, please consider giving it a star!

## 🙏 Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) by Sebastián Ramírez
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [Pydantic](https://docs.pydantic.dev/)
- [Celery](https://docs.celeryq.dev/)
- And many other amazing open-source projects

---

**Built with ❤️ for the developer community**
