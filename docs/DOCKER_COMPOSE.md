# Docker Compose Setup

Complete development environment with all required services.

## Services Included

### Core Application Services

1. **API** - FastAPI application server
   - Port: `8000`
   - Endpoint: http://localhost:8000
   - Docs: http://localhost:8000/docs

2. **Celery Worker** - Background task processor
   - Processes async tasks (email, file processing, etc.)

3. **Celery Beat** - Task scheduler
   - Runs periodic tasks (PyPI version checks, cleanup, etc.)

4. **Flower** - Celery monitoring dashboard
   - Port: `5555`
   - Dashboard: http://localhost:5555

### Infrastructure Services

5. **PostgreSQL** - Primary database
   - Port: `5432`
   - Database: `saas_db` (from `.env`)
   - User: `postgres` (from `.env`)
   - Password: Configured in `.env` (default: `postgres`)

6. **Adminer** - Database management UI
   - Port: `8080`
   - URL: http://localhost:8080
   - System: PostgreSQL
   - Server: `postgres`
   - Username: From `POSTGRES_USER` in `.env`
   - Password: From `POSTGRES_PASSWORD` in `.env`
   - Database: From `POSTGRES_DB` in `.env`

7. **Redis** - Cache and message broker
   - Port: `6379`
   - Used for: Caching, Celery broker, session storage

8. **MinIO** - S3-compatible object storage
   - API Port: `9000` (configurable via `MINIO_API_PORT` in `.env`)
   - Console Port: `9001` (configurable via `MINIO_CONSOLE_PORT` in `.env`)
   - Console: http://localhost:9001
   - Access Key: From `MINIO_ROOT_USER` in `.env` (default: `minioadmin`)
   - Secret Key: From `MINIO_ROOT_PASSWORD` in `.env` (default: `minioadmin`)
   - Bucket: From `AWS_S3_BUCKET` in `.env` (default: `saas-uploads`, auto-created)

## Quick Start

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 4GB RAM minimum
- 10GB disk space

### Environment Configuration

**IMPORTANT: Security First!**

Before starting the services, you **must** configure environment variables:

1. **Copy the example environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Update critical security values in `.env`:**
   - `SECRET_KEY` - **MUST** be changed to a secure random string (min 32 characters)
   - `POSTGRES_PASSWORD` - Change from default `postgres`
   - `MINIO_ROOT_PASSWORD` - Change from default `minioadmin`
   - `AWS_SECRET_ACCESS_KEY` - Should match `MINIO_ROOT_PASSWORD`

3. **Generate a secure SECRET_KEY:**
   ```bash
   # Linux/macOS
   openssl rand -hex 32

   # Or Python
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

**Note:** The `.env` file is already in `.gitignore` to prevent accidental commits. Never commit credentials to version control.

### Start All Services

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f api
docker-compose logs -f celery_worker
```

### Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (⚠️ deletes all data)
docker-compose down -v
```

## Initial Setup

### 1. Wait for Services to Start

```bash
# Check service health
docker-compose ps

# All services should show "healthy" or "running"
```

### 2. Run Database Migrations

```bash
# Run Alembic migrations
docker-compose exec api alembic upgrade head
```

### 3. Create Initial Admin User (Optional)

```bash
# Access API container
docker-compose exec api python

# In Python shell:
from app.db.session import SessionLocal
from app.services.auth import AuthService
import asyncio

async def create_admin():
    async with SessionLocal() as db:
        user = await AuthService.register(
            db=db,
            email="admin@example.com",
            password="Admin123!",
            username="admin"
        )
        user.is_superuser = True
        await db.commit()
        print(f"Admin user created: {user.email}")

asyncio.run(create_admin())
```

## Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| API Documentation | http://localhost:8000/docs | - |
| API Health Check | http://localhost:8000/health | - |
| Adminer (DB UI) | http://localhost:8080 | postgres / postgres |
| MinIO Console | http://localhost:9001 | minioadmin / minioadmin |
| Flower (Tasks) | http://localhost:5555 | - |

## Configuration

### Environment Variables

All services are pre-configured in `docker-compose.yml`. Key configurations:

- **File Storage**: MinIO (S3-compatible)
- **Max File Size**: 50MB (configurable via `MAX_FILE_SIZE_MB`)
- **Database**: PostgreSQL with 20 connection pool
- **Redis**: 4 databases (0=cache, 1=cache-db, 2=broker, 3=results)

### File Storage Setup

Files are automatically stored in MinIO:
- **Bucket**: `saas-uploads` (auto-created)
- **Endpoint**: http://minio:9000
- **Access**: Via presigned URLs

To access MinIO console:
1. Open http://localhost:9001
2. Login: `minioadmin` / `minioadmin`
3. View uploaded files in `saas-uploads` bucket

### Changing File Storage Provider

To use local filesystem instead of MinIO:

```bash
# Edit docker-compose.yml
# Change this environment variable in the 'api' service:
- FILE_STORAGE_PROVIDER=local

# Restart API
docker-compose restart api
```

## Development Workflow

### Making Code Changes

Code changes are automatically reloaded (hot reload enabled):

```bash
# API restarts automatically on code changes
# Watch logs to see reload
docker-compose logs -f api
```

### Running Tests

```bash
# Run all tests
docker-compose exec api pytest

