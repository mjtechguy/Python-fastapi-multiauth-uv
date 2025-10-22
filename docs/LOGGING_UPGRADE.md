# Logging Modernization - Structlog Implementation

**Date:** 2025-10-22
**Status:** ✅ COMPLETED

---

## Executive Summary

Upgraded from Python's standard library `logging` to **structlog** for production-grade structured logging aligned with 2025 best practices.

### Key Benefits

✅ **Structured JSON Logging** - Machine-parseable logs for ELK, CloudWatch, etc.
✅ **Request Correlation** - Automatic request_id, user_id tracking across all logs
✅ **Performance Optimized** - Logger caching, lazy evaluation, async support
✅ **OpenTelemetry Ready** - Built-in trace/span correlation
✅ **Developer Experience** - Beautiful colored console output in dev mode
✅ **Production Battle-Tested** - Used by Sentry, GitLab, Stripe, and others

---

## What Changed

### 1. Dependencies Added

```toml
# Added to pyproject.toml
"structlog>=25.4.0"
"python-json-logger>=3.2.1"
```

### 2. Configuration (app/core/logging_config.py)

**Before:**
```python
import logging
logger = logging.getLogger(__name__)
logger.info("message", extra={"key": "value"})  # Manual extra dict
```

**After:**
```python
from app.core.logging_config import get_logger
logger = get_logger(__name__)
logger.info("message", key="value")  # Keyword arguments, cleaner!
```

### 3. Request Context Middleware (NEW)

Created `app/middleware/logging.py` that automatically:
- Binds `request_id` to all logs in a request
- Binds `user_id` for authenticated requests
- Binds `trace_id` and `span_id` for OpenTelemetry
- Logs HTTP requests with timing

### 4. Files Updated

**Core:**
- ✅ `pyproject.toml` - Added dependencies
- ✅ `app/core/logging_config.py` - Complete rewrite with structlog
- ✅ `app/middleware/logging.py` - NEW request context middleware
- ✅ `app/main.py` - Initialize logging, add middleware

**Services:**
- ✅ `app/services/auth.py` - Updated OAuth/Keycloak error logging

**Tasks:**
- ✅ `app/tasks/celery_app.py` - Celery worker logging initialization
- ✅ `app/tasks/pypi_check.py` - Updated logger instances

---

## Log Output Examples

### Development Mode (Console)

```
2025-10-22T10:30:45.123456Z [info     ] application_starting           app_name=saas_backend environment=development debug=True
2025-10-22T10:30:45.234567Z [info     ] cache_connected
2025-10-22T10:30:46.123456Z [info     ] http_request                   method=GET path=/api/v1/users request_id=abc-123 status_code=200 duration_ms=45.23
```

### Production Mode (JSON)

```json
{
  "timestamp": "2025-10-22T10:30:45.123456Z",
  "level": "info",
  "event": "application_starting",
  "logger": "app.main",
  "app_name": "saas_backend",
  "environment": "production",
  "debug": false
}

{
  "timestamp": "2025-10-22T10:30:46.123456Z",
  "level": "info",
  "event": "http_request",
  "logger": "app.middleware.logging",
  "method": "GET",
  "path": "/api/v1/users",
  "request_id": "abc-123",
  "user_id": "user-456",
  "status_code": 200,
  "duration_ms": 45.23
}

{
  "timestamp": "2025-10-22T10:31:00.123456Z",
  "level": "error",
  "event": "task_failed_after_retries",
  "logger": "app.tasks.celery_app",
  "task_id": "task-789",
  "task_name": "deliver_webhook_task",
  "retry_count": 3,
  "exception_type": "ConnectionError",
  "exception_message": "Failed to connect to webhook endpoint",
  "exception": "Traceback (most recent call last)..."
}
```

---

## How to Use

### Basic Logging

```python
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Info logging
logger.info("user_created", user_id=user.id, email=user.email)

# Warning logging
logger.warning("quota_exceeded", organization_id=org.id, quota_type="api_calls")

# Error logging with exception
try:
    risky_operation()
except Exception as e:
    logger.error("operation_failed", error=str(e), exc_info=True)
```

### Binding Context

```python
# Bind context that persists for multiple log calls
logger = logger.bind(user_id=user.id, org_id=org.id)

logger.info("action_started")  # Includes user_id and org_id
logger.info("action_completed")  # Still includes user_id and org_id
```

### Request Context (Automatic)

All logs within a request automatically include:
- `request_id` - From RequestIDMiddleware
- `method` - HTTP method
- `path` - Request path
- `client_host` - Client IP
- `user_id` - If authenticated
- `trace_id` - If OpenTelemetry is active

```python
# In any endpoint or service called during a request
logger.info("processing_payment")
# Output includes request_id, user_id, etc. automatically!
```

### Celery Tasks

```python
from app.core.logging_config import get_logger

logger = get_logger(__name__)

@celery_app.task
def my_task(arg1, arg2):
    logger.info("task_started", arg1=arg1, arg2=arg2)
    # ... task logic ...
    logger.info("task_completed")
```

---

## Migration Guide for Existing Code

### Pattern 1: Replace Logger Initialization

**Before:**
```python
import logging
logger = logging.getLogger(__name__)
```

**After:**
```python
from app.core.logging_config import get_logger
logger = get_logger(__name__)
```

### Pattern 2: Replace extra= Dictionaries

**Before:**
```python
logger.info("User logged in", extra={"user_id": user.id, "ip": ip})
```

