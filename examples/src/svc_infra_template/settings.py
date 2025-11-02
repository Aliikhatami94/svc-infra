"""
Centralized configuration management using Pydantic Settings.

All configuration is loaded from environment variables (.env file).
Type-safe with validation and defaults.
"""

from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ========================================================================
    # Application
    # ========================================================================
    app_env: Literal["local", "dev", "test", "prod"] = Field(default="local")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    log_format: Literal["plain", "json"] = Field(default="plain")

    # API
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8001)

    # ========================================================================
    # Database
    # ========================================================================
    sql_url: Optional[str] = Field(
        default=None,
        description="Database connection string",
    )
    sql_pool_size: int = Field(default=5)
    sql_max_overflow: int = Field(default=10)
    sql_pool_timeout: int = Field(default=30)

    # ========================================================================
    # Cache (Redis)
    # ========================================================================
    redis_url: Optional[str] = Field(default=None)
    cache_prefix: str = Field(default="svc_infra_template")
    cache_version: str = Field(default="v1")
    cache_default_ttl: int = Field(default=3600)

    # ========================================================================
    # Authentication
    # ========================================================================
    auth_secret: str = Field(
        default="dev-secret-change-in-production",
        description="Secret key for JWT tokens",
    )
    auth_jwt_algorithm: str = Field(default="HS256")
    auth_access_token_expire_minutes: int = Field(default=30)
    auth_refresh_token_expire_days: int = Field(default=7)

    # Password Policy
    auth_min_password_length: int = Field(default=8)
    auth_require_uppercase: bool = Field(default=True)
    auth_require_lowercase: bool = Field(default=True)
    auth_require_digits: bool = Field(default=True)
    auth_require_special_chars: bool = Field(default=True)

    # Account Lockout
    auth_max_login_attempts: int = Field(default=5)
    auth_lockout_duration_minutes: int = Field(default=30)

    # Email Verification
    auth_require_email_verification: bool = Field(default=False)
    auth_verification_token_expire_hours: int = Field(default=24)

    # OAuth
    auth_google_client_id: Optional[str] = Field(default=None)
    auth_google_client_secret: Optional[str] = Field(default=None)
    auth_github_client_id: Optional[str] = Field(default=None)
    auth_github_client_secret: Optional[str] = Field(default=None)

    # ========================================================================
    # Payments
    # ========================================================================
    payment_provider: Optional[Literal["stripe", "adyen", "fake"]] = Field(default=None)

    # Stripe
    stripe_secret_key: Optional[str] = Field(default=None)
    stripe_publishable_key: Optional[str] = Field(default=None)
    stripe_webhook_secret: Optional[str] = Field(default=None)

    # Adyen
    adyen_api_key: Optional[str] = Field(default=None)
    adyen_merchant_account: Optional[str] = Field(default=None)
    adyen_environment: Literal["test", "live"] = Field(default="test")

    # ========================================================================
    # Observability
    # ========================================================================
    metrics_enabled: bool = Field(default=True)
    metrics_path: str = Field(default="/metrics")

    otel_enabled: bool = Field(default=False)
    otel_service_name: str = Field(default="svc-infra-template")
    otel_exporter_otlp_endpoint: Optional[str] = Field(default=None)

    # Grafana Cloud
    grafana_cloud_instance_id: Optional[str] = Field(default=None)
    grafana_cloud_api_key: Optional[str] = Field(default=None)
    grafana_cloud_prometheus_url: Optional[str] = Field(default=None)
    grafana_cloud_tempo_url: Optional[str] = Field(default=None)

    # ========================================================================
    # Webhooks
    # ========================================================================
    webhooks_enabled: bool = Field(default=True)
    webhooks_max_retries: int = Field(default=3)
    webhooks_retry_backoff_seconds: int = Field(default=60)
    webhooks_secret: str = Field(default="dev-webhook-secret")

    # ========================================================================
    # Rate Limiting
    # ========================================================================
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_requests_per_minute: int = Field(default=60)
    rate_limit_burst: int = Field(default=10)

    # ========================================================================
    # Idempotency
    # ========================================================================
    idempotency_enabled: bool = Field(default=True)
    idempotency_header: str = Field(default="Idempotency-Key")
    idempotency_ttl_seconds: int = Field(default=86400)

    # ========================================================================
    # Multi-Tenancy
    # ========================================================================
    tenancy_enabled: bool = Field(default=False)
    tenancy_resolution: Literal["header", "subdomain", "path"] = Field(default="header")
    tenancy_header_name: str = Field(default="X-Tenant-ID")

    # ========================================================================
    # Admin & Operations
    # ========================================================================
    admin_enabled: bool = Field(default=True)
    admin_impersonation_enabled: bool = Field(default=True)

    maintenance_mode: bool = Field(default=False)
    maintenance_message: str = Field(default="We're performing scheduled maintenance. Back soon!")

    # ========================================================================
    # Background Jobs
    # ========================================================================
    jobs_enabled: bool = Field(default=True)
    jobs_redis_url: Optional[str] = Field(default=None)

    scheduler_enabled: bool = Field(default=True)

    # ========================================================================
    # Data Lifecycle & Compliance
    # ========================================================================
    data_retention_days: int = Field(default=365)
    data_archival_enabled: bool = Field(default=False)
    data_archival_s3_bucket: Optional[str] = Field(default=None)

    gdpr_enabled: bool = Field(default=False)
    gdpr_auto_delete_after_days: int = Field(default=30)

    # ========================================================================
    # CORS
    # ========================================================================
    cors_enabled: bool = Field(default=True)
    cors_origins: Optional[str] = Field(
        default=None,
        description="Comma-separated list of allowed origins",
    )
    cors_allow_credentials: bool = Field(default=True)
    cors_allow_methods: str = Field(default="GET,POST,PUT,PATCH,DELETE")
    cors_allow_headers: str = Field(default="*")

    # ========================================================================
    # Documentation
    # ========================================================================
    docs_enabled: bool = Field(default=True)
    docs_path: str = Field(default="/docs")
    redoc_path: str = Field(default="/redoc")
    sdk_generation_enabled: bool = Field(default=False)

    # ========================================================================
    # Email
    # ========================================================================
    smtp_host: Optional[str] = Field(default=None)
    smtp_port: int = Field(default=587)
    smtp_username: Optional[str] = Field(default=None)
    smtp_password: Optional[str] = Field(default=None)
    smtp_from: Optional[str] = Field(default=None)
    smtp_from_name: str = Field(default="SVC Infra Template")

    # ========================================================================
    # External Services
    # ========================================================================
    sentry_dsn: Optional[str] = Field(default=None)
    sentry_environment: Optional[str] = Field(default=None)

    aws_access_key_id: Optional[str] = Field(default=None)
    aws_secret_access_key: Optional[str] = Field(default=None)
    aws_region: str = Field(default="us-east-1")

    # ========================================================================
    # Helpers
    # ========================================================================

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env == "prod"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.app_env in ("local", "dev")

    @property
    def cors_origins_list(self) -> list[str]:
        """Get CORS origins as a list."""
        if not self.cors_origins:
            return []
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def database_configured(self) -> bool:
        """Check if database is configured."""
        return self.sql_url is not None

    @property
    def cache_configured(self) -> bool:
        """Check if cache is configured."""
        return self.redis_url is not None

    @property
    def smtp_configured(self) -> bool:
        """Check if SMTP is configured."""
        return all([self.smtp_host, self.smtp_username, self.smtp_password])


# Global settings instance
settings = Settings()
