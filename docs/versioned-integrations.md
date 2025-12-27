# Using add_* Functions Under Versioned Routing

## Problem

By default, `add_*` functions from svc-infra and fin-infra mount routes at root level (e.g., `/banking/*`, `/_sql/*`). However, you may want all features consolidated under a single versioned API prefix (e.g., `/v0/banking`) to keep your API organized under version namespaces.

## Simple Solution (Recommended)

Use the `extract_router()` helper:

```python
# src/your_api/routers/v0/banking.py
from svc_infra.api.fastapi.versioned import extract_router
from fin_infra.banking import add_banking

# Extract router and provider from add_banking()
router, banking_provider = extract_router(
    add_banking,
    prefix="/banking",
    provider="plaid",
    cache_ttl=60,
)

# That's it! svc-infra auto-discovers 'router' and mounts at /v0/banking
```

### Result

- ✅ All banking endpoints under `/v0/banking/*`
- ✅ Banking docs included in `/v0/docs` (not separate card)
- ✅ Full `add_banking()` functionality preserved
- ✅ Returns provider instance for additional use

## Complete Example

```python
# Directory structure
your_api/
  routers/
    v0/
      __init__.py
      status.py
      banking.py      # <- Integration using helper
      payments.py     # <- Another integration

# banking.py - Clean and simple
"""Banking integration under v0 routing."""
from svc_infra.api.fastapi.versioned import extract_router
from fin_infra.banking import add_banking

router, banking_provider = extract_router(
    add_banking,
    prefix="/banking",
    provider="plaid",  # or "teller"
    cache_ttl=60,
)

# Optional: Store provider on app state for later use
# This happens in app.py after router discovery:
# app.state.banking = banking_provider
```

## Works With

Any svc-infra or fin-infra function that calls `app.include_router()`:

```python
# Banking integration
from fin_infra.banking import add_banking
router, provider = extract_router(add_banking, prefix="/banking", provider="plaid")

# Market data
from fin_infra.markets import add_market_data
router, provider = extract_router(add_market_data, prefix="/markets")

# Analytics
from fin_infra.analytics import add_analytics
router, provider = extract_router(add_analytics, prefix="/analytics")

# Budgets
from fin_infra.budgets import add_budgets
router, provider = extract_router(add_budgets, prefix="/budgets")

# Documents
from fin_infra.documents import add_documents
router, provider = extract_router(add_documents, prefix="/documents")

# Any custom add_* function following the pattern
```

## When to Use

**Use when:**
- Building a monolithic versioned API where all features belong under `/v0`, `/v1`, etc.
- You want unified documentation at `/v0/docs` showing all features together
- You're consolidating multiple integrations under one version
- You need version-specific behavior for third-party integrations

**Don't use when:**
- Feature should have its own root-level endpoint (e.g., public webhooks at `/webhooks`)
- Integration is shared across multiple versions (mount at root instead)
- You only need a subset of endpoints (define manually)

## Alternative: Manual Definition

For simple integrations, define routes manually:

```python
# routers/v0/banking.py
from svc_infra.api.fastapi.dual.public import public_router
from fin_infra.banking import easy_banking

router = public_router(prefix="/banking", tags=["Banking"])
banking = easy_banking(provider="plaid")

@router.post("/link")
async def create_link(request: CreateLinkRequest):
    return banking.create_link_token(user_id=request.user_id)

# ... define other endpoints
```

Use manual definition when:
- Only need a subset of integration endpoints
- Want custom validation/transforms per endpoint
- Integration is very simple (2-3 endpoints)
- Need version-specific behavior per endpoint

## How It Works

The `extract_router()` helper:

1. **Creates Mock App**: Temporary FastAPI instance to capture router
2. **Intercepts Router**: Monkey-patches `include_router()` to capture instead of mount
3. **Calls Integration**: Runs `add_*()` function which creates all routes normally
4. **Returns Router**: Exports captured router for svc-infra auto-discovery
5. **Auto-Mounts**: svc-infra finds `router` in `v0.banking` and mounts at `/v0/banking`

The provider/integration instance is also returned for additional use if needed.

## See Also

