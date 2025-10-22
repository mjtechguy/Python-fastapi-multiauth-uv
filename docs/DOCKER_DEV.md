# Docker Development Guide

## 🚀 Quick Start

### Start Development Environment

```bash
# Start all services with hot reload
docker-compose up -d

# View logs
docker-compose logs -f api

# View specific service logs
docker-compose logs -f celery_worker
```

**That's it!** All your code changes will be instantly reflected thanks to:
- ✅ Volume mounting (`.:/app`)
- ✅ Uvicorn hot reload (`--reload` flag)
- ✅ Celery auto-reload (via `watchfiles`)

## 📝 How Live Reload Works

### API Service (FastAPI)

The API container automatically reloads when you edit Python files:

```yaml
volumes:
  - .:/app              # Mount your code into container
command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level debug
```

**What gets reloaded:**
- ✅ API endpoints (`app/api/`)
- ✅ Services (`app/services/`)
- ✅ Models (`app/models/`)
- ✅ Middleware (`app/middleware/`)
- ✅ Configuration (`app/core/`)

**What doesn't reload (requires restart):**
- ❌ Environment variables
- ❌ Dependency changes (`pyproject.toml`)
- ❌ Dockerfile changes

### Celery Workers

Celery workers use `watchfiles` to auto-reload on code changes:

```yaml
command: watchfiles "celery -A app.tasks.celery_app worker --loglevel=debug" app/
```

This watches the `app/` directory and restarts Celery when files change.

## 🔄 Common Development Tasks

### Edit Code

```bash
# 1. Edit any Python file
vim app/api/v1/endpoints/users.py

# 2. Save the file

# 3. Check logs to see reload
docker-compose logs -f api
# Output: INFO:     Application startup complete.
```

### Add New Dependencies

```bash
# 1. Edit pyproject.toml
echo 'new-package>=1.0.0' >> pyproject.toml

# 2. Rebuild containers
docker-compose build api celery_worker

# 3. Restart services
docker-compose up -d
```

### Run Database Migrations

```bash
# Create migration
docker-compose exec api alembic revision --autogenerate -m "Add new field"

# Apply migration
docker-compose exec api alembic upgrade head

# Rollback
docker-compose exec api alembic downgrade -1
```

### Access Services

```bash
# API Shell
docker-compose exec api python

# Database Shell
docker-compose exec postgres psql -U postgres -d saas_db

# Redis CLI
docker-compose exec redis redis-cli

# Check Celery Tasks
docker-compose exec celery_worker celery -A app.tasks.celery_app inspect active
```

### View Service UIs

- **API Docs**: http://localhost:8000/docs
- **Adminer (DB UI)**: http://localhost:8080
- **MinIO Console**: http://localhost:9001
- **Flower (Celery)**: http://localhost:5555
- **Prometheus Metrics**: http://localhost:8000/metrics

## 🐛 Debugging

### Debug Mode

Enable more verbose logging:

```bash
# Already enabled in docker-compose.override.yml
LOG_LEVEL=debug
```

### Interactive Debugging

Add breakpoints using `pdb`:

```python
# In your code
import pdb; pdb.set_trace()
```

Then attach to the container:

```bash
docker-compose exec api python -m pdb
```

### Check Service Health

```bash
# API health
curl http://localhost:8000/health

# Database health
docker-compose exec api curl http://localhost:8000/api/v1/health/db

# All services health
curl http://localhost:8000/api/v1/health/all
```

## 🔧 Troubleshooting

### Port Already in Use

```bash
# Find what's using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or change port in docker-compose.yml
ports:
  - "8001:8000"  # Use 8001 instead
```

### Hot Reload Not Working

```bash
# 1. Check volume mount
docker-compose exec api ls -la /app
# Should show your source files

# 2. Check reload flag
docker-compose exec api ps aux | grep uvicorn
# Should show --reload flag

# 3. Restart container
docker-compose restart api
```

### Code Changes Not Reflecting

```bash
# Check if file is excluded in .dockerignore
cat .dockerignore

# Ensure you're editing the right file (not inside container)
docker-compose exec api cat app/main.py
# Compare with your local file
```

