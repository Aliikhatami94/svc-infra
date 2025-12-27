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

## External Admin UI Integration

### React Admin

[React Admin](https://marmelab.com/react-admin/) is a popular admin framework that works well with svc-infra's REST patterns.

#### Data Provider Setup

```typescript
// src/dataProvider.ts
import { fetchUtils } from 'react-admin';
import simpleRestDataProvider from 'ra-data-simple-rest';

const httpClient = (url: string, options: fetchUtils.Options = {}) => {
    const token = localStorage.getItem('admin_token');
    const headers = new Headers(options.headers);
    headers.set('Authorization', `Bearer ${token}`);
    headers.set('Accept', 'application/json');
    return fetchUtils.fetchJson(url, { ...options, headers });
};

export const dataProvider = simpleRestDataProvider(
    'https://api.example.com/admin',
    httpClient
);
```

#### Authentication Provider

```typescript
// src/authProvider.ts
import { AuthProvider } from 'react-admin';

export const authProvider: AuthProvider = {
    login: async ({ username, password }) => {
        const response = await fetch('/api/v1/auth/login', {
            method: 'POST',
            body: JSON.stringify({ email: username, password }),
            headers: { 'Content-Type': 'application/json' },
        });
        if (response.status < 200 || response.status >= 300) {
            throw new Error('Login failed');
        }
        const { access_token } = await response.json();
        localStorage.setItem('admin_token', access_token);
    },
    logout: () => {
        localStorage.removeItem('admin_token');
        return Promise.resolve();
    },
    checkAuth: () => {
        return localStorage.getItem('admin_token')
            ? Promise.resolve()
            : Promise.reject();
    },
    checkError: (error) => {
        if (error.status === 401 || error.status === 403) {
            localStorage.removeItem('admin_token');
            return Promise.reject();
        }
        return Promise.resolve();
    },
    getPermissions: async () => {
        const token = localStorage.getItem('admin_token');
        if (!token) return [];
        const payload = JSON.parse(atob(token.split('.')[1]));
        return payload.roles || [];
    },
};
```

#### User Resource

```typescript
// src/resources/users.tsx
import { List, Datagrid, TextField, EmailField, DateField, Edit, SimpleForm, TextInput, BooleanField, BooleanInput } from 'react-admin';

export const UserList = () => (
    <List>
        <Datagrid rowClick="edit">
            <TextField source="id" />
            <EmailField source="email" />
            <TextField source="first_name" />
            <TextField source="last_name" />
            <BooleanField source="is_active" />
            <DateField source="created_at" />
        </Datagrid>
    </List>
);

export const UserEdit = () => (
    <Edit>
        <SimpleForm>
            <TextInput source="email" disabled />
            <TextInput source="first_name" />
            <TextInput source="last_name" />
            <BooleanInput source="is_active" />
        </SimpleForm>
    </Edit>
);
```

### Retool

[Retool](https://retool.com/) connects directly to your API. Configure these settings:

```yaml
# Retool Resource Configuration
resource_type: REST API
base_url: https://api.example.com
auth_type: Bearer Token
headers:
  Content-Type: application/json
  Accept: application/json
```

#### Common Query Examples

```javascript
// List users with pagination
GET /admin/users?page={{ table1.page }}&per_page={{ table1.pageSize }}

// Search users
GET /admin/users?email={{ textInput1.value }}

// Update user
PATCH /admin/users/{{ table1.selectedRow.id }}
Body: { "is_active": {{ switch1.value }} }
```

### Appsmith

[Appsmith](https://www.appsmith.com/) is an open-source alternative. Setup:

```javascript
// API Configuration
export default {
    baseUrl: 'https://api.example.com',
    headers: {
        'Authorization': `Bearer ${appsmith.store.adminToken}`,
        'Content-Type': 'application/json',
    },
};

// Users query
export const getUsers = () => Api1.run({
    method: 'GET',
    url: '/admin/users',
    params: {
        page: Table1.pageNo,
        per_page: Table1.pageSize,
    },
});
```

### Backend Routes for Admin UIs

Add dedicated admin endpoints that match common admin UI expectations:

```python
from fastapi import APIRouter, Query, Depends
from svc_infra.api.fastapi.admin import admin_router
from svc_infra.security.permissions import RequirePermission

router = admin_router(prefix="/admin", tags=["admin"])

@router.get("/users", dependencies=[RequirePermission("user.read")])
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    email: str | None = None,
    is_active: bool | None = None,
    session = Depends(get_session),
):
    """List users with filtering and pagination for admin UIs."""
    stmt = select(User)
    if email:
        stmt = stmt.where(User.email.ilike(f"%{email}%"))
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)

    # Get total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar()

    # Apply pagination
    offset = (page - 1) * per_page
    stmt = stmt.offset(offset).limit(per_page)
    result = await session.execute(stmt)
    users = result.scalars().all()

    return {
        "data": [user.to_dict() for user in users],
        "total": total,
        "page": page,
        "per_page": per_page,
    }

@router.get("/users/{user_id}", dependencies=[RequirePermission("user.read")])
async def get_user(user_id: str, session = Depends(get_session)):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return {"data": user.to_dict()}

@router.patch("/users/{user_id}", dependencies=[RequirePermission("user.write")])
async def update_user(
    user_id: str,
    updates: UserUpdateSchema,
    session = Depends(get_session),
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    for field, value in updates.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    await session.commit()
    return {"data": user.to_dict()}
```

---

## Audit Log Querying

### Hash-Chain Verification

svc-infra uses hash-chain audit logs for tamper detection:

```python
from svc_infra.security.audit_service import verify_chain_for_tenant

# Verify all events for a tenant
ok, broken_indices = await verify_chain_for_tenant(session, tenant_id="t_123")
if not ok:
    logger.critical(f"Audit log tampering detected at indices: {broken_indices}")
    await alert_security_team(tenant_id, broken_indices)
```

### Querying Audit Events

```python
from sqlalchemy import select, and_
from svc_infra.security.models import AuditLog
from datetime import datetime, timedelta

# Recent impersonation events
async def get_impersonation_events(
    session,
    days: int = 30,
    limit: int = 100,
) -> list[AuditLog]:
    cutoff = datetime.utcnow() - timedelta(days=days)
    stmt = (
        select(AuditLog)
        .where(and_(
            AuditLog.event_type.in_([
                "admin.impersonation.started",
                "admin.impersonation.stopped"
            ]),
            AuditLog.ts >= cutoff,
        ))
        .order_by(AuditLog.ts.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())

# Events by actor
async def get_actor_activity(
    session,
    actor_id: str,
    event_types: list[str] | None = None,
) -> list[AuditLog]:
    stmt = select(AuditLog).where(AuditLog.actor_id == actor_id)
    if event_types:
        stmt = stmt.where(AuditLog.event_type.in_(event_types))
    stmt = stmt.order_by(AuditLog.ts.desc()).limit(500)
    result = await session.execute(stmt)
    return list(result.scalars().all())

# Events for a resource
async def get_resource_history(
    session,
    resource_ref: str,
) -> list[AuditLog]:
    stmt = (
        select(AuditLog)
        .where(AuditLog.resource_ref == resource_ref)
        .order_by(AuditLog.ts.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
```

### Compliance Reports

#### Monthly Admin Activity Report

```python
from sqlalchemy import select, func
from collections import defaultdict

async def generate_admin_activity_report(
    session,
    year: int,
    month: int,
) -> dict:
    """Generate monthly summary of admin activities."""
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)

    stmt = (
        select(AuditLog)
        .where(and_(
            AuditLog.ts >= start,
            AuditLog.ts < end,
            AuditLog.event_type.like("admin.%"),
        ))
        .order_by(AuditLog.ts.asc())
    )
    result = await session.execute(stmt)
    events = list(result.scalars().all())

    # Group by actor
    by_actor = defaultdict(list)
    for e in events:
        by_actor[e.actor_id].append(e)

    # Group by event type
    by_type = defaultdict(int)
    for e in events:
        by_type[e.event_type] += 1

    # Impersonation summary
    impersonations = [e for e in events if "impersonation" in e.event_type]
    unique_targets = set(
        e.event_metadata.get("target_id")
        for e in impersonations
        if e.event_metadata
    )

    return {
        "period": f"{year}-{month:02d}",
        "total_events": len(events),
        "unique_actors": len(by_actor),
        "events_by_type": dict(by_type),
        "impersonation_count": len([e for e in impersonations if e.event_type == "admin.impersonation.started"]),
        "unique_impersonation_targets": len(unique_targets),
        "actors": [
            {
                "actor_id": actor_id,
                "event_count": len(actor_events),
                "event_types": list(set(e.event_type for e in actor_events)),
            }
            for actor_id, actor_events in by_actor.items()
        ],
    }
```

#### Audit Export for DSAR

```python
async def export_audit_for_dsar(
    session,
    user_id: str,
) -> list[dict]:
    """Export all audit events related to a user for Data Subject Access Request."""
    # Events where user was the actor
    actor_events = await session.execute(
        select(AuditLog).where(AuditLog.actor_id == user_id)
    )

    # Events where user was the target (impersonation, profile updates, etc.)
    target_events = await session.execute(
        select(AuditLog).where(
            AuditLog.resource_ref.like(f"user:{user_id}%")
        )
    )

    all_events = list(actor_events.scalars()) + list(target_events.scalars())
    all_events.sort(key=lambda e: e.ts)

    return [
        {
            "timestamp": e.ts.isoformat(),
            "event_type": e.event_type,
            "resource": e.resource_ref,
            "metadata": e.event_metadata,
        }
        for e in all_events
    ]
```

---

## Impersonation Cookbook

### Common Use Cases

#### 1. Debugging User-Reported Issues

```python
# Support workflow
@router.post("/support/investigate")
async def investigate_user_issue(
    ticket_id: str,
    user_id: str,
    request: Request,
    session = Depends(get_session),
    principal = Depends(RequirePermission("admin.impersonate")),
):
    """Start investigation with automatic audit trail."""
    # Fetch ticket for reason
    ticket = await get_support_ticket(session, ticket_id)

    # Log investigation start
    await append_audit_event(
        session,
        actor_id=principal.user.id,
        event_type="support.investigation.started",
        resource_ref=f"ticket:{ticket_id}",
        metadata={
            "target_user_id": user_id,
            "ticket_summary": ticket.summary,
        },
    )

    # Start impersonation
    response = await start_impersonation(
        request,
        user_id=user_id,
        reason=f"Support ticket #{ticket_id}: {ticket.summary}",
    )

    return response
```

#### 2. Verifying User Permissions

```python
@router.get("/admin/verify-access/{user_id}")
async def verify_user_access(
    user_id: str,
    resource_type: str,
    resource_id: str,
    session = Depends(get_session),
    principal = Depends(RequirePermission("admin.impersonate")),
):
    """Check what a user can access without full impersonation."""
    user = await get_user(session, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    # Create temporary principal for the target user
    target_principal = Identity(user=user)
    perms = principal_permissions(target_principal)

    # Check specific resource access
    resource = await get_resource(session, resource_type, resource_id)
    can_access = await check_resource_access(target_principal, resource)

    return {
        "user_id": user_id,
        "permissions": list(perms),
        "resource": f"{resource_type}:{resource_id}",
        "can_access": can_access,
    }
```

#### 3. Bulk User Operations

```python
@router.post("/admin/bulk-action")
async def bulk_user_action(
    user_ids: list[str],
    action: str,  # "deactivate", "reset_mfa", "force_logout"
    reason: str,
    session = Depends(get_session),
    principal = Depends(RequirePermission("user.write")),
):
    """Perform bulk operations with comprehensive audit trail."""
    results = []

    for user_id in user_ids:
        try:
            if action == "deactivate":
                await deactivate_user(session, user_id)
            elif action == "reset_mfa":
                await reset_user_mfa(session, user_id)
            elif action == "force_logout":
                await revoke_all_sessions(session, user_id)

            await append_audit_event(
                session,
                actor_id=principal.user.id,
                event_type=f"admin.user.{action}",
                resource_ref=f"user:{user_id}",
                metadata={"reason": reason, "bulk_operation": True},
            )
            results.append({"user_id": user_id, "status": "success"})
        except Exception as e:
            results.append({"user_id": user_id, "status": "failed", "error": str(e)})

    await session.commit()

    return {
        "action": action,
        "total": len(user_ids),
        "successful": len([r for r in results if r["status"] == "success"]),
        "results": results,
    }
```

#### 4. Tenant-Scoped Admin Access

```python
from svc_infra.tenancy import TenantId

@router.get("/admin/tenant/{tenant_id}/users")
async def list_tenant_users(
    tenant_id: str,
    session = Depends(get_session),
    principal = Depends(RequirePermission("user.read")),
):
    """List users for a specific tenant (super-admin only)."""
    # Verify admin has cross-tenant access
    if not has_permission(principal, "admin.cross_tenant"):
        # Check if admin belongs to this tenant
        admin_tenant = getattr(principal.user, "tenant_id", None)
        if admin_tenant != tenant_id:
            raise HTTPException(403, "Cannot access other tenant's users")

    stmt = select(User).where(User.tenant_id == tenant_id)
    result = await session.execute(stmt)
    users = result.scalars().all()

    return {"tenant_id": tenant_id, "users": [u.to_dict() for u in users]}
```

---

## Further Reading

- [Security & Auth Hardening](./security.md)
- [Permissions & RBAC](./security.md#permissions-and-rbac)
- [Audit Logging](./security.md#audit-logging)
- [Observability](./observability.md)
