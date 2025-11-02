"""
Main FastAPI application using svc-infra utilities - COMPLETE SHOWCASE.

This example demonstrates ALL svc-infra features with real implementations:
✅ Flexible logging setup (environment-aware)
✅ Service metadata & versioned APIs
✅ Security hardening (headers, CORS, HSTS, sessions)
✅ Database with SQLAlchemy + Alembic
✅ Redis caching with lifecycle management
✅ Observability (Prometheus metrics + tracing)
✅ Rate limiting & idempotency
✅ Payments integration (Stripe/Adyen/Fake)
✅ Webhooks (outbound events)
✅ Billing & subscriptions (usage-based, quotas)
✅ Authentication (users, OAuth, MFA, API keys) [commented]
✅ Multi-tenancy (header/subdomain/path resolution) [commented]
✅ Data lifecycle & GDPR compliance [commented]
✅ Admin operations & impersonation
✅ Background jobs & scheduling [commented]
✅ Custom middleware & extensions

The setup is organized in clear steps for easy learning and customization.
Each feature can be enabled/disabled via environment variables (.env file).
Some features are commented out and require additional setup (database models, etc.).
"""

# Import settings for configuration
from svc_infra_template.settings import settings

from svc_infra.api.fastapi import APIVersionSpec, ServiceInfo, setup_service_api
from svc_infra.api.fastapi.openapi.models import Contact, License
from svc_infra.api.fastapi.ops.add import add_maintenance_mode, add_probes
from svc_infra.app import LogLevelOptions, pick, setup_logging

# ============================================================================
# STEP 1: Logging Setup
# ============================================================================
# Configure logging with environment-aware levels.
# The pick() helper automatically selects the right config based on APP_ENV.
#
# Environment detection:
#   - Checks APP_ENV env var first
#   - Falls back to RAILWAY_ENVIRONMENT_NAME if on Railway
#   - Defaults to 'local' if neither is set
#
# Log format is auto-selected:
#   - prod/test → JSON format (structured, machine-readable)
#   - dev/local → Plain format (human-readable, colorized)
#
# You can override via env vars: LOG_LEVEL, LOG_FORMAT

setup_logging(
    level=pick(
        prod=LogLevelOptions.INFO,  # Production: INFO and above
        test=LogLevelOptions.INFO,  # Testing: INFO and above
        dev=LogLevelOptions.DEBUG,  # Development: DEBUG and above
        local=LogLevelOptions.DEBUG,  # Local: DEBUG and above (most verbose)
    ),
    # Optional: Drop noisy paths from access logs in prod/test
    filter_envs=("prod", "test"),
    drop_paths=["/metrics", "/health", "/_health", "/ping"],
)

# ============================================================================
# STEP 2: Application Lifecycle (Startup/Shutdown)
# ============================================================================
# Handle application startup and shutdown events.
# This is where you initialize/cleanup resources that live for the app lifetime.
# Note: We'll register these after creating the app


# ============================================================================
# STEP 3: Service Configuration
# ============================================================================
# Create the FastAPI app with explicit service metadata.
# All metadata appears in the OpenAPI docs at /docs and /openapi.json
#
# What setup_service_api does:
#   1. Creates a FastAPI() instance with lifespan handler
#   2. Configures OpenAPI metadata (title, description, contact, license)
#   3. Mounts versioned routers (e.g., /v1/*, /v2/*)
#   4. Adds standard middlewares:
#      - Request ID generation (X-Request-Id header)
#      - Exception handling with proper error responses
#      - CORS (if configured)
#   5. Adds root health check endpoint: GET /ping

