# Admin Scope & Operations

This guide covers the admin subsystem: admin-only routes, permissions, impersonation, and operational guardrails.

## Overview

The admin module provides:
- **Admin router pattern**: Role-gated endpoints under `/admin` with fine-grained permission checks
- **Impersonation**: Controlled user impersonation for support and debugging with full audit trails
- **Permission alignment**: `admin.impersonate` permission integrated with the RBAC system
- **Easy integration**: One-line setup via `add_admin(app, ...)`

## Quick Start

### Basic Setup

```python
from fastapi import FastAPI
from svc_infra.api.fastapi.admin import add_admin

app = FastAPI()

# Mount admin endpoints with defaults
add_admin(app)

# Endpoints are now available:
# POST /admin/impersonate/start
# POST /admin/impersonate/stop
```

### Custom User Loader

If you have a custom user model or retrieval logic:

```python
from fastapi import Request

async def my_user_getter(request: Request, user_id: str):
    # Your custom user loading logic
    user = await my_user_service.get_user(user_id)
    if not user:
        raise HTTPException(404, "user_not_found")
    return user

add_admin(app, impersonation_user_getter=my_user_getter)
```

### Configuration

Environment variables:

- `ADMIN_IMPERSONATION_SECRET`: Secret for signing impersonation tokens (falls back to `APP_SECRET` or `"dev-secret"`)
- `ADMIN_IMPERSONATION_TTL`: Token TTL in seconds (default: 900 = 15 minutes)
- `ADMIN_IMPERSONATION_COOKIE`: Cookie name (default: `"impersonation"`)

Function parameters:

```python
add_admin(
    app,
    base_path="/admin",              # Base path for admin routes
    enable_impersonation=True,        # Enable impersonation endpoints
    secret=None,                      # Override token signing secret
    ttl_seconds=15 * 60,              # Token TTL (15 minutes)
    cookie_name="impersonation",      # Cookie name
    impersonation_user_getter=None,   # Custom user loader
)
```

## Permissions & RBAC

### Admin Role

The `admin` role includes the following permissions by default:

- `user.read`, `user.write`: User management
- `billing.read`, `billing.write`: Billing operations
- `security.session.list`, `security.session.revoke`: Session management
- `admin.impersonate`: User impersonation

### Permission Guards

Admin endpoints use layered guards:

1. **Role gate** at router level: `RequireRoles("admin")`
2. **Permission gate** at endpoint level: `RequirePermission("admin.impersonate")`

This ensures both coarse-grained role membership and fine-grained permission enforcement.

### Custom Admin Routes

```python
from svc_infra.api.fastapi.admin import admin_router
from svc_infra.security.permissions import RequirePermission

# Create an admin-only router
router = admin_router(prefix="/admin", tags=["admin"])

@router.get("/analytics", dependencies=[RequirePermission("analytics.read")])
async def admin_analytics():
    return {"data": "..."}

app.include_router(router)
```

## Impersonation

### Use Cases

- **Customer support**: Debug issues as the affected user
- **Testing**: Verify permission boundaries and user-specific behavior
- **Compliance**: Audit access patterns under controlled conditions

### Workflow

#### 1. Start Impersonation

```bash
POST /admin/impersonate/start
Content-Type: application/json

{
  "user_id": "u-12345",
  "reason": "Investigating billing issue #789"
}
```

**Requirements:**
- Authenticated user must have `admin` role
- User must have `admin.impersonate` permission
- `reason` field is mandatory

**Response:** `204 No Content` with impersonation cookie set

#### 2. Make Requests as Impersonated User

All subsequent requests will be made as the target user while preserving the admin's permissions for authorization checks:

```bash
GET /api/v1/profile
Cookie: impersonation=<token>

# Returns the impersonated user's profile
```

**Behavior:**
- `request.user` reflects the impersonated user
- `request.user.roles` inherits the actor's roles (admin maintains permissions)
- `principal.via` is set to `"impersonated"` for tracking

#### 3. Stop Impersonation