# Run with coverage
docker-compose exec api pytest --cov=app

# Run specific test file
docker-compose exec api pytest tests/unit/test_security.py
```

### Database Operations

```bash
# Create new migration
docker-compose exec api alembic revision --autogenerate -m "description"

# Apply migrations
docker-compose exec api alembic upgrade head

# Rollback migration
docker-compose exec api alembic downgrade -1

# View migration history
docker-compose exec api alembic history
```

### Celery Tasks

```bash
# View active tasks in Flower
open http://localhost:5555

# Check worker status
docker-compose exec celery_worker celery -A app.tasks.celery_app inspect active

# Monitor task execution
docker-compose logs -f celery_worker
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose logs <service-name>

# Rebuild service
docker-compose build <service-name>
docker-compose up -d <service-name>
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Test connection
docker-compose exec postgres psql -U postgres -d saas_db -c "SELECT 1;"

# View PostgreSQL logs
docker-compose logs postgres
```

### Redis Connection Issues

```bash
# Check Redis is running
docker-compose ps redis

# Test connection
docker-compose exec redis redis-cli ping
# Should return: PONG
```

### MinIO Issues

```bash
# Check MinIO is running
docker-compose ps minio

# View MinIO logs
docker-compose logs minio

# Recreate bucket
docker-compose exec minio_client mc mb myminio/saas-uploads --ignore-existing
```

### Port Conflicts

If ports are already in use:

```bash
# Check what's using the port
lsof -i :8000  # or :5432, :6379, etc.

# Change port in docker-compose.yml
# For example, change API port:
ports:
  - "8001:8000"  # Changed from 8000:8000
```

### Container Out of Memory

```bash
# Increase Docker memory limit
# Docker Desktop: Settings > Resources > Memory

# Or reduce service resource usage in docker-compose.yml
```

### Clear All Data and Restart Fresh

```bash
# ⚠️ This deletes all data
docker-compose down -v
docker-compose up -d

# Re-run migrations
docker-compose exec api alembic upgrade head
```

## Production Considerations

**⚠️ This docker-compose setup is for development only.**

For production:

1. **Don't use docker-compose** - Use Kubernetes with Helm charts (see `helm/` directory)
2. **Use managed services**:
   - AWS RDS for PostgreSQL
   - AWS ElastiCache for Redis
   - AWS S3 for file storage
3. **Secure credentials** - Use secrets management (AWS Secrets Manager, HashiCorp Vault)
4. **Enable TLS** - Use HTTPS with valid certificates
5. **Configure monitoring** - Set up logging and alerting
6. **Set up backups** - Automated database and file backups
7. **Use production SECRET_KEY** - Generate secure random key
8. **Disable DEBUG mode** - Set `DEBUG=false`

## Advanced Usage

### Custom Network

All services communicate via `saas_network` bridge network:

```bash
# Inspect network
docker network inspect python-fastapi-multiauth-uv_saas_network

# Connect external container
docker run --network python-fastapi-multiauth-uv_saas_network -it alpine sh
```

### Volume Management

```bash
# List volumes
docker volume ls | grep saas

# Inspect volume
docker volume inspect python-fastapi-multiauth-uv_postgres_data

# Backup PostgreSQL volume
docker run --rm -v python-fastapi-multiauth-uv_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres-backup.tar.gz /data

# Restore PostgreSQL volume
docker run --rm -v python-fastapi-multiauth-uv_postgres_data:/data -v $(pwd):/backup alpine tar xzf /backup/postgres-backup.tar.gz -C /
```

### Scaling Workers

```bash
# Scale Celery workers
docker-compose up -d --scale celery_worker=3

# Check scaled workers
docker-compose ps celery_worker
```

### Resource Monitoring

```bash
# Monitor resource usage
docker stats

# Monitor specific services
docker stats saas_api saas_celery_worker saas_postgres
```

## Integration with Frontend

### CORS Configuration

Default CORS origins: `http://localhost:3000,http://localhost:8000`

To add more origins:

```bash
# Edit docker-compose.yml
# Update CORS_ORIGINS in api service:
- CORS_ORIGINS=http://localhost:3000,http://localhost:8000,http://localhost:5173
```

### API Testing

```bash
# Health check
curl http://localhost:8000/health

# Register user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!",
    "username": "testuser"
  }'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!"
  }'
```

## Cleaning Up

### Remove Specific Services

```bash
# Stop specific service
docker-compose stop api
docker-compose rm api

# Rebuild and restart
docker-compose up -d api
```

### Remove Images

```bash
# Remove built images
docker-compose down --rmi local

# Remove all images (including base images)
docker-compose down --rmi all
```

### Complete Cleanup

```bash
# Stop and remove everything
docker-compose down -v --rmi all

# Remove orphaned volumes
docker volume prune

# Remove orphaned networks
docker network prune
```

## Support

For issues or questions:
- Check logs: `docker-compose logs -f`
- GitHub Issues: https://github.com/yourusername/saas-backend/issues
- Documentation: See main README.md

## Related Documentation

- [Kubernetes Deployment](k8s/README.md)
- [Helm Charts](helm/saas-backend/README.md)
- [API Documentation](http://localhost:8000/docs)
- [Architecture](docs/ARCHITECTURE.md)