app = setup_service_api(
    service=ServiceInfo(
        name="svc-infra-template",
        description=(
            "Complete showcase of svc-infra utilities for building production-ready FastAPI services. "
            "Features: DB, caching, auth, payments, observability, webhooks, admin, jobs, and more."
        ),
        release="0.2.0",
        contact=Contact(
            name="Engineering Team",
            email="eng@example.com",
            url="https://github.com/yourusername/svc-infra",
        ),
        license=License(
            name="MIT",
            url="https://opensource.org/licenses/MIT",
        ),
    ),
    versions=[
        # Version 1 API
        APIVersionSpec(
            tag="v1",
            routers_package="svc_infra_template.api.v1",
            # Optional: Override base URL for this version's docs
            # public_base_url="https://api.example.com"
        ),
        # Add more versions as your API evolves:
        # APIVersionSpec(
        #     tag="v2",
        #     routers_package="svc_infra_template.api.v2",
        # ),
    ],
    # Configure CORS for browser-based clients
    public_cors_origins=settings.cors_origins_list if settings.cors_enabled else None,
)

# ============================================================================
# STEP 3.5: Security Hardening (Headers, CORS, Sessions)
# ============================================================================
# Add security middlewares with production-ready defaults
from svc_infra.security.add import add_security

add_security(
    app,
    cors_origins=settings.cors_origins_list if settings.cors_enabled else None,
    allow_credentials=settings.cors_allow_credentials,
    enable_hsts_preload=settings.is_production,  # Enable HSTS preload in production
    install_session_middleware=True,  # Required for some auth flows
    session_secret_key=settings.auth_secret,
    session_cookie_https_only=settings.is_production,
)

# Features added by add_security:
# - Security headers (CSP, X-Frame-Options, X-Content-Type-Options, etc.)
# - HSTS with preload for HTTPS enforcement
# - CORS middleware with environment-aware configuration
# - Session middleware for stateful auth (cookies)
#
# See: src/svc_infra/security/headers.py for defaults

print("✅ Security middlewares enabled")

# ============================================================================
# STEP 4: Register Lifecycle Events
# ============================================================================


@app.on_event("startup")
async def startup_event():
    """
    Application startup handler.

    Initialize resources:
      - Database connections
      - Cache connections
      - Background workers
      - External service clients
    """
    print("🚀 Starting svc-infra-template...")

    # Database initialization
    if settings.database_configured:
        from svc_infra_template.db import get_engine

        get_engine()
        print(f"✅ Database connected: {settings.sql_url.split('@')[-1]}")

        # Cache initialization (using add_cache for lifecycle management)
    if settings.cache_configured:
        from svc_infra.cache.add import add_cache

        # add_cache wires startup/shutdown handlers automatically
        add_cache(
            app,
            url=settings.redis_url,
            prefix="svc-template",
            version="v1",
            expose_state=True,  # Exposes at app.state.cache
        )
        print(f"✅ Cache connected: {settings.redis_url}")

    # Background jobs initialization (if enabled)
    if settings.jobs_enabled and settings.jobs_redis_url:
        # Note: In production, run worker separately: python -m svc_infra.jobs worker
        print("✅ Background jobs configured")

    print("🎉 Application startup complete!\n")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Application shutdown handler.

    Cleanup resources:
      - Close database connections
      - Stop background workers
      - Flush metrics
    """
    print("\n🛑 Shutting down svc-infra-template...")

    # Close database connections
    if settings.database_configured:
        from svc_infra_template.db import get_engine

        engine = get_engine()
        await engine.dispose()
        print("✅ Database connections closed")

    print("👋 Shutdown complete")


# ============================================================================
# STEP 5: Add Features (Modular, Enable What You Need)
# ============================================================================
# svc-infra provides modular features that you can enable independently.
# Each feature is controlled by settings (environment variables).

# --- 4.1 Database (SQLAlchemy 2.0 + Alembic Migrations) ---
if settings.database_configured:
    from svc_infra_template.db import Base, get_engine
    from svc_infra_template.db.models import Project, Task
    from svc_infra_template.db.schemas import (
        ProjectCreate,
        ProjectRead,
        ProjectUpdate,
        TaskCreate,
        TaskRead,
        TaskUpdate,
    )

    from svc_infra.api.fastapi.db.sql.add import add_sql_db, add_sql_health, add_sql_resources
    from svc_infra.db.sql.resource import SqlResource

    # Add database session management
    add_sql_db(app, url=settings.sql_url)

    # Add health check endpoint for database
    add_sql_health(app, prefix="/_health/db")

    # Create tables on startup (for demo purposes - normally use Alembic migrations)
    async def _create_db_tables():
        """Create database tables if they don't exist."""
        from sqlalchemy.ext.asyncio import AsyncEngine

        engine: AsyncEngine = get_engine()
        async with engine.begin() as conn:
            # Create all tables defined in Base.metadata
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Database tables created")

    # Register startup function
    app.add_event_handler("startup", _create_db_tables)

    # Add auto-generated CRUD endpoints for models
    # These will be available at /_sql/projects and /_sql/tasks
    add_sql_resources(
        app,
        resources=[
            SqlResource(
                model=Project,
                prefix="/projects",
                tags=["Projects"],
                soft_delete=True,  # Project has deleted_at field
                search_fields=["name", "owner_email"],  # Enable search by these fields
                ordering_default="-created_at",  # Default sort by newest first
                allowed_order_fields=["id", "name", "created_at", "updated_at"],
                # Pydantic schemas for serialization/validation
                read_schema=ProjectRead,
                create_schema=ProjectCreate,
                update_schema=ProjectUpdate,
            ),
            SqlResource(
                model=Task,
                prefix="/tasks",
                tags=["Tasks"],
                soft_delete=False,  # Task doesn't use soft delete
                search_fields=["title", "status"],  # Enable search by these fields
                ordering_default="-created_at",
                allowed_order_fields=["id", "title", "status", "created_at", "updated_at"],
                # Pydantic schemas for serialization/validation
                read_schema=TaskRead,
                create_schema=TaskCreate,
                update_schema=TaskUpdate,
            ),
        ],
    )

