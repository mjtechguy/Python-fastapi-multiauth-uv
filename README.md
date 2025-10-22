# SaaS Backend Framework

A production-grade, scalable FastAPI backend framework designed for enterprise SaaS applications with comprehensive authentication, authorization, and multi-tenancy support.

## Features

### Core Features
- **FastAPI** - Modern, fast web framework with automatic API documentation
- **UV Package Manager** - Ultra-fast Python package management
- **PostgreSQL** - Robust relational database with async support
- **Redis** - High-performance caching and message broker
- **Celery + Flower** - Distributed task queue with monitoring

### Authentication & Authorization
- **Multiple Auth Strategies**:
  - Local email/password authentication
  - OAuth2 (Google, GitHub, Microsoft)
  - Keycloak integration
  - API key authentication
- **JWT Tokens** - Secure access and refresh tokens
- **Password Security** - Bcrypt hashing with strength validation
- **Account Security** - Failed login tracking and account lockout

### RBAC (Role-Based Access Control)
- Fine-grained permissions system
- Dynamic role creation and assignment
- Organization and team-scoped permissions
- System-defined and custom roles

### Multi-Tenancy
- **Organizations** - Top-level tenant isolation
- **Teams** - Sub-groups within organizations
- **Member Management** - User-organization-team relationships
- **Scoped Resources** - Data isolation per tenant

### Security
- Security headers middleware
- Rate limiting
- CORS configuration
- Audit logging
- Password policies
- Session management

### Developer Experience
- **Type Safety** - Full type hints with Mypy
- **Code Quality** - Black, Ruff linting
- **Testing** - Pytest with async support
- **Database Migrations** - Alembic
- **API Documentation** - Auto-generated OpenAPI/Swagger docs
- **Docker Support** - Complete containerization

### Integrations
- **OpenAI API** - LLM provider abstraction supporting OpenAI and compatible endpoints
- **Email** - Async email sending with Celery
- **PyPI Version Checking** - Automated dependency updates monitoring

## Quick Start

### Prerequisites
- Python 3.12+
- PostgreSQL 16+
- Redis 7+
- UV package manager

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd Python-fastapi-multiauth-uv
```

2. **Install UV**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. **Install dependencies**
```bash
make dev-install
# or
uv pip install -r pyproject.toml --extra dev
```

4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Start services with Docker**
```bash
make docker-up
# or
docker-compose up -d
```

6. **Run database migrations**
```bash
make migrate
# or
alembic upgrade head
```

7. **Run the application**
```bash
make run
# or
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

- **API Documentation**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **Flower (Celery Monitor)**: `http://localhost:5555`

## Project Structure

```
.
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── dependencies/    # Dependency injection
│   │       └── endpoints/       # API routes
│   ├── core/                    # Core configuration
│   ├── db/                      # Database configuration
│   ├── middleware/              # Custom middleware
│   ├── models/                  # SQLAlchemy models
│   ├── schemas/                 # Pydantic schemas
│   ├── services/                # Business logic
│   ├── tasks/                   # Celery tasks
│   ├── utils/                   # Utilities
│   └── main.py                  # Application entry point
├── alembic/                     # Database migrations
├── tests/                       # Test suite
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   └── e2e/                     # End-to-end tests
├── scripts/                     # Utility scripts
├── docker-compose.yml           # Docker orchestration
├── Dockerfile                   # Container definition
├── pyproject.toml              # Project dependencies
└── Makefile                    # Development commands
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login with credentials
- `POST /api/v1/auth/refresh` - Refresh access token
- `GET /api/v1/auth/me` - Get current user
- `GET /api/v1/auth/oauth/{provider}/authorize` - OAuth authorization
- `POST /api/v1/auth/oauth/{provider}/callback` - OAuth callback
- `POST /api/v1/auth/keycloak/callback` - Keycloak authentication

### Users
- `GET /api/v1/users/me` - Get current user profile
- `PUT /api/v1/users/me` - Update current user
- `PUT /api/v1/users/me/password` - Change password
- `GET /api/v1/users` - List users (admin)
- `GET /api/v1/users/{user_id}` - Get user by ID
- `DELETE /api/v1/users/{user_id}` - Delete user (admin)

### Organizations
- `POST /api/v1/organizations` - Create organization
- `GET /api/v1/organizations` - List user's organizations
- `GET /api/v1/organizations/{org_id}` - Get organization
- `PUT /api/v1/organizations/{org_id}` - Update organization
- `DELETE /api/v1/organizations/{org_id}` - Delete organization
- `POST /api/v1/organizations/{org_id}/members` - Add member
- `DELETE /api/v1/organizations/{org_id}/members` - Remove member

### Health
- `GET /health` - Basic health check
- `GET /api/v1/health` - Detailed health check
- `GET /api/v1/health/db` - Database health check

## Development

### Running Tests
```bash
make test
# or
pytest tests/ -v --cov=app
```

### Code Formatting
```bash
make format
# or
black app/ tests/
ruff check --fix app/ tests/
```

### Linting
```bash
make lint
# or
ruff check app/ tests/
mypy app/
```

### Security Checks
```bash
make security
# or
bandit -r app/ -ll
safety check
```

### Database Migrations

Create a new migration:
```bash
make revision message="Add new table"
# or
alembic revision --autogenerate -m "Add new table"
```

Apply migrations:
```bash
make migrate
# or
alembic upgrade head
```

## Configuration

### Environment Variables

Key environment variables (see `.env.example` for complete list):

```env
# Application
APP_NAME=SaaS Backend Framework
APP_ENV=development
SECRET_KEY=your-secret-key-min-32-chars

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/2