```bash
POST /admin/impersonate/stop

# Response: 204 No Content
# Cookie deleted, subsequent requests use original identity
```

### Security Guardrails

#### Short TTL
- Default: 15 minutes
- No sliding refresh: token expires after TTL regardless of activity
- Rationale: Minimize blast radius of compromised impersonation sessions

#### Explicit Reason
- Required for every impersonation start
- Logged in audit trail for compliance and forensics

#### Audit Trail
Every impersonation action is logged with:
- `admin.impersonation.started`: actor, target, reason, expiry
- `admin.impersonation.stopped`: termination reason (manual/expired)

Example log entry:
```json
{
  "message": "admin.impersonation.started",
  "actor_id": "u-admin-42",
  "target_id": "u-12345",
  "reason": "Investigating billing issue #789",
  "expires_in": 900,
  "timestamp": "2025-11-01T12:00:00Z"
}
```

#### Token Security
- HMAC-SHA256 signed tokens with nonce
- Includes: actor_id, target_id, issued_at, expires_at, nonce
- Tamper detection via signature verification
- Cookie attributes:
  - `httponly=true`: No JavaScript access
  - `samesite=lax`: CSRF protection
  - `secure=true` in production: HTTPS only

#### Permission Preservation
- Impersonated requests maintain the actor's permissions
- Prevents privilege escalation by impersonating a higher-privileged user
- Target user context for data scoping, actor permissions for authorization

### Operational Recommendations

#### Development
```python
# Relaxed for local testing
add_admin(
    app,
    secret="dev-secret",
    ttl_seconds=60 * 60,  # 1 hour for convenience
)
```

#### Production
```python
# Strict settings
add_admin(
    app,
    secret=os.environ["ADMIN_IMPERSONATION_SECRET"],  # Strong secret from vault
    ttl_seconds=15 * 60,  # 15 minutes max
)
```

**Best practices:**
- Rotate `ADMIN_IMPERSONATION_SECRET` periodically
- Monitor impersonation logs for anomalies
- Set up alerts for frequent impersonation by the same actor
- Consider org/tenant scoping for multi-tenant systems
- Document allowed impersonation reasons in your runbook

## Monitoring & Observability

### Metrics

Label admin routes with `route_class=admin` for SLO tracking:

```python
from svc_infra.obs.add import add_observability

def route_classifier(path: str) -> str:
    if path.startswith("/admin"):
        return "admin"
    # ... other classifications
    return "public"

add_observability(app, route_classifier=route_classifier)
```

### Audit Log Queries

Search for impersonation events:
```python
# Example: Query structured logs
logs.filter(message="admin.impersonation.started") \
    .filter(actor_id="u-admin-42") \
    .order_by(timestamp.desc()) \
    .limit(100)
```

Compliance report:
```python
# Generate monthly impersonation summary
impersonations = audit_log.filter(
    event_type__in=["admin.impersonation.started", "admin.impersonation.stopped"],
    timestamp__gte=start_of_month,
)
report = impersonations.group_by("actor_id").agg(count="id", targets=unique("target_id"))
```

## Testing

### Unit Tests

```python
import pytest
from svc_infra.api.fastapi.admin import add_admin

@pytest.mark.admin
def test_impersonation_requires_permission():
    app = make_test_app()
    add_admin(app, impersonation_user_getter=lambda req, uid: User(id=uid))

    # Without admin role → 403
    client = TestClient(app)
    r = client.post("/admin/impersonate/start", json={"user_id": "u-2", "reason": "test"})
    assert r.status_code == 403
```

### Acceptance Tests

```python
@pytest.mark.acceptance
@pytest.mark.admin
def test_impersonation_lifecycle(admin_client):
    # Start impersonation
    r = admin_client.post(
        "/admin/impersonate/start",
        json={"user_id": "u-target", "reason": "acceptance test"}
    )
    assert r.status_code == 204

    # Verify impersonated context
    profile = admin_client.get("/api/v1/profile")
    assert profile.json()["id"] == "u-target"

    # Stop impersonation
    r = admin_client.post("/admin/impersonate/stop")
    assert r.status_code == 204
```

