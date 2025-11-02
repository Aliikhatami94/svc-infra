"""
Main FastAPI application using svc-infra utilities.

This example demonstrates a flexible, team-friendly setup where you can:
- Choose which features to enable (DB, auth, payments, observability, etc.)
- Customize service metadata (name, version, contact, license)
- Control logging and environment behavior
- Add custom routers and middleware
- Extend with team-specific requirements

The setup is organized in 4 clear steps for easy learning and customization.
"""

from svc_infra.api.fastapi import APIVersionSpec, ServiceInfo, setup_service_api
from svc_infra.api.fastapi.openapi.models import Contact, License
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
# You can also force a specific format by passing fmt="json" or fmt="plain"

setup_logging(
    level=pick(
        prod=LogLevelOptions.INFO,  # Production: INFO and above
        test=LogLevelOptions.INFO,  # Testing: INFO and above
        dev=LogLevelOptions.DEBUG,  # Development: DEBUG and above
        local=LogLevelOptions.DEBUG,  # Local: DEBUG and above (most verbose)
    ),
    # Optional overrides:
    # fmt="json",   # Force JSON format regardless of environment
    # fmt="plain",  # Force plain format regardless of environment
    # Note: You can also control via environment variables:
    #   LOG_LEVEL=DEBUG
    #   LOG_FORMAT=json
)

# ============================================================================
# STEP 2: Service Configuration
# ============================================================================
# Create the FastAPI app with explicit service metadata.
# All metadata appears in the OpenAPI docs at /docs and /openapi.json
#
# What setup_service_api does:
#   1. Creates a FastAPI() instance
#   2. Configures OpenAPI metadata (title, description, contact, license)
#   3. Mounts versioned routers (e.g., /v1/*, /v2/*)
#   4. Adds standard middlewares:
#      - Request ID generation (X-Request-Id header)
#      - Exception handling with proper error responses
#      - CORS (if configured)
#   5. Adds root health check endpoint: GET /ping
#
# API Versioning:
#   - Each version gets its own URL prefix (e.g., /v1/*)
#   - Routes are auto-discovered from the routers_package
#   - The package must have a 'router' variable (APIRouter instance)
#   - Example: svc_infra_template.api.v1 → /v1/ping, /v1/status