# --- 4.2 Observability (Prometheus Metrics + OpenTelemetry Tracing) ---
if settings.metrics_enabled:
    from svc_infra.obs import add_observability

    # Get DB engine if database is configured
    db_engines = []
    if settings.database_configured:
        db_engines = [get_engine()]

    add_observability(
        app,
        db_engines=db_engines,  # Instrument DB connection pool metrics
        metrics_path=settings.metrics_path,
        skip_metric_paths=["/health", "/_health", "/ping", "/metrics"],
    )

    # CLI for local Grafana + Prometheus:
    #   svc-infra obs-up    # Start local observability stack
    #   svc-infra obs-down  # Stop local observability stack
    #
    # Or connect to Grafana Cloud (set GRAFANA_CLOUD_* env vars)

    print("✅ Observability feature enabled")

# --- 4.3 Rate Limiting ---
if settings.rate_limit_enabled:
    from svc_infra.api.fastapi.middleware.ratelimit import SimpleRateLimitMiddleware

    # Add simple rate limiting middleware
    # Parameters:
    #   - limit: Number of requests allowed
    #   - window: Time window in seconds
    # Note: For production, use Redis-backed rate limiting
    app.add_middleware(
        SimpleRateLimitMiddleware,
        limit=settings.rate_limit_requests_per_minute,
        window=60,  # 60 seconds window
    )

    print("✅ Rate limiting feature enabled")

# --- 4.4 Idempotency ---
if settings.idempotency_enabled and settings.cache_configured:
    from svc_infra.api.fastapi.middleware.idempotency import IdempotencyMiddleware

    # Add idempotency middleware (requires Redis)
    # Clients send Idempotency-Key header to prevent duplicate processing
    app.add_middleware(
        IdempotencyMiddleware,
        redis_url=settings.redis_url,
        header_name=settings.idempotency_header,
        ttl_seconds=settings.idempotency_ttl_seconds,
    )

    print("✅ Idempotency feature enabled")

