"""Rate limiting middleware."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"]
    if settings.RATE_LIMIT_ENABLED
    else [],
    enabled=settings.RATE_LIMIT_ENABLED,
)