app = setup_service_api(
    service=ServiceInfo(
        name="svc-infra-template",
        description="Example service template built with svc-infra utilities",
        release="0.1.0",
        contact=Contact(
            name="Support",
            email="support@example.com",
            url="https://example.com",
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
    # Optional: Add root-level routers (outside versioning)
    # These appear directly at / without version prefix
    # root_routers="svc_infra_template.routers.root",
    # Optional: Configure CORS for public APIs
    # Allows browser-based clients to call your API from different domains
    # public_cors_origins=[
    #     "https://app.example.com",
    #     "https://www.example.com",
    # ],
)

# ============================================================================
# STEP 3: Add Features (Pick What You Need)
# ============================================================================
# svc-infra provides modular features that you can enable independently.
# Each feature is added with a simple add_* function call.
# Uncomment and configure the features your team needs.

# --- Database (SQLAlchemy 2.0 + Alembic Migrations) ---
# Provides:
#   - Async SQLAlchemy session management
#   - Database connection pooling
#   - Alembic integration for migrations
#   - CLI commands: python -m svc_infra.db init|migrate|upgrade|etc.
#
# Usage:
#   from svc_infra.api.fastapi.db import add_sql_db
#   add_sql_db(app)
#
# Configuration via .env:
#   SQL_URL=postgresql+asyncpg://user:pass@localhost:5432/dbname
#
# See: https://docs.sqlalchemy.org/

# --- Observability (Prometheus Metrics + OpenTelemetry Tracing) ---
# Provides:
#   - Prometheus metrics at /metrics endpoint
#   - Request duration, count, error rate
#   - Database connection pool metrics
#   - HTTP client instrumentation
#   - Distributed tracing support
#
# Usage:
#   from svc_infra.obs import add_observability
#   add_observability(
#       app,
#       db_engines=[engine],              # Optional: instrument DB
#       skip_metric_paths=["/health"],    # Don't track these in metrics
#   )
#
# CLI for local Grafana + Prometheus:
#   svc-infra obs-up    # Start local observability stack
#   svc-infra obs-down  # Stop local observability stack

# --- Authentication (FastAPI-Users: OAuth, Password, API Keys) ---
# Provides:
#   - User registration and login
#   - OAuth2 flows (Google, GitHub, etc.)
#   - Password authentication with hashing
#   - API key authentication
#   - Email verification
#   - Password reset flows
#   - User management endpoints
#
# Usage:
#   from svc_infra.api.fastapi.auth.add import add_auth_users
#   from your_app.db.auth import models, schemas
#
#   add_auth_users(
#       app,
#       user_model=models.User,              # SQLAlchemy model
#       schema_read=schemas.UserRead,        # Pydantic schema
#       schema_create=schemas.UserCreate,    # Pydantic schema
#       schema_update=schemas.UserUpdate,    # Pydantic schema
#       enable_oauth=True,                   # Enable OAuth providers
#       enable_password=True,                # Enable password login
#       enable_api_keys=True,                # Enable API key auth
#   )
#
# Adds routes:
#   POST   /auth/register
#   POST   /auth/login
#   POST   /auth/logout
#   GET    /auth/me
#   PATCH  /auth/me
#   POST   /auth/forgot-password
#   POST   /auth/reset-password
#   GET    /auth/verify
#   GET    /auth/{provider}/authorize  (OAuth)
#   GET    /auth/{provider}/callback   (OAuth)

# --- Payments (Stripe, Adyen, Fake for Testing) ---
# Provides:
#   - Unified payment provider interface
#   - Support for multiple payment gateways
#   - Webhook handling for payment events
#   - Subscription management
#
# Usage:
#   from svc_infra.api.fastapi.apf_payments.setup import add_payments
#   from svc_infra.apf_payments.provider.stripe import StripeAdapter
#
#   add_payments(
#       app,
#       # adapter=StripeAdapter(),  # For production
#       # adapter=FakeAdapter(),    # For development/testing
#   )
#
# Configuration via .env:
#   STRIPE_SECRET_KEY=sk_test_...
#   STRIPE_WEBHOOK_SECRET=whsec_...

# --- Caching (Redis + Cashews) ---
# Provides:
#   - Decorator-based caching (@cache_read, @cache_write)
#   - Resource-based patterns (user, project, etc.)
#   - Tag-based invalidation
#   - TTL support
#   - Automatic cache warming
#
# Usage:
#   from svc_infra.cache import init_cache, resource
#
#   init_cache(
#       url="redis://localhost:6379/0",
#       prefix="myapp",
#       version="v1",
#   )
#
#   # Define a cached resource
#   user = resource("user", "user_id")
#
#   @user.cache_read(suffix="profile")
#   async def get_user_profile(user_id: str):
#       # Cached with key: myapp:v1:user:{user_id}:profile
#       return await db.fetch_user(user_id)
#
#   @user.cache_write()
#   async def update_user(user_id: str, data: dict):
#       # Invalidates cache for this user
#       return await db.update_user(user_id, data)
#
# See: README in src/svc_infra/cache/

# --- Webhooks (Outbound Events) ---
# Provides:
#   - Webhook delivery management
#   - Retry logic with exponential backoff
#   - Webhook signature verification
#   - Event subscription management
#
# Usage:
#   from svc_infra.webhooks.add import add_webhooks
#   add_webhooks(app, ...)

# --- Admin Impersonation ---
# Provides:
#   - Admin users can impersonate other users
#   - Full audit trail of impersonation sessions
#   - Automatic context switching
#   - Security guardrails
#
# Usage:
#   from svc_infra.api.fastapi.admin.add import add_admin
#   add_admin(app)
#
# Adds routes:
#   POST   /admin/impersonate/{user_id}
#   POST   /admin/stop-impersonation
#   GET    /admin/audit/impersonation
#
# See: src/svc_infra/docs/admin.md

# --- Multi-Tenancy ---
# Provides:
#   - Tenant resolution from request (header, subdomain, path)
#   - Automatic tenant context injection
#   - Row-level security patterns
#
# Usage:
#   from svc_infra.api.fastapi.tenancy.add import add_tenancy
#   add_tenancy(app, resolver=...)

# --- Data Lifecycle Management (Retention, Archival, Deletion) ---
# Provides:
#   - Automatic data retention enforcement
#   - Data archival workflows
#   - GDPR-compliant data deletion
#   - Scheduled cleanup jobs
#
# Usage:
#   from svc_infra.data.add import add_data_lifecycle
#   add_data_lifecycle(app, ...)

# ============================================================================
# STEP 4: Custom Extensions (Team-Specific)
# ============================================================================
# This is where you add your own customizations:
# - Startup/shutdown logic
# - Custom middleware
# - Background tasks
# - Additional routers
# - Third-party integrations

# --- Startup/Shutdown Events ---
# Run code when the application starts or stops
# Useful for: initializing connections, warming caches, cleanup
#
# @app.on_event("startup")
# async def startup_event():
#     """Run when the application starts"""
#     # Initialize database connections
#     # Warm up caches
#     # Start background workers
#     # Log startup
#     pass
#
# @app.on_event("shutdown")
# async def shutdown_event():
#     """Run when the application stops"""
#     # Close database connections
#     # Stop background workers
#     # Flush metrics
#     # Log shutdown
#     pass

# --- Custom Middleware ---
# Add custom processing for every request/response
# Useful for: custom headers, logging, rate limiting, etc.
#
# @app.middleware("http")
# async def custom_middleware(request, call_next):
#     """Run for every HTTP request"""
#     # Before request
#     # Add custom headers, log request, check rate limits, etc.
#
#     response = await call_next(request)
#
#     # After request
#     # Add response headers, log response, record metrics, etc.
#     response.headers["X-Custom-Header"] = "value"
#
#     return response

# --- Background Tasks ---
# Schedule tasks to run in the background
# Note: For production, use svc_infra.jobs for persistent background jobs
#
# from fastapi import BackgroundTasks
#
# def send_email_task(email: str, message: str):
#     """Background task example"""
#     # Send email asynchronously
#     pass
#
# @app.post("/send-email")
# async def send_email(email: str, background_tasks: BackgroundTasks):
#     background_tasks.add_task(send_email_task, email, "Welcome!")
#     return {"message": "Email queued"}

# --- Additional Routers ---
# Mount extra routers for additional functionality
#
# from fastapi import APIRouter
# custom_router = APIRouter(prefix="/custom", tags=["Custom"])
#
# @custom_router.get("/health")
# async def custom_health():
#     return {"status": "ok"}
#
# app.include_router(custom_router)

# --- Third-Party Integrations ---
# Add integrations with external services
#
# Example: Sentry for error tracking
# import sentry_sdk
# sentry_sdk.init(dsn="your-dsn-here")
#
# Example: Custom monitoring
# from prometheus_client import Counter
# request_counter = Counter('my_requests', 'Custom request counter')

# =============================================================================
# That's it! Your service is ready to run.
#
# To start: make run
# Visit: http://localhost:8000/docs
# =============================================================================


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
