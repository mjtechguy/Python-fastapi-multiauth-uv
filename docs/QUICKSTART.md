# ⚡ Quick Start Guide

**Get your SaaS backend running in 5 minutes!**

---

## 🎯 One-Command Startup

```bash
./scripts/start.sh
```

That's it! The script will:
✅ Check Docker is running
✅ Create `.env` from template
✅ Start all services
✅ Generate database migrations
✅ Apply migrations
✅ Verify everything is working

---

## 🔐 Production Startup with Traefik (SSL/TLS)

For production deployments with automatic SSL certificates and domain routing:

```bash
./scripts/start-traefik.sh
```

**Before running, configure:**

1. **Set your domain:**
   ```bash
   cp traefik/.env.example traefik/.env
   nano traefik/.env  # Update DOMAIN and ACME_EMAIL
   ```

2. **Update Traefik config:**
   ```bash
   nano traefik/traefik.yml  # Update email in certificatesResolvers
   ```

3. **Configure DNS:**
   - `api.yourdomain.com` → Your server IP
   - `traefik.yourdomain.com` → Your server IP
   - `minio.yourdomain.com` → Your server IP
   - `s3.yourdomain.com` → Your server IP

4. **Run the script** and access via HTTPS:
   - API: https://api.yourdomain.com
   - API Docs: https://api.yourdomain.com/docs
   - Traefik Dashboard: https://traefik.yourdomain.com

See [traefik/README.md](../traefik/README.md) for complete guide.

---

## 📋 Manual Setup (If You Prefer)

### Step 1: Prerequisites

```bash
# Check Docker
docker --version

# Check Python
python --version  # 3.12+

# Install UV (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Step 2: Install Dependencies

```bash
# Install Python dependencies
uv pip install -e ".[dev,cli]"
```

### Step 3: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# (Optional) Edit .env
# For development, defaults are fine!
# For production, change SECRET_KEY and database URLs
```

### Step 4: Start Services

```bash
# Start infrastructure (PostgreSQL, Redis, MinIO)
docker-compose up -d postgres redis minio

# Wait for services to be ready
sleep 30
```

### Step 5: Initialize Database

```bash
# CRITICAL: Generate migrations for all models
docker-compose up -d api
docker-compose exec api alembic revision --autogenerate -m "Initial migration"

# Apply migrations
docker-compose exec api alembic upgrade head

# Verify tables were created
docker-compose exec postgres psql -U postgres saas_db -c "\dt"
```

### Step 6: Start All Services

```bash
# Start everything
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f api
```

### Step 7: Verify

```bash
# Test API
curl http://localhost:8000/health
# Should return: {"status":"healthy"}

# Check all services
curl http://localhost:8000/api/v1/health/all

# Open API docs in browser
open http://localhost:8000/docs  # macOS
xdg-open http://localhost:8000/docs  # Linux
```

---

## 🧪 Run Tests

### E2E Test Suite

```bash
# Create test database
docker-compose exec postgres createdb -U postgres saas_backend_test

# Run all tests
pytest tests/e2e/ -v

# Run with coverage
pytest tests/e2e/ --cov=app --cov-report=html

# Or use test runner
./run_tests.sh
```

### CLI Testing Tool

```bash
# Register user
python cli.py auth register

# Login
python cli.py auth login

# Test features
python cli.py auth me
python cli.py health check-all
python cli.py org create
python cli.py webhooks events
python cli.py quota status
```

---

## 🎯 Access Points

Once running, access these URLs:

| Service | URL | Credentials |
|---------|-----|-------------|
| **API** | http://localhost:8000 | - |
| **API Docs** | http://localhost:8000/docs | - |
| **Health Check** | http://localhost:8000/health | - |
| **Metrics** | http://localhost:8000/metrics | - |
| **Adminer (DB)** | http://localhost:8080 | System: PostgreSQL<br>Server: postgres<br>User: postgres<br>Password: postgres<br>Database: saas_db |
| **MinIO Console** | http://localhost:9001 | User: minioadmin<br>Password: minioadmin |
| **Flower (Celery)** | http://localhost:5555 | - |

---

## 🔍 Verify Everything Works

### 1. Check Services

```bash
docker-compose ps
```

All services should show "Up" status.

### 2. Test API

```bash
# Basic health
curl http://localhost:8000/health

# Detailed health
curl http://localhost:8000/api/v1/health/all | jq

# API documentation
curl http://localhost:8000/openapi.json | jq .info
```