# OAuth Providers
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret

# OpenAI
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=gpt-4-turbo-preview
```

## Deployment

### Docker Deployment

1. Build the image:
```bash
docker build -t saas-backend .
```

2. Run with docker-compose:
```bash
docker-compose up -d
```

### Production Checklist

- [ ] Set strong `SECRET_KEY`
- [ ] Configure production database
- [ ] Set up SSL/TLS certificates
- [ ] Configure proper CORS origins
- [ ] Set up monitoring (Sentry, etc.)
- [ ] Configure email service
- [ ] Set up backup strategy
- [ ] Configure rate limiting
- [ ] Review security headers
- [ ] Set up logging aggregation
- [ ] Configure OAuth providers
- [ ] Set environment to `production`

## Architecture

### Database Models

- **User** - User accounts with multi-auth support
- **Organization** - Top-level tenants
- **Team** - Sub-groups within organizations
- **Role** - Permission groups
- **Permission** - Fine-grained access control
- **OAuthAccount** - Social authentication linkage
- **APIKey** - Programmatic access tokens
- **AuditLog** - Security and compliance logging

### Service Layer

- **UserService** - User management operations
- **AuthService** - Authentication strategies
- **RBACService** - Role and permission management
- **OrganizationService** - Multi-tenancy operations
- **LLMService** - AI/LLM integration

### Background Tasks

- **Email Tasks** - Verification, password reset, notifications
- **PyPI Check** - Dependency version monitoring
- **Custom Tasks** - Extensible task system

## Security Features

1. **Password Security**
   - Bcrypt hashing with configurable rounds
   - Strength validation (length, complexity)
   - Password history (optional)

2. **Account Protection**
   - Failed login attempt tracking
   - Automatic account lockout
   - Session timeout

3. **API Security**
   - JWT token authentication
   - API key support
   - Rate limiting
   - CORS protection

4. **Headers**
   - X-Content-Type-Options
   - X-Frame-Options
   - X-XSS-Protection
   - Strict-Transport-Security
   - Referrer-Policy

5. **Audit Logging**
   - All sensitive operations logged
   - IP address and user agent tracking
   - Compliance-ready

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
- GitHub Issues: [Create an issue]
- Documentation: See `/docs` directory
- API Docs: `http://localhost:8000/docs`

## Roadmap

- [ ] GraphQL API support
- [ ] WebSocket real-time features
- [ ] Advanced analytics
- [ ] Multi-factor authentication
- [ ] SSO integration
- [ ] Advanced audit reporting
- [ ] API versioning strategies
- [ ] Kubernetes deployment configs
- [ ] Performance monitoring integration
- [ ] Advanced caching strategies