- [API Versioning](./api.md#versioning) - How svc-infra version routing works
- [Router Auto-Discovery](./api.md#router-discovery) - How routers are found and mounted
- [Dual Routers](./api.md#dual-routers) - Similar pattern for public/protected routers
- `svc_infra.api.fastapi.versioned` - Source code for helper function

---

## Additional Integration Examples

### Healthcare System

Mount authentication, RBAC, and audit logging under versioned routes for a healthcare API:

```python
from fastapi import FastAPI
from svc_infra.api.fastapi.dual import extract_router
from svc_infra.auth import add_auth
from svc_infra.rbac import add_rbac
from svc_infra.audit import add_audit_log
from svc_infra.documents import add_documents
from svc_infra.rate_limit import add_rate_limiting
from svc_infra.webhooks import add_webhooks

app = FastAPI(title="Healthcare API")

# Define version routers
v1 = APIRouter(prefix="/api/v1", tags=["v1"])
v2 = APIRouter(prefix="/api/v2", tags=["v2"])

# Authentication (both versions)
auth_v1 = extract_router(add_auth, jwt_secret="...", token_expiry=3600)
auth_v2 = extract_router(add_auth, jwt_secret="...", token_expiry=7200)

v1.include_router(auth_v1)
v2.include_router(auth_v2)

# RBAC - v2 has enhanced role system
rbac_v1 = extract_router(add_rbac, roles=["admin", "doctor", "nurse", "patient"])
rbac_v2 = extract_router(add_rbac, roles=[
    "admin",
    "attending_physician",
    "resident",
    "nurse_practitioner",
    "registered_nurse",
    "medical_assistant",
    "patient",
    "family_member",  # New in v2
])

v1.include_router(rbac_v1)
v2.include_router(rbac_v2)

# Documents - v2 has HIPAA-compliant audit logging
documents_v1 = extract_router(add_documents)
documents_v2 = extract_router(
    add_documents,
    storage_backend=encrypted_s3_backend,  # Encryption at rest
    max_file_size=50 * 1024 * 1024,        # 50MB limit
)

v1.include_router(documents_v1)
v2.include_router(documents_v2)

# Audit logging - v2 only (new feature)
audit_router = extract_router(
    add_audit_log,
    retention_days=365 * 7,  # 7 years for HIPAA
    include_phi=False,       # Never log PHI
)
v2.include_router(audit_router)

# Mount version routers
app.include_router(v1)
app.include_router(v2)
```

### E-Commerce Platform

```python
from fastapi import FastAPI
from svc_infra.api.fastapi.dual import extract_router
from svc_infra.auth import add_auth
from svc_infra.rate_limit import add_rate_limiting
from svc_infra.cache import add_cache
from svc_infra.webhooks import add_webhooks
from svc_infra.storage import add_storage

app = FastAPI(title="E-Commerce API")

# Version routers
v1 = APIRouter(prefix="/api/v1", tags=["v1"])
v2 = APIRouter(prefix="/api/v2", tags=["v2"])

# Rate limiting - different limits per version
rate_v1 = extract_router(
    add_rate_limiting,
    default_limit="100/minute",
    endpoints={
        "/products": "200/minute",
        "/orders": "50/minute",
    }
)
rate_v2 = extract_router(
    add_rate_limiting,
    default_limit="200/minute",  # Increased for v2
    endpoints={
        "/products": "500/minute",
        "/orders": "100/minute",
        "/search": "300/minute",  # New endpoint in v2
    }
)

v1.include_router(rate_v1)
v2.include_router(rate_v2)

# Webhooks - v2 has enhanced webhook features
webhooks_v1 = extract_router(
    add_webhooks,
    events=["order.created", "order.shipped", "order.delivered"]
)
webhooks_v2 = extract_router(
    add_webhooks,
    events=[
        "order.created",
        "order.updated",      # New in v2
        "order.shipped",
        "order.delivered",
        "order.cancelled",    # New in v2
        "payment.succeeded",  # New in v2
        "payment.failed",     # New in v2
        "inventory.low",      # New in v2
    ],
    retry_policy="exponential",  # New feature in v2
    max_retries=5,
)

v1.include_router(webhooks_v1)
v2.include_router(webhooks_v2)

# Storage for product images
storage_v1 = extract_router(add_storage, backend="s3", prefix="products-v1")
storage_v2 = extract_router(
    add_storage,
    backend="s3",
    prefix="products-v2",
    image_optimization=True,  # New in v2: auto-resize images
    cdn_enabled=True,         # New in v2: CDN integration
)

v1.include_router(storage_v1)
v2.include_router(storage_v2)

app.include_router(v1)
app.include_router(v2)
```

### SaaS Multi-Tenant Platform

```python
from fastapi import FastAPI
from svc_infra.api.fastapi.dual import extract_router
from svc_infra.auth import add_auth
from svc_infra.rbac import add_rbac
from svc_infra.tenant import add_multi_tenancy
from svc_infra.billing import add_usage_tracking
from svc_infra.feature_flags import add_feature_flags

app = FastAPI(title="SaaS Platform API")

# Version routers
v1 = APIRouter(prefix="/api/v1", tags=["v1"])
v2 = APIRouter(prefix="/api/v2", tags=["v2"])
internal = APIRouter(prefix="/internal/v1", tags=["internal"])

# Multi-tenancy (all versions)
tenant_router = extract_router(
    add_multi_tenancy,
    isolation_level="schema",  # Schema-per-tenant
    tenant_header="X-Tenant-ID",
)
v1.include_router(tenant_router)
v2.include_router(tenant_router)

# Auth with tenant context
auth_v1 = extract_router(
    add_auth,
    jwt_secret="...",
    include_tenant=True,  # Include tenant in JWT claims
)
auth_v2 = extract_router(
    add_auth,
    jwt_secret="...",
    include_tenant=True,
    mfa_enabled=True,  # New in v2: MFA support
)

v1.include_router(auth_v1)
v2.include_router(auth_v2)

# Usage tracking for billing
usage_v1 = extract_router(
    add_usage_tracking,
    metrics=["api_calls", "storage_bytes", "compute_seconds"]
)
usage_v2 = extract_router(
    add_usage_tracking,
    metrics=[
        "api_calls",
        "storage_bytes",
        "compute_seconds",
        "ai_tokens",      # New in v2
        "bandwidth_bytes", # New in v2
    ],
    granularity="minute",  # More granular in v2
)

v1.include_router(usage_v1)
v2.include_router(usage_v2)

# Feature flags (v2 only)
feature_flags_router = extract_router(
    add_feature_flags,
    flags=["new_dashboard", "ai_assistant", "advanced_analytics"]
)
v2.include_router(feature_flags_router)

# Internal admin routes (not versioned publicly)
admin_router = extract_router(
    add_admin_dashboard,
    auth_required=True,
    allowed_roles=["super_admin"],
)
internal.include_router(admin_router)

app.include_router(v1)
app.include_router(v2)
app.include_router(internal)
```

---

## Deprecation Workflow

Managing API version deprecation requires careful planning and clear communication to clients.

### Deprecation Timeline

| Phase | Duration | Actions |
|-------|----------|---------|
| **Announcement** | T-6 months | Announce deprecation, update docs |
| **Warning** | T-3 months | Add deprecation headers, log usage |
| **Sunset Warning** | T-1 month | Aggressive warnings, contact heavy users |
| **Read-Only** | T-1 week | Disable write operations |
| **Shutdown** | T-0 | Return 410 Gone |

### Implementation

```python
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime, date

class DeprecationMiddleware(BaseHTTPMiddleware):
    """Middleware to handle API version deprecation."""

    def __init__(
        self,
        app,
        deprecated_versions: dict[str, dict],
        # Format: {"v1": {"sunset_date": "2025-06-01", "successor": "v2"}}
    ):
        super().__init__(app)
        self.deprecated_versions = deprecated_versions

    async def dispatch(self, request: Request, call_next):
        # Extract version from path
        path = request.url.path
        version = self._extract_version(path)

        if version and version in self.deprecated_versions:
            deprecation_info = self.deprecated_versions[version]
            sunset_date = date.fromisoformat(deprecation_info["sunset_date"])
            successor = deprecation_info.get("successor", "")

            # Check if past sunset date
            if date.today() >= sunset_date:
                return Response(
                    content=f"API {version} has been retired. Please use {successor}.",
                    status_code=410,  # Gone
                    headers={
                        "Sunset": sunset_date.isoformat(),
                        "Link": f'</api/{successor}>; rel="successor-version"',
                    }
                )

            # Add deprecation headers
            response = await call_next(request)

            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = sunset_date.isoformat()
            if successor:
                response.headers["Link"] = f'</api/{successor}>; rel="successor-version"'

            # Log usage for tracking
            self._log_deprecated_usage(request, version)

            return response

        return await call_next(request)

    def _extract_version(self, path: str) -> str | None:
        """Extract API version from path."""
        import re
        match = re.search(r'/api/(v\d+)/', path)
        return match.group(1) if match else None

    def _log_deprecated_usage(self, request: Request, version: str):
        """Log usage of deprecated API for migration tracking."""
        # Log to file, database, or monitoring service
        client_ip = request.client.host
        user_agent = request.headers.get("user-agent", "")
        endpoint = request.url.path

        # In production, send to analytics/monitoring
        print(f"DEPRECATED API USAGE: {version} - {endpoint} - {client_ip}")

# Usage
app = FastAPI()

app.add_middleware(
    DeprecationMiddleware,
    deprecated_versions={
        "v1": {
            "sunset_date": "2025-06-01",
            "successor": "v2",
        }
    }
)
```

### Version-Specific Deprecation Responses

```python
from fastapi import APIRouter, HTTPException
from functools import wraps

def deprecated_in_version(
    version: str,
    sunset_date: str,
    message: str,
    successor_endpoint: str | None = None
):
    """Decorator to mark an endpoint as deprecated in specific version."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Execute the endpoint
            result = await func(*args, **kwargs)

            # Log deprecation usage
            # In production, track which clients are using deprecated endpoints

            return result

        # Add metadata for documentation
        wrapper.__doc__ = f"""
        ⚠️ **DEPRECATED in {version}** - Sunset: {sunset_date}

        {message}

        {f"Use `{successor_endpoint}` instead." if successor_endpoint else ""}

        ---

        {func.__doc__ or ""}
        """

        return wrapper
    return decorator

# Usage
v1_router = APIRouter(prefix="/api/v1")

@v1_router.get("/users/{user_id}/profile")
@deprecated_in_version(
    version="v1",
    sunset_date="2025-06-01",
    message="This endpoint returns limited user data.",
    successor_endpoint="GET /api/v2/users/{user_id}"
)
async def get_user_profile_v1(user_id: str):
    """Get user profile (deprecated, limited fields)."""
    return {"id": user_id, "name": "..."}

# v2 has the full implementation
v2_router = APIRouter(prefix="/api/v2")

@v2_router.get("/users/{user_id}")
async def get_user_v2(user_id: str):
    """Get user with full details."""
    return {
        "id": user_id,
        "name": "...",
        "email": "...",
        "created_at": "...",
        "settings": {...},
    }
```

### Migration Assistant Endpoint

Help clients discover changes between versions:

```python
from fastapi import APIRouter
from pydantic import BaseModel

class EndpointChange(BaseModel):
    """Describes a change between versions."""
    v1_endpoint: str
    v2_endpoint: str
    change_type: str  # renamed, moved, removed, added, modified
    description: str
    breaking: bool
    migration_guide: str | None = None

class MigrationGuide(BaseModel):
    """Migration guide between versions."""
    from_version: str
    to_version: str
    changes: list[EndpointChange]
    notes: list[str]

migration_router = APIRouter(prefix="/api/migration", tags=["Migration"])

@migration_router.get("/v1-to-v2", response_model=MigrationGuide)
async def get_v1_to_v2_migration():
    """Get migration guide from v1 to v2."""
    return MigrationGuide(
        from_version="v1",
        to_version="v2",
        changes=[
            EndpointChange(
                v1_endpoint="GET /api/v1/users/{id}/profile",
                v2_endpoint="GET /api/v2/users/{id}",
                change_type="renamed",
                description="Endpoint renamed and response extended",
                breaking=False,
                migration_guide="Replace `/profile` suffix. Response now includes additional fields."
            ),
            EndpointChange(
                v1_endpoint="POST /api/v1/orders",
                v2_endpoint="POST /api/v2/orders",
                change_type="modified",
                description="Request body schema changed",
                breaking=True,
                migration_guide="""
                    - `items` field now requires `sku` instead of `product_id`
                    - `shipping_address` is now required (was optional)
                    - Add `idempotency_key` header for safe retries
                """
            ),
            EndpointChange(
                v1_endpoint="GET /api/v1/analytics",
                v2_endpoint="GET /api/v2/analytics/summary",
                change_type="moved",
                description="Analytics endpoints reorganized",
                breaking=True,
                migration_guide="Update path. See /api/v2/analytics/* for new structure."
            ),
            EndpointChange(
                v1_endpoint="DELETE /api/v1/users/{id}",
                v2_endpoint="",
                change_type="removed",
                description="Hard delete removed for compliance",
                breaking=True,
                migration_guide="Use PATCH /api/v2/users/{id} with `{\"status\": \"deleted\"}` for soft delete."
            ),
        ],
        notes=[
            "Authentication tokens from v1 continue to work in v2",
            "Rate limits have been increased in v2",
            "All v2 endpoints support pagination via `cursor` parameter",
            "Webhook event payloads now include `api_version` field",
        ]
    )

@migration_router.get("/deprecated-usage")
async def get_deprecated_usage_stats():
    """Get stats on deprecated endpoint usage (admin only)."""
    # In production, fetch from analytics/logging system
    return {
        "v1_total_calls_last_30_days": 152340,
        "top_deprecated_endpoints": [
            {"endpoint": "GET /api/v1/users/{id}/profile", "calls": 45000},
            {"endpoint": "POST /api/v1/orders", "calls": 32000},
        ],
        "top_clients_using_v1": [
            {"client_id": "client_abc", "calls": 25000},
            {"client_id": "client_xyz", "calls": 18000},
        ],
        "migration_progress": "68%",  # % of traffic on v2
    }
```

### Client Communication

```python
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, EmailStr

class DeprecationNotification(BaseModel):
    """Deprecation notification settings."""
    client_id: str
    email: EmailStr
    notify_on: list[str]  # ["announcement", "warning", "sunset"]

notification_router = APIRouter(prefix="/api/deprecation-notifications")

@notification_router.post("/subscribe")
async def subscribe_to_deprecation_notices(
    notification: DeprecationNotification,
    background_tasks: BackgroundTasks
):
    """Subscribe to deprecation notices."""
    # Store subscription
    # In production, save to database

    # Send confirmation email
    background_tasks.add_task(
        send_deprecation_welcome_email,
        notification.email,
        notification.client_id
    )

    return {"status": "subscribed", "email": notification.email}

async def send_deprecation_welcome_email(email: str, client_id: str):
    """Send welcome email with deprecation timeline."""
    # Use your email service
    pass

# Scheduled job to notify clients
async def send_deprecation_reminders():
    """Send deprecation reminders (run via cron)."""
    from datetime import date, timedelta

    deprecations = [
        {"version": "v1", "sunset_date": date(2025, 6, 1)},
    ]

    for dep in deprecations:
        days_until_sunset = (dep["sunset_date"] - date.today()).days

        if days_until_sunset in [180, 90, 30, 14, 7, 1]:
            # Get subscribers for this notification type
            subscribers = get_subscribers_for_notification(
                "warning" if days_until_sunset > 30 else "sunset"
            )

            for subscriber in subscribers:
                await send_deprecation_reminder_email(
                    email=subscriber.email,
                    version=dep["version"],
                    days_remaining=days_until_sunset,
                    sunset_date=dep["sunset_date"].isoformat()
                )
```

---

## Version Routing Patterns

### Semantic Versioning with Breaking Changes

```python
from fastapi import FastAPI, APIRouter
from enum import Enum

class APIVersion(str, Enum):
    V1 = "v1"
    V2 = "v2"
    V3_BETA = "v3-beta"

def create_versioned_app() -> FastAPI:
    """Create app with proper version routing."""
    app = FastAPI(
        title="My API",
        version="3.0.0-beta",
        description="""
        ## API Versions

        - **v1** (Deprecated): Sunset June 2025
        - **v2** (Stable): Current recommended version
        - **v3-beta** (Preview): Breaking changes, not for production
        """
    )

    # Stable versions
    v1_router = create_v1_router()
    v2_router = create_v2_router()

    # Beta/preview versions
    v3_router = create_v3_router()

    app.include_router(v1_router, prefix="/api/v1", deprecated=True)
    app.include_router(v2_router, prefix="/api/v2")
    app.include_router(v3_router, prefix="/api/v3-beta", tags=["beta"])

    # Latest alias (points to stable)
    @app.get("/api/latest/version")
    async def get_latest_version():
        return {"version": "v2", "message": "Use /api/v2 for stable API"}

    return app
```

### Feature Flags for Gradual Rollout

```python
from fastapi import Depends, HTTPException
from functools import wraps

class FeatureFlags:
    """Feature flag service."""

    def __init__(self):
        self.flags = {
            "v3_endpoints": False,
            "enhanced_search": True,
            "new_auth_flow": False,
        }

    def is_enabled(self, flag: str, user_id: str = None) -> bool:
        """Check if feature is enabled (optionally per-user)."""
        # In production, check against feature flag service (LaunchDarkly, etc.)
        return self.flags.get(flag, False)

feature_flags = FeatureFlags()

def require_feature(flag: str):
    """Dependency to require a feature flag."""
    def dependency():
        if not feature_flags.is_enabled(flag):
            raise HTTPException(
                status_code=404,
                detail=f"This endpoint is not yet available"
            )
    return Depends(dependency)

# Usage
@v3_router.get(
    "/search/advanced",
    dependencies=[require_feature("enhanced_search")]
)
async def advanced_search(query: str):
    """Advanced search (feature flagged)."""
    return {"results": [...]}
```

---

## Best Practices

### 1. Version Everything from Day 1

```python
# ❌ Bad: No versioning
app.include_router(user_router, prefix="/users")

# ✅ Good: Version from the start
app.include_router(user_router, prefix="/api/v1/users")
```

### 2. Use Header Versioning for Minor Changes

```python
from fastapi import Header

@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    api_version: str = Header(default="2024-01-01", alias="X-API-Version")
):
    """Get user with version-specific behavior."""
    if api_version >= "2024-06-01":
        # New response format
        return UserV2(...)
    else:
        # Legacy format
        return UserV1(...)