# --- 4.5 Payments (Stripe, Adyen, or Fake for Testing) ---
# Note: Payments require database setup first
if settings.database_configured and settings.payment_provider:
    from svc_infra.apf_payments.provider.fake import FakeAdapter
    from svc_infra.api.fastapi.apf_payments.setup import add_payments

    # Choose payment adapter based on configuration
    if settings.payment_provider == "fake":
        adapter = FakeAdapter()
    elif settings.payment_provider == "stripe" and settings.stripe_secret_key:
        from svc_infra.apf_payments.provider.stripe import StripeAdapter

        adapter = StripeAdapter(
            secret_key=settings.stripe_secret_key,
            webhook_secret=settings.stripe_webhook_secret,
        )
    # elif settings.payment_provider == "adyen" and settings.adyen_api_key:
    #     from svc_infra.apf_payments.provider.adyen import AdyenAdapter
    #     adapter = AdyenAdapter(...)
    else:
        adapter = None

    if adapter:
        add_payments(app, adapter=adapter)
        print(f"✅ Payments feature enabled (provider: {settings.payment_provider})")

# --- 4.6 Webhooks (Outbound Events) ---
if settings.webhooks_enabled and settings.database_configured:
    from svc_infra.webhooks.add import add_webhooks

    add_webhooks(app)

    # Webhooks allow your service to notify external systems of events
    # Example: await webhook_service.send_event("user.created", {"user_id": 123})
    #
    # Adds routes:
    #   POST   /webhooks/subscriptions          - Create webhook subscription
    #   GET    /webhooks/subscriptions          - List subscriptions
    #   GET    /webhooks/subscriptions/{id}     - Get subscription
    #   DELETE /webhooks/subscriptions/{id}     - Delete subscription
    #   GET    /webhooks/deliveries             - List delivery attempts

    print("✅ Webhooks feature enabled")

# --- 4.7 Billing & Subscriptions ---
if settings.billing_enabled and settings.database_configured:
    from svc_infra.billing.async_service import BillingService
    from svc_infra.billing.quotas import QuotaEnforcer

    # Initialize billing service for subscription and usage tracking
    # This provides the core billing logic but doesn't mount API routes
    # (you'd add custom routes in your versioned routers)
    billing_service = BillingService()
    quota_enforcer = QuotaEnforcer() if settings.billing_quota_enforcement else None

    # Store in app state for access in route handlers
    app.state.billing_service = billing_service
    if quota_enforcer:
        app.state.quota_enforcer = quota_enforcer

    # Note: Billing typically integrates with payment providers (Stripe)
    # and requires auth to associate subscriptions with users
    #
    # Features:
    # - Subscription plans (free, pro, enterprise)
    # - Usage-based/metered billing
    # - Quota enforcement and overage detection
    # - Invoice generation with line items
    # - Payment history tracking
    # - Automatic subscription renewal
    #
    # Example usage in routes:
    #   billing_service = request.app.state.billing_service
    #   await billing_service.record_usage(user_id, "api_calls", 1)
    #   subscription = await billing_service.get_subscription(user_id)
    #
    # See: src/svc_infra/billing/ for full API

    print("✅ Billing & quota enforcement enabled")