### 3. Test Database

```bash
# Connect to database
docker-compose exec postgres psql -U postgres saas_db

# List tables
\dt

# Check a table
SELECT * FROM users LIMIT 1;

# Exit
\q
```

### 4. Test Redis

```bash
# Connect to Redis
docker-compose exec redis redis-cli

# Test commands
PING
# Should return: PONG

SET test "hello"
GET test
# Should return: "hello"

# Exit
exit
```

### 5. Test Storage

```bash
# MinIO is accessible at http://localhost:9001
# Login with: minioadmin / minioadmin
# Check bucket "saas-uploads" exists
```

### 6. Test Celery

```bash
# Check Flower dashboard
open http://localhost:5555

# Or check worker status
docker-compose exec celery_worker celery -A app.tasks.celery_app status
```

---

## 🚦 Troubleshooting

### Services won't start

```bash
# Check Docker is running
docker info

# Check logs
docker-compose logs api
docker-compose logs postgres

# Restart everything
docker-compose restart
```

### Database connection errors

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check database exists
docker-compose exec postgres psql -U postgres -l | grep saas_db

# Recreate database (WARNING: deletes data)
docker-compose exec postgres dropdb -U postgres saas_db --if-exists
docker-compose exec postgres createdb -U postgres saas_db
docker-compose exec api alembic upgrade head
```

### No migrations found

```bash
# Generate migrations
docker-compose exec api alembic revision --autogenerate -m "Initial migration"

# Apply migrations
docker-compose exec api alembic upgrade head

# Check migration status
docker-compose exec api alembic current
```

### Import errors

```bash
# Reinstall dependencies
uv pip install -e ".[dev,cli]"

# Check Python path
python -c "import sys; print(sys.path)"

# Test imports
python -c "from app.main import app; print('OK')"
```

### Port already in use

```bash
# Check what's using port 8000
lsof -i :8000
# or
netstat -an | grep 8000

# Stop other services or change port in docker-compose.yml
```

### Full reset

```bash
# Stop everything
docker-compose down

# Remove volumes (WARNING: deletes all data!)
docker-compose down -v

# Start fresh
./scripts/start.sh
```

---

## 📚 Next Steps

### 1. Read Documentation

- **[TESTING.md](TESTING.md)** - Complete testing guide
- **[CLI_REFERENCE.md](CLI_REFERENCE.md)** - CLI command reference
- **[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)** - Production deployment
- **[README.md](../README.md)** - Full documentation

### 2. Try Example Workflows

```bash
# Complete user flow
python cli.py auth register --email test@example.com --password "Test123!" --name "Test User"
python cli.py auth login --email test@example.com --password "Test123!"
python cli.py auth me

# Organization and quotas
python cli.py org create --name "My Startup" --slug "my-startup"
python cli.py quota status

# File uploads
echo "Test content" > test.txt
python cli.py files upload test.txt
python cli.py files list

# Webhooks
python cli.py webhooks events
python cli.py webhooks create
python cli.py webhooks list

# Monitoring
python cli.py health check-all
python cli.py sessions list
python cli.py dlq stats
```

### 3. Run Test Suite

```bash
# Full test suite
./run_tests.sh

# Or pytest directly
pytest tests/e2e/ -v --cov=app
```

### 4. Explore API

```bash
# Open Swagger UI
open http://localhost:8000/docs

# Try endpoints interactively
# All endpoints are documented with examples
```

### 5. Check Logs

```bash
# Follow API logs
docker-compose logs -f api

# Check worker logs
docker-compose logs -f celery_worker

# Check all logs
docker-compose logs -f
```

---

## ✅ Ready for Frontend Integration

Once you verify:
- ✅ All services running (`docker-compose ps`)
- ✅ Health checks passing (`curl http://localhost:8000/api/v1/health/all`)
- ✅ Tests passing (`./run_tests.sh`)
- ✅ CLI working (`python cli.py auth register`)

**You're ready to integrate your frontend!** 🎉

---

## 🆘 Need Help?

- **Documentation:** [docs/](docs/)
- **API Docs:** http://localhost:8000/docs
- **Issues:** Check logs with `docker-compose logs -f`
- **Full Reset:** `docker-compose down -v && ./scripts/start.sh`

---

**Happy Building! 🚀**