Run admin tests:
```bash
pytest -m admin
```

## Troubleshooting

### Impersonation Not Working

**Symptom:** Impersonation cookie set but requests still use original identity

**Check:**
1. Cookie is being sent: verify `Cookie: impersonation=<token>` in request headers
2. Token is valid: check signature and expiry
3. User getter succeeds: ensure `impersonation_user_getter` doesn't raise exceptions
4. Dependency override is active: `add_admin` registers a global override on startup

**Debug:**
```python
# Enable debug logging
import logging
logging.getLogger("svc_infra.api.fastapi.admin").setLevel(logging.DEBUG)
```

### Permission Denied

**Symptom:** 403 when calling `/admin/impersonate/start`

**Check:**
1. User has `admin` role: verify `user.roles` includes `"admin"`
2. Permission registered: ensure `admin.impersonate` is in the permission registry
3. Permission assigned to role: check `PERMISSION_REGISTRY["admin"]` includes `"admin.impersonate"`

### Token Expired Too Soon

**Symptom:** Impersonation session ends before expected TTL

**Possible causes:**
1. TTL misconfigured: check `ADMIN_IMPERSONATION_TTL` environment variable
2. Server time skew: verify system clock is synchronized (NTP)
3. Cookie attributes: ensure `max_age` matches TTL

## Security Considerations

### Threat Model

| Threat | Mitigation |
|--------|-----------|
| Token theft (XSS) | `httponly=true` cookie prevents JavaScript access |
| Token theft (network) | `secure=true` requires HTTPS in production |
| CSRF attacks | `samesite=lax` prevents cross-site cookie sending |
| Privilege escalation | Actor permissions preserved during impersonation |
| Prolonged access | Short TTL (15 min default) with no refresh |
| Abuse detection | Audit logs with reason, actor, and target tracking |
| Insider threat | Required reason and comprehensive audit trail |

### Compliance

**SOC 2 / ISO 27001:**
- Audit trail requirement: ✅ All impersonation events logged
- Access justification: ✅ Mandatory `reason` field
- Time-bound access: ✅ Short TTL with no renewal
- Least privilege: ✅ Permission-based access control

**GDPR / Data Protection:**
- Lawful basis: Support/debugging under legitimate interest or contract performance
- Data minimization: Only necessary user context loaded
- Transparency: Log access for data subject access requests (DSAR)
- Documentation: This guide serves as basis for DPA documentation

## API Reference

### `add_admin(app, **kwargs)`

Wire admin endpoints and impersonation to a FastAPI app.

**Parameters:**
- `app` (FastAPI): Target application
- `base_path` (str): Admin router base path (default: `"/admin"`)
- `enable_impersonation` (bool): Enable impersonation endpoints (default: `True`)
- `secret` (str | None): Token signing secret (default: env `ADMIN_IMPERSONATION_SECRET`)
- `ttl_seconds` (int): Token TTL (default: `900` = 15 minutes)
- `cookie_name` (str): Cookie name (default: `"impersonation"`)
- `impersonation_user_getter` (Callable | None): Custom user loader `(request, user_id) -> user`

**Returns:** None (modifies app in place)

**Idempotency:** Safe to call multiple times; only wires once per app instance

### `admin_router(**kwargs)`

Create an admin-only router with role gate.

**Parameters:** Same as `APIRouter` (FastAPI)

**Returns:** APIRouter with `RequireRoles("admin")` dependency

**Example:**
```python
from svc_infra.api.fastapi.admin import admin_router

router = admin_router(prefix="/admin/reports", tags=["admin-reports"])

@router.get("/summary")
async def admin_summary():
    return {"total_users": 1234}
```

## Further Reading

- [ADR 0011: Admin scope and impersonation](../src/svc_infra/docs/adr/0011-admin-scope-and-impersonation.md)
- [Security & Auth Hardening](./security.md)
- [Permissions & RBAC](./security.md#permissions-and-rbac)
- [Audit Logging](./security.md#audit-logging)
- [Observability](./observability.md)