# --- 4.8 Authentication (Users, Sessions, OAuth) ---
# if settings.database_configured:
#     from svc_infra.api.fastapi.auth.add import add_auth_users
#
#     # Add complete authentication system with:
#     # - User registration & login
#     # - Password hashing with bcrypt
#     # - JWT access & refresh tokens
#     # - OAuth providers (Google, GitHub)
#     # - MFA/TOTP support
#     # - Account lockout after failed attempts
#     # - Email verification
#     # - API keys for service-to-service auth
#     add_auth_users(
#         app,
#         session_secret=settings.auth_secret,
#         access_token_expire_minutes=settings.auth_access_token_expire_minutes,
#         refresh_token_expire_days=settings.auth_refresh_token_expire_days,
#         # Password policy
#         min_password_length=settings.auth_min_password_length,
#         require_uppercase=settings.auth_require_uppercase,
#         require_lowercase=settings.auth_require_lowercase,
#         require_digits=settings.auth_require_digits,
#         require_special_chars=settings.auth_require_special_chars,
#         # Account lockout
#         max_login_attempts=settings.auth_max_login_attempts,
#         lockout_duration_minutes=settings.auth_lockout_duration_minutes,
#         # Email verification
#         require_email_verification=settings.auth_require_email_verification,
#         # OAuth providers
#         google_client_id=settings.auth_google_client_id,
#         google_client_secret=settings.auth_google_client_secret,
#         github_client_id=settings.auth_github_client_id,
#         github_client_secret=settings.auth_github_client_secret,
#     )
#
#     # Adds routes:
#     #   POST   /auth/register              - Register new user
#     #   POST   /auth/login                 - Login with credentials
#     #   POST   /auth/refresh               - Refresh access token
#     #   POST   /auth/logout                - Logout (invalidate tokens)
#     #   GET    /auth/me                    - Get current user
#     #   POST   /auth/verify-email          - Verify email with token
#     #   POST   /auth/forgot-password       - Request password reset
#     #   POST   /auth/reset-password        - Reset password with token
#     #   GET    /auth/{provider}/authorize  - OAuth authorize
#     #   GET    /auth/{provider}/callback   - OAuth callback
#     #   POST   /auth/mfa/enable            - Enable MFA
#     #   POST   /auth/mfa/verify            - Verify MFA code
#     #   POST   /auth/api-keys              - Create API key
#     #   GET    /auth/api-keys              - List API keys
#     #   DELETE /auth/api-keys/{key_id}     - Revoke API key
#     #
#     # See: src/svc_infra/docs/auth.md
#
#     print("✅ Authentication enabled")

# --- 4.9 Multi-Tenancy ---
# if settings.tenancy_enabled and settings.database_configured:
#     from svc_infra.api.fastapi.tenancy.add import add_tenancy
#     from svc_infra.api.fastapi.tenancy.resolvers import HeaderTenantResolver
#
#     # Add multi-tenancy support with automatic tenant resolution
#     # Resolves tenant from header, subdomain, or path
#     resolver = HeaderTenantResolver(header_name=settings.tenancy_header_name)
#
#     add_tenancy(
#         app,
#         resolver=resolver,
#         enforce=True,  # Require tenant for all requests
#     )
#
#     # Automatically adds tenant_id to all database queries
#     # Prevents data leakage between tenants
#     #
#     # See: src/svc_infra/docs/tenancy.md
#
#     print("✅ Multi-tenancy enabled")

# --- 4.10 Data Lifecycle & Compliance (GDPR) ---
# if settings.database_configured and settings.gdpr_enabled:
#     from svc_infra.data.add import add_data_lifecycle
#
#     # Add data lifecycle management:
#     # - Automatic data retention policies
#     # - Data archival to S3
#     # - GDPR right-to-deletion
#     # - Data export for portability
#     add_data_lifecycle(
#         app,
#         retention_days=settings.data_retention_days,
#         archival_enabled=settings.data_archival_enabled,
#         archival_s3_bucket=settings.data_archival_s3_bucket,
#         gdpr_auto_delete_after_days=settings.gdpr_auto_delete_after_days,
#     )
#
#     # Adds routes:
#     #   POST   /data/export                - Request data export
#     #   POST   /data/delete                - Request account deletion
#     #   GET    /data/export/{request_id}   - Download exported data
#     #
#     # See: src/svc_infra/docs/data-lifecycle.md
#
#     print("✅ Data lifecycle & GDPR compliance enabled")

# --- 4.11 Admin & Impersonation ---
if settings.admin_enabled:
    from svc_infra.api.fastapi.admin.add import add_admin

    # Add admin operations with user impersonation capabilities
    # Requires auth setup for proper permission checks
    add_admin(
        app,
        enable_impersonation=settings.admin_impersonation_enabled,
        secret=settings.auth_secret,  # Use auth secret for signing impersonation tokens
        ttl_seconds=15 * 60,  # 15 minutes impersonation session
    )

    # Adds routes:
    #   POST   /admin/impersonate/start        - Start impersonating a user (admin only)
    #   POST   /admin/impersonate/stop         - Stop impersonation session
    #
    # Features:
    # - Admin can impersonate any user for troubleshooting
    # - Audit logging of all impersonation actions
    # - Time-limited sessions with automatic expiry
    # - Actor's permissions preserved during impersonation
    # - Secure token-based implementation with HMAC
    #
    # See: src/svc_infra/docs/admin.md

    print("✅ Admin & impersonation enabled")

