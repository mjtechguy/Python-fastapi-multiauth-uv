# Security Policy

## Supported Versions

Currently supported versions for security updates:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability, please follow these steps:

1. **Do NOT** open a public GitHub issue
2. Email security concerns to: [your-security-email]
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if available)

We will respond within 48 hours and work with you to address the issue.

## Security Features

### Authentication & Authorization
- JWT-based authentication with refresh tokens
- Multiple authentication strategies (local, OAuth2, Keycloak)
- Password strength validation
- Account lockout after failed attempts
- Role-Based Access Control (RBAC)

### Data Protection
- Bcrypt password hashing
- Secure token generation
- API key authentication
- Database connection encryption

### API Security
- Rate limiting
- CORS protection
- Security headers (X-Frame-Options, CSP, etc.)
- Input validation with Pydantic
- SQL injection protection via SQLAlchemy ORM

### Monitoring & Auditing
- Comprehensive audit logging
- Failed login attempt tracking
- Session management
- IP address logging

## Environment Variables & Secrets Management

### Critical Configuration Before Production

**⚠️ NEVER use default credentials in production!**

The following environment variables **MUST** be changed from their default values:

#### 1. Application Secret Key

Generate a secure random key:
```bash
# Using OpenSSL
openssl rand -hex 32

# Using Python
python -c "import secrets; print(secrets.token_hex(32))"
```

Update in `.env`:
```bash
SECRET_KEY=your-generated-secure-key-minimum-32-characters
```

#### 2. Database Credentials

```bash
POSTGRES_USER=secure_username
POSTGRES_PASSWORD=secure_random_password
POSTGRES_DB=your_database_name

# Update DATABASE_URL to match
DATABASE_URL=postgresql+asyncpg://secure_username:secure_random_password@postgres:5432/your_database_name
```

#### 3. MinIO/S3 Storage

```bash
MINIO_ROOT_USER=secure_minio_username
MINIO_ROOT_PASSWORD=secure_minio_password

# Must match MinIO credentials
AWS_ACCESS_KEY_ID=secure_minio_username
AWS_SECRET_ACCESS_KEY=secure_minio_password
```

### Environment Files

| File | Purpose | Git Tracked | Required |
|------|---------|-------------|----------|
| `.env.example` | Template with placeholders | ✅ Yes | No (reference) |
| `.env` | Active configuration | ❌ No | Yes |
| `.env.local` | Local overrides | ❌ No | Optional |
| `.env.production` | Production secrets | ❌ No | Yes (prod) |

**The `.env` file is already in `.gitignore`.** Always verify before committing.

### Docker Compose Configuration

The `docker-compose.yml` now uses environment variables with safe defaults for development:

```yaml
environment:
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
  SECRET_KEY: ${SECRET_KEY}
```

- Variables with `:-` syntax provide development defaults
- Variables without defaults (like `SECRET_KEY`) must be set in `.env`
- Production should override all defaults with secure values

## Security Best Practices

### For Deployment
1. **Change all default passwords** - See environment variables section above
2. Use strong `SECRET_KEY` (minimum 32 characters)
3. Enable HTTPS/TLS in production
4. Set `APP_ENV=production`
5. Configure proper CORS origins (never use `*` in production)
6. Use environment variables for secrets
7. Enable rate limiting
8. Regular security updates
9. Database backups
10. Monitor audit logs
11. Implement network segmentation

### For Development
1. Never commit secrets to version control
2. Use `.env.example` for documentation only
3. Run security scans regularly
4. Keep dependencies updated
5. Follow principle of least privilege
6. Review code for security issues
7. Use type checking and linting

## Dependency Security

We use:
- `safety` for known vulnerability scanning
- `bandit` for code security analysis
- Automated CI/CD security checks
- Regular dependency updates

Run security checks:
```bash
make security
```

## Compliance

This framework is designed to support:
- GDPR compliance (data protection)
- SOC 2 requirements (audit logging)
- HIPAA considerations (data encryption)
- PCI DSS guidelines (secure authentication)

## Security Updates

Security patches will be released as soon as possible after verification. Subscribe to releases for notifications.