### Dependencies Not Found

```bash
# Rebuild with dev dependencies
docker-compose build --no-cache api celery_worker

# Verify installation
docker-compose exec api pip list | grep <package-name>
```

## 📦 File Sync Behavior

### What Syncs Instantly:
- ✅ Python files (`.py`)
- ✅ Templates (`.html`, `.jinja2`)
- ✅ Static files (`.css`, `.js`)
- ✅ Configuration files (`.yaml`, `.json`)

### What Requires Rebuild:
- ❌ `Dockerfile` changes
- ❌ `pyproject.toml` dependency changes
- ❌ System packages
- ❌ `.dockerignore` changes

### What Requires Restart:
- ⚠️ `.env` file changes
- ⚠️ `docker-compose.yml` changes
- ⚠️ Database migrations (need to run manually)

## 🎯 Performance Tips

### Fast Container Startup

Use the dev Dockerfile which includes dev dependencies:

```bash
# Already configured in docker-compose.override.yml
dockerfile: Dockerfile.dev
```

### Reduce Rebuild Time

Cache dependencies by copying `pyproject.toml` first:

```dockerfile
# Already done in Dockerfile.dev
COPY pyproject.toml ./
RUN uv pip install --system --no-cache -r pyproject.toml --extra dev
```

### Volume Exclusions

Exclude cache directories to avoid conflicts:

```yaml
volumes:
  - .:/app
  - /app/.venv           # Exclude venv
  - /app/__pycache__     # Exclude cache
  - /app/.pytest_cache   # Exclude pytest cache
```

## 🔒 Security Notes

### Dev vs Production

The development setup is **NOT** for production:

| Feature | Dev | Production |
|---------|-----|------------|
| Debug mode | ✅ Enabled | ❌ Disabled |
| Auto-reload | ✅ Enabled | ❌ Disabled |
| Log level | DEBUG | INFO/WARNING |
| Root user | ✅ Sometimes | ❌ Never |
| Secrets | Hard-coded | Environment/Vault |

### Dev Secrets

The `docker-compose.yml` includes dev secrets:

```env
SECRET_KEY=dev-secret-key-change-in-production-min-32-characters-long
```

**Never use these in production!**

## 🚦 Best Practices

### 1. Use docker-compose.override.yml

This file is automatically loaded and contains dev-specific overrides:

```yaml
# docker-compose.override.yml
services:
  api:
    command: uvicorn app.main:app --reload --log-level debug
```

### 2. Keep Data Persistent

Use named volumes for databases:

```yaml
volumes:
  postgres_data:  # Survives container deletion
  redis_data:
  minio_data:
```

### 3. Clean Up Regularly

```bash
# Remove stopped containers
docker-compose down

# Remove volumes (DELETES DATA!)
docker-compose down -v

# Remove images
docker-compose down --rmi all

# Clean everything
docker system prune -a --volumes
```

### 4. Use .dockerignore

Keep the image small:

```
.git
.venv
__pycache__
*.pyc
.pytest_cache
node_modules
```

## 📚 Additional Resources

- [Docker Compose Docs](https://docs.docker.com/compose/)
- [FastAPI Development](https://fastapi.tiangolo.com/tutorial/)
- [Uvicorn Auto-reload](https://www.uvicorn.org/settings/#development)
- [Watchfiles Documentation](https://watchfiles.helpmanual.io/)

## ❓ FAQ

**Q: Do I need to rebuild after every code change?**
A: No! Hot reload handles Python code changes automatically.

**Q: Can I use a debugger?**
A: Yes! Use `pdb` or attach your IDE's debugger to the container.

**Q: Why is the first startup slow?**
A: Initial image build and dependency installation. Subsequent starts are fast.

**Q: Can I develop without Docker?**
A: Yes! See [Local Development Guide](QUICKSTART.md#option-2-local-development).

**Q: How do I test production builds locally?**
A: Use the production Dockerfile: `docker build -f Dockerfile -t myapp .`