# --- 4.12 Operations & Health Checks ---

# Add Kubernetes-style health probes
add_probes(app, prefix="/_ops")

# Add maintenance mode support
if settings.maintenance_mode:
    add_maintenance_mode(app)

print("✅ Operations features enabled")

# --- 4.13 Documentation Enhancements ---
if settings.docs_enabled:
    from svc_infra.api.fastapi.docs.add import add_docs

    # Disable the built-in landing page since we have our own custom root endpoint below
    add_docs(app, include_landing=False)

    # Adds enhanced documentation features:
    #   - Scoped docs per API version
    #   - Interactive API explorer

    print("✅ Documentation enhancements enabled")

# --- 4.14 Background Jobs (Optional, requires Redis) ---
if settings.jobs_enabled and settings.jobs_redis_url:
    # Note: Jobs are typically run in a separate worker process
    # Start worker: python -m svc_infra.jobs worker
    #
    # from svc_infra.jobs.easy import easy_jobs
    #
    # worker, scheduler = easy_jobs(
    #     app,
    #     redis_url=settings.jobs_redis_url,
    #     enable_scheduler=settings.scheduler_enabled,
    # )
    #
    # Example job:
    # @worker.task()
    # async def send_email(email: str, subject: str, body: str):
    #     # Send email asynchronously
    #     pass
    #
    # # Enqueue job:
    # await send_email.kiq(email="user@example.com", subject="Hello", body="World")

    print("✅ Background jobs configured (run worker separately)")

# ============================================================================
# STEP 6: Custom Extensions (Team-Specific)
# ============================================================================
# This is where you add your own customizations.

# --- 5.1 Custom Middleware ---
# Add custom processing for every request/response


@app.middleware("http")
async def custom_headers_middleware(request, call_next):
    """
    Add custom headers to all responses.

    This example adds:
    - X-App-Version: Your app version
    - X-Environment: Current environment
    """
    response = await call_next(request)

    # Add custom headers
    response.headers["X-App-Version"] = "0.2.0"
    response.headers["X-Environment"] = settings.app_env

    return response


# --- 5.2 Request ID Middleware ---
# Already added by setup_service_api, but you can customize:
# @app.middleware("http")
# async def request_id_middleware(request, call_next):
#     request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
#     # Store in request state for use in endpoints
#     request.state.request_id = request_id
#     response = await call_next(request)
#     response.headers["X-Request-Id"] = request_id
#     return response

# --- 5.3 Error Tracking (Sentry) ---
if settings.sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment or settings.app_env,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
        ],
        traces_sample_rate=0.1 if settings.is_production else 1.0,
    )

    print("✅ Sentry error tracking enabled")

# =============================================================================
# That's it! Your service is fully configured with ALL svc-infra features.
#
# Note: setup_service_api() already provides a nice landing page at "/" with
# links to all API documentation (root and versioned). No custom root endpoint needed.
#
# To start:
#   1. Configure .env file with your settings
#   2. Run migrations (if using database):
#      python -m svc_infra.db init --project-root .
#      python -m svc_infra.db revision -m "Initial" --project-root .
#      python -m svc_infra.db upgrade head --project-root .
#   3. Start the service:
#      make run
#   4. Visit: http://localhost:8001/docs
#
# Enable/disable features via .env:
#   - Set SQL_URL to enable database
#   - Set REDIS_URL to enable caching & idempotency
#   - Set METRICS_ENABLED=false to disable metrics
#   - Set PAYMENT_PROVIDER=stripe and STRIPE_SECRET_KEY=... for payments
#   - And more! See .env.example for all options
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level="info",
    )