```

### 3. Document Breaking Changes

```python
from fastapi import FastAPI

app = FastAPI(
    title="My API",
    description="""
    ## Changelog

    ### v2.0.0 (2024-06-01)
    - **BREAKING**: `GET /users/{id}` response schema changed
    - **BREAKING**: `product_id` renamed to `sku` in order items
    - Added: `GET /analytics/realtime` endpoint
    - Deprecated: `GET /reports/legacy` (use `/analytics` instead)

    ### v1.5.0 (2024-03-01)
    - Added: Webhook retry configuration
    - Fixed: Rate limit headers now accurate
    """
)
```

### 4. Maintain Backward Compatibility Where Possible

```python
from pydantic import BaseModel, Field

class OrderItemV1(BaseModel):
    """v1 order item (deprecated)."""
    product_id: str  # Old field name

class OrderItemV2(BaseModel):
    """v2 order item (current)."""
    sku: str = Field(..., alias="product_id")  # Accept both names

# Response can include both for gradual migration
class OrderResponse(BaseModel):
    items: list[OrderItemV2]

    # Include legacy field for v1 clients
    @property
    def items_v1(self):
        return [{"product_id": item.sku} for item in self.items]
```

### 5. Test All Supported Versions

```python
import pytest
from httpx import AsyncClient

API_VERSIONS = ["v1", "v2"]

@pytest.fixture(params=API_VERSIONS)
def api_version(request):
    return request.param

@pytest.mark.asyncio
async def test_get_user(client: AsyncClient, api_version: str):
    """Test get user works on all supported versions."""
    response = await client.get(f"/api/{api_version}/users/123")
    assert response.status_code == 200

    # Version-specific assertions
    if api_version == "v1":
        assert "profile" in response.json()
    else:
        assert "settings" in response.json()
```
