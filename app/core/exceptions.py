"""Custom exception classes for the application."""


class BaseAPIException(Exception):
    """Base exception for API errors."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class QuotaExceededException(BaseAPIException):
    """Raised when organization exceeds quota."""

    def __init__(self, quota_type: str):
        super().__init__(
            message=f"Organization has exceeded {quota_type} quota",
            status_code=429
        )
        self.quota_type = quota_type


class ResourceNotFoundException(BaseAPIException):
    """Raised when resource not found."""

    def __init__(self, resource: str, resource_id: str):
        super().__init__(
            message=f"{resource} with id {resource_id} not found",
            status_code=404
        )
        self.resource = resource
        self.resource_id = resource_id


class AuthenticationException(BaseAPIException):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class AuthorizationException(BaseAPIException):
    """Raised when user lacks permissions."""

    def __init__(self, message: str = "Insufficient permissions", permission: str | None = None):
        super().__init__(message, status_code=403)
        self.permission = permission


class AccountLockedException(BaseAPIException):
    """Raised when account is locked due to failed login attempts."""

    def __init__(self, lockout_until: str | None = None):
        message = "Account is locked due to too many failed login attempts"
        if lockout_until:
            message += f" until {lockout_until}"
        super().__init__(message, status_code=403)
        self.lockout_until = lockout_until


class InvalidTokenException(BaseAPIException):
    """Raised when token is invalid or expired."""

    def __init__(self, message: str = "Invalid or expired token"):
        super().__init__(message, status_code=401)


class ValidationException(BaseAPIException):
    """Raised when validation fails."""

    def __init__(self, message: str, field: str | None = None):
        super().__init__(message, status_code=422)
        self.field = field


class DuplicateResourceException(BaseAPIException):
    """Raised when attempting to create a duplicate resource."""

    def __init__(self, resource: str, field: str, value: str):
        super().__init__(
            message=f"{resource} with {field} '{value}' already exists",
            status_code=409
        )
        self.resource = resource
        self.field = field
        self.value = value


class RateLimitExceededException(BaseAPIException):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after: int | None = None):
        message = "Rate limit exceeded"
        if retry_after:
            message += f". Retry after {retry_after} seconds"
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class ExternalServiceException(BaseAPIException):
    """Raised when external service fails."""

    def __init__(self, service: str, message: str | None = None):
        error_message = f"External service '{service}' is unavailable"
        if message:
            error_message += f": {message}"
        super().__init__(error_message, status_code=503)
        self.service = service


class StorageException(BaseAPIException):
    """Raised when storage operation fails."""

    def __init__(self, message: str = "Storage operation failed"):
        super().__init__(message, status_code=500)


class WebhookDeliveryException(BaseAPIException):
    """Raised when webhook delivery fails."""

    def __init__(self, webhook_id: str, message: str = "Webhook delivery failed"):
        super().__init__(message, status_code=500)
        self.webhook_id = webhook_id
