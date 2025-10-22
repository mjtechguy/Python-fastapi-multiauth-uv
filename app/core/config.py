"""Application configuration management."""

from typing import Any, Literal
from pydantic import (
    AnyHttpUrl,
    Field,
    PostgresDsn,
    RedisDsn,
    field_validator,
    ValidationInfo,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
        case_sensitive=True,
    )

    # Application
    APP_NAME: str = "SaaS Backend Framework"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # Security
    SECRET_KEY: str = Field(min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    BCRYPT_ROUNDS: int = 12
    PASSWORD_MIN_LENGTH: int = 8
    SESSION_TIMEOUT_MINUTES: int = 60
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 30

    # Database
    DATABASE_URL: PostgresDsn
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: RedisDsn
    REDIS_CACHE_DB: int = 1

    # Celery
    CELERY_BROKER_URL: RedisDsn
    CELERY_RESULT_BACKEND: RedisDsn

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"
    CORS_ALLOW_CREDENTIALS: bool = True

    def get_cors_origins(self) -> list[str]:
        """Get CORS origins as a list."""
        if not self.CORS_ORIGINS:
            return ["http://localhost:3000"]
        if isinstance(self.CORS_ORIGINS, list):
            return self.CORS_ORIGINS
        # Parse comma-separated string
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    # OAuth2 - Google
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""

    # OAuth2 - GitHub
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_REDIRECT_URI: str = ""

    # OAuth2 - Microsoft
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""
    MICROSOFT_REDIRECT_URI: str = ""

    # Keycloak
    KEYCLOAK_SERVER_URL: str = ""
    KEYCLOAK_REALM: str = ""
    KEYCLOAK_CLIENT_ID: str = ""
    KEYCLOAK_CLIENT_SECRET: str = ""

    # OpenAI / LLM
    OPENAI_API_KEY: str = ""
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_MAX_TOKENS: int = 2000

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60

    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""

    # Monitoring
    SENTRY_DSN: str = ""
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # PyPI Version Check
    PYPI_CHECK_ENABLED: bool = True
    PYPI_CHECK_INTERVAL_HOURS: int = 24

    # File Storage
    FILE_STORAGE_PROVIDER: Literal["local", "s3"] = "local"
    LOCAL_UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 50
    AWS_S3_BUCKET: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    AWS_ENDPOINT_URL: str = ""  # For MinIO or other S3-compatible services

    # File Upload Restrictions
    ALLOWED_FILE_TYPES: str = ""  # Comma-separated MIME types, or "*" for all types
    BLOCKED_FILE_TYPES: str = "application/x-executable,application/x-dosexec,application/x-msdos-program"  # Security: block executables

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.APP_ENV == "production"

    @property
    def database_url_sync(self) -> str:
        """Get synchronous database URL for Alembic."""
        return str(self.DATABASE_URL).replace("+asyncpg", "")

    @property
    def allowed_file_types_list(self) -> list[str] | None:
        """Get list of allowed file types from comma-separated string.

        Returns:
            - None if ALLOWED_FILE_TYPES is empty (use default allow list)
            - ["*"] if ALLOWED_FILE_TYPES is "*" (allow all types)
            - List of MIME types otherwise
        """
        if not self.ALLOWED_FILE_TYPES:
            return None
        if self.ALLOWED_FILE_TYPES.strip() == "*":
            return ["*"]
        return [mime.strip() for mime in self.ALLOWED_FILE_TYPES.split(",") if mime.strip()]

    @property
    def blocked_file_types_list(self) -> list[str]:
        """Get list of blocked file types from comma-separated string."""
        if not self.BLOCKED_FILE_TYPES:
            return []
        return [mime.strip() for mime in self.BLOCKED_FILE_TYPES.split(",") if mime.strip()]


settings = Settings()
