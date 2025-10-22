# 🚀 Deployment Checklist

## Critical Steps Before Testing

### ⚠️ REQUIRED: Generate Database Migrations

**The application will NOT work without migrations!**

```bash
# Create initial migration for all models
docker-compose up -d postgres redis
sleep 10

# Generate migration
docker-compose run --rm api alembic revision --autogenerate -m "Initial migration with all models"

# Apply migration
docker-compose exec api alembic upgrade head
```

### Complete Setup Steps

#### 1. Prerequisites Check

```bash
# Check Docker is installed and running
docker --version
docker-compose --version
docker info

# Check Python and UV
python --version  # Should be 3.12+
uv --version
```

#### 2. Initial Setup

```bash
# Clone repository
git clone <your-repo>
cd Python-fastapi-multiauth-uv

# Install dependencies
uv pip install -e ".[dev,cli]"

# Copy environment file
cp .env.example .env

# Review and update .env if needed
# IMPORTANT: Change SECRET_KEY in production!
```

#### 3. Start Services

```bash
# Start infrastructure services first
docker-compose up -d postgres redis minio

# Wait for services to be healthy
sleep 30

# Check services are running
docker-compose ps
```

#### 4. Generate and Run Migrations

```bash
# THIS STEP IS CRITICAL!
# Generate initial migration
docker-compose run --rm api alembic revision --autogenerate -m "Initial migration"

# Review the generated migration (optional but recommended)
ls -la alembic/versions/

# Apply migrations
docker-compose up -d api
docker-compose exec api alembic upgrade head

# Verify migrations
docker-compose exec postgres psql -U postgres saas_db -c "\dt"
```

#### 5. Start Application Services

```bash
# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f api

# Wait for startup (30 seconds)
sleep 30
```

#### 6. Verify Installation

```bash
# Check all services are running
docker-compose ps

# Test API
curl http://localhost:8000/health

# Test health checks
curl http://localhost:8000/api/v1/health/all

# Check metrics
curl http://localhost:8000/metrics

# Open API docs in browser
open http://localhost:8000/docs  # macOS
# or
xdg-open http://localhost:8000/docs  # Linux
```

#### 7. Run Tests

```bash
# Create test database
docker-compose exec postgres createdb -U postgres saas_backend_test

# Run E2E tests
pytest tests/e2e/ -v

# Or use test runner
./run_tests.sh
```

#### 8. Test CLI Tool

```bash
# Register user
python cli.py auth register

# Login
python cli.py auth login

# Test features
python cli.py auth me
python cli.py health check-all
python cli.py org create
```

---

## Post-Deployment Verification

### Check All Services

```bash
# API
curl http://localhost:8000/health
# Should return: {"status": "healthy"}

# Database
docker-compose exec postgres psql -U postgres saas_db -c "SELECT 1;"

# Redis
docker-compose exec redis redis-cli ping
# Should return: PONG

# MinIO
curl http://localhost:9000/minio/health/live
# Should return: OK

# Flower
curl http://localhost:5555/
# Should return: HTML page
```

### Check Database Tables

```bash
docker-compose exec postgres psql -U postgres saas_db -c "\dt"
```

**Expected tables:**
- users
- organizations
- organization_quotas
- usage_logs
- webhooks
- webhook_deliveries
- dead_letter_tasks
- password_reset_tokens
- email_verification_tokens
- files
- teams
- roles
- permissions
- role_permissions
- oauth_accounts
- api_keys
- audit_logs
- totp_secrets
- user_sessions
- notifications
- invitations
- feature_flags

### Test Critical Endpoints

```bash
# Health checks
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/health/all

# API documentation
curl http://localhost:8000/openapi.json

# Metrics
curl http://localhost:8000/metrics

# Register user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test123!","full_name":"Test User"}'
```

---

## Production Deployment

### Security Checklist

- [ ] Change `SECRET_KEY` to strong random value (min 32 chars)
- [ ] Change all default passwords (PostgreSQL, Redis, MinIO)
- [ ] Set `DEBUG=false`
- [ ] Set `APP_ENV=production`
- [ ] Use production database (AWS RDS, Google Cloud SQL, etc.)
- [ ] Use production Redis (AWS ElastiCache, Google Memorystore)
- [ ] Use production S3 (AWS S3, not MinIO)
- [ ] Configure proper CORS origins
- [ ] Set up TLS/SSL certificates
- [ ] Configure rate limiting appropriately
- [ ] Set up monitoring and alerting
- [ ] Configure email service (SendGrid, AWS SES)
- [ ] Set up backup strategy
- [ ] Configure OAuth providers with production credentials
- [ ] Review and adjust quota limits
- [ ] Set up log aggregation (ELK, CloudWatch)

### Traefik Deployment (Docker Only - Optional)

**For Docker-based production deployments only.** Traefik provides automatic SSL/TLS certificates and DNS-based routing.

> **Note:** For Kubernetes deployments, use **ingress-nginx** with **cert-manager** instead. See Kubernetes Deployment section below.