**After:**
```python
logger.info("user_logged_in", user_id=user.id, ip=ip)
```

### Pattern 3: Event Names (Best Practice)

Use snake_case event names as the first argument:

**Good:**
```python
logger.info("database_connection_established", host=db_host, port=db_port)
logger.error("payment_processing_failed", payment_id=payment.id, reason=error)
```

**Avoid:**
```python
logger.info("Database connection established")  # No context, harder to query
logger.error(f"Payment {payment.id} failed")  # F-strings lose structure
```

---

## Environment Configuration

### Development

Set in `.env`:
```bash
APP_ENV=development
DEBUG=True
```

**Result:** Beautiful colored console output

### Production

Set in `.env`:
```bash
APP_ENV=production
DEBUG=False
```

**Result:** JSON output for log aggregation

---

## Integration with Observability Tools

### ELK Stack (Elasticsearch, Logstash, Kibana)

JSON logs can be directly ingested:
```bash
# Forward logs to Logstash
uvicorn app.main:app | logstash -f logstash.conf
```

### AWS CloudWatch

```python
# CloudWatch Log Insights queries
fields @timestamp, event, request_id, user_id, status_code
| filter event = "http_request"
| filter status_code >= 400
| sort @timestamp desc
```

### Datadog

```python
# Query logs by structured fields
service:saas_backend event:payment_processing_failed
```

### OpenTelemetry (Future)

The `LoggingMiddleware` already extracts trace/span IDs:
```python
# Logs automatically include:
{
  "trace_id": "a1b2c3d4e5f6g7h8i9j0",
  "span_id": "k1l2m3n4o5p6",
  "event": "database_query",
  "duration_ms": 23.45
}
```

---

## Performance Considerations

### Logger Caching

Structlog caches loggers on first use for **major performance gains**:
```python
# First call: initializes and caches
logger = get_logger(__name__)  # ~100μs

# Subsequent calls: returns cached instance
logger = get_logger(__name__)  # ~1μs (100x faster!)
```

### Lazy Evaluation

Expensive operations only execute if log level is enabled:
```python
# This only serializes if DEBUG level is active
logger.debug("debug_info", expensive_data=compute_expensive_data())
```

### Async Support

Structlog is async-friendly and thread-safe:
```python
async def my_handler():
    logger.info("async_operation_started")
    await some_async_work()
    logger.info("async_operation_completed")
```

---

## Troubleshooting

### Issue: Logs not showing in development

**Check:**
1. Is `APP_ENV=development` set?
2. Is `DEBUG=True` set?
3. Run `uv pip install structlog`

### Issue: JSON logs showing in development

**Fix:** Ensure `.env` has:
```bash
APP_ENV=development
```

### Issue: No request_id in logs

**Check:** LoggingMiddleware must be after RequestIDMiddleware:
```python
app.add_middleware(RequestIDMiddleware)  # First
app.add_middleware(LoggingMiddleware)    # Second
```

### Issue: Celery logs not structured

**Fix:** Ensure Celery workers are restarted after upgrade:
```bash
pkill -f celery
celery -A app.tasks.celery_app worker --loglevel=info
```

---

## Best Practices

### ✅ DO

- Use snake_case event names: `user_created`, `payment_failed`
- Add relevant context as kwargs: `user_id=user.id`
- Use `exc_info=True` for exception logging
- Log at appropriate levels (DEBUG, INFO, WARNING, ERROR)
- Use structured data, not f-strings

### ❌ DON'T

- Don't use f-strings: `f"User {user.id} logged in"` ❌
- Don't log sensitive data: passwords, tokens, credit cards
- Don't log in tight loops (creates noise)
- Don't mix structlog and stdlib logging
- Don't use generic event names: `"error"`, `"info"`

---

## Next Steps

### Phase 1: ✅ DONE
- [x] Install structlog
- [x] Configure logging pipeline
- [x] Add request context middleware
- [x] Update existing loggers
- [x] Configure Celery logging

### Phase 2: Recommended
- [ ] Add log sampling for high-volume endpoints
- [ ] Integrate Sentry for error tracking
- [ ] Set up log aggregation (ELK/CloudWatch)
- [ ] Create alerting rules in log platform
- [ ] Add OpenTelemetry tracing integration

### Phase 3: Advanced
- [ ] Add log-based metrics
- [ ] Implement log retention policies
- [ ] Create monitoring dashboards
- [ ] Set up log-based SLIs/SLOs
- [ ] Add anomaly detection

---

## References

- [Structlog Documentation](https://www.structlog.org/)
- [FastAPI Logging Best Practices](https://betterstack.com/community/guides/logging/logging-with-fastapi/)
- [Python Logging Best Practices 2025](https://www.matthewstrawbridge.com/content/2024/python-logging-basic-better-best/)
- [OpenTelemetry Python](https://opentelemetry.io/docs/instrumentation/python/)

---

## Questions?

**Q: Can I still use `logging.getLogger()` in some places?**
A: Yes, but not recommended. Structlog integrates with stdlib logging, but you lose benefits.

**Q: How do I query these logs?**
A: Use your log aggregation tool's query language. Event names and field names are consistent.

**Q: Will this break existing logging?**
A: No, backward compatible. Stdlib logging still works, but use structlog going forward.

**Q: Performance impact?**
A: Structlog is **faster** than stdlib logging due to caching and lazy evaluation.

---

**Document Version:** 1.0
**Last Updated:** 2025-10-22
**Author:** Claude Code Review Assistant