**Prerequisites:**
- Domain name pointing to your server
- Ports 80 and 443 accessible from the internet
- Valid email for Let's Encrypt

**Quick Setup:**

```bash
# 1. Configure domain
cp traefik/.env.example traefik/.env
nano traefik/.env  # Update DOMAIN and ACME_EMAIL

# 2. Update Traefik email
nano traefik/traefik.yml  # Update email in certificatesResolvers section

# 3. Configure DNS records
# api.yourdomain.com      → Your server IP
# traefik.yourdomain.com  → Your server IP
# minio.yourdomain.com    → Your server IP
# s3.yourdomain.com       → Your server IP

# 4. Start with Traefik
./scripts/start-traefik.sh
# OR manually:
docker-compose -f docker-compose.yml -f docker-compose.traefik.yml up -d
```

**Features:**
- ✅ Automatic SSL/TLS certificates from Let's Encrypt
- ✅ DNS-based routing (api.yourdomain.com, traefik.yourdomain.com, etc.)
- ✅ Built-in rate limiting and security headers
- ✅ Zero-downtime deployments with health checks
- ✅ Traefik dashboard for monitoring

**Access Services:**
- API: https://api.yourdomain.com
- API Docs: https://api.yourdomain.com/docs
- Traefik Dashboard: https://traefik.yourdomain.com (default: admin/changeme)

**Security:**
- [ ] Change Traefik dashboard password
- [ ] Restrict Traefik dashboard access by IP (optional)
- [ ] Review rate limiting settings
- [ ] Monitor certificate expiry (auto-renews 30 days before)

See [traefik/README.md](traefik/README.md) for complete guide.

### Environment Variables for Production

Update `.env` for production:

```env
# CRITICAL: Change these!
SECRET_KEY=<generate-random-32+-character-string>
DEBUG=false
APP_ENV=production

# Database (use managed service)
DATABASE_URL=postgresql+asyncpg://user:password@production-db-host:5432/production_db

# Redis (use managed service)
REDIS_URL=redis://production-redis-host:6379/0

# S3 (use AWS S3, not MinIO)
FILE_STORAGE_PROVIDER=s3
AWS_S3_BUCKET=production-bucket
AWS_ACCESS_KEY_ID=<your-aws-key>
AWS_SECRET_ACCESS_KEY=<your-aws-secret>
AWS_REGION=us-east-1
AWS_ENDPOINT_URL=  # Leave empty for AWS S3

# OAuth (production credentials)
GOOGLE_CLIENT_ID=<production-client-id>
GOOGLE_CLIENT_SECRET=<production-secret>
# ... other OAuth providers

# Rate Limiting
RATE_LIMIT_PER_MINUTE=30  # More restrictive

# CORS
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### Kubernetes Deployment

See:
- [k8s/README.md](k8s/README.md) - Direct Kubernetes manifests
- [helm/saas-backend/README.md](helm/saas-backend/README.md) - Helm chart deployment

---

## Troubleshooting

### Issue: No module named 'app'

```bash
# Ensure PYTHONPATH is set
export PYTHONPATH=/app

# Or reinstall package
uv pip install -e .
```

### Issue: Database connection failed

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check database exists
docker-compose exec postgres psql -U postgres -l

# Check connection string
echo $DATABASE_URL
```

### Issue: Migrations not applied

```bash
# Check migration status
docker-compose exec api alembic current

# Show migration history
docker-compose exec api alembic history

# Apply all migrations
docker-compose exec api alembic upgrade head
```

### Issue: Services not healthy

```bash
# Check logs
docker-compose logs api
docker-compose logs postgres
docker-compose logs redis
docker-compose logs celery_worker

# Restart services
docker-compose restart

# Full reset (CAREFUL: deletes data!)
docker-compose down -v
docker-compose up -d
```

### Issue: Import errors in tests

```bash
# Install test dependencies
uv pip install -e ".[dev,cli]"

# Check Python path
python -c "import sys; print('\n'.join(sys.path))"
```

---

## Quick Commands

```bash
# Start everything
docker-compose up -d && sleep 30

# Check status
docker-compose ps

# View logs
docker-compose logs -f api

# Run migrations
docker-compose exec api alembic upgrade head

# Access database
docker-compose exec postgres psql -U postgres saas_db

# Access Redis
docker-compose exec redis redis-cli

# Run tests
./run_tests.sh

# Stop everything
docker-compose down

# Stop and remove volumes (CAREFUL!)
docker-compose down -v
```

---

## Support URLs

When services are running:

- **API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **Health:** http://localhost:8000/health
- **Metrics:** http://localhost:8000/metrics
- **Adminer (DB UI):** http://localhost:8080
- **MinIO Console:** http://localhost:9001
- **Flower (Celery):** http://localhost:5555

---

## Ready to Go!

Once all checks pass:

✅ All services running
✅ Migrations applied
✅ Health checks passing
✅ Tests passing
✅ CLI tool working

**You're ready to integrate your frontend! 🚀**
