# Multi-Tenant Architecture

**svc-infra** provides a soft-tenant isolation model where all tenants share the same database schema, with automatic scoping by a `tenant_id` column. This approach balances isolation with operational simplicity.

---

## Quick Start

```python
from fastapi import FastAPI, Depends
from svc_infra.api.fastapi.tenancy.add import add_tenancy
from svc_infra.api.fastapi.tenancy.context import TenantId, OptionalTenantId

app = FastAPI()

# Enable tenancy middleware
add_tenancy(app)

@app.get("/items")
async def list_items(tenant_id: TenantId):
    """TenantId is a required dependency - raises 400 if missing."""
    return {"tenant": tenant_id, "items": []}

@app.get("/public")
async def public_endpoint(tenant_id: str | None = Depends(OptionalTenantId)):
    """OptionalTenantId allows anonymous access."""
    return {"tenant": tenant_id or "anonymous"}
```

---

## Core Concepts

### Tenant Resolution Order

The SDK resolves tenant ID through a configurable priority chain:

```
1. Global Override Hook  →  set_tenant_resolver()
         ↓
2. Auth Identity         →  user.tenant_id or api_key.tenant_id
         ↓
3. HTTP Header          →  X-Tenant-Id
         ↓
4. Request State        →  request.state.tenant_id
```

Each step is attempted in order. The first non-null value becomes the active tenant.

### Dependencies

| Dependency | Behavior | Use Case |
|------------|----------|----------|
| `TenantId` | Raises HTTP 400 if no tenant resolved | Protected endpoints |
| `OptionalTenantId` | Returns `None` if no tenant resolved | Public endpoints, admin routes |

```python
from svc_infra.api.fastapi.tenancy.context import TenantId

# TenantId = Annotated[str, Depends(require_tenant_id)]
async def protected_route(tenant_id: TenantId):
    # tenant_id is guaranteed non-null here
    ...
```

---

## Configuration

### Basic Setup

```python
from fastapi import FastAPI
from svc_infra.api.fastapi.tenancy.add import add_tenancy

app = FastAPI()
add_tenancy(app)
```

### Custom Resolver

Override the default resolution logic with a custom resolver:

```python
from fastapi import FastAPI, Request
from svc_infra.api.fastapi.tenancy.add import add_tenancy

def my_resolver(request: Request, identity, header: str | None) -> str | None:
    """Custom tenant resolution logic."""
    # Priority 1: Subdomain extraction
    host = request.headers.get("host", "")
    if "." in host:
        subdomain = host.split(".")[0]
        if subdomain not in ("www", "api"):
            return subdomain

    # Priority 2: Auth identity
    if identity and hasattr(identity, "user") and identity.user:
        return getattr(identity.user, "tenant_id", None)

    # Priority 3: Header fallback
    return header

app = FastAPI()
add_tenancy(app, resolver=my_resolver)
```

### Async Resolver

The resolver can be async for database lookups:

```python
async def async_resolver(request: Request, identity, header: str | None) -> str | None:
    """Async resolver for database-backed tenant lookup."""
    if header:
        # Verify tenant exists in database
        tenant = await get_tenant_by_slug(header)
        return tenant.id if tenant else None
    return None

add_tenancy(app, resolver=async_resolver)
```

---

## Database Integration

### TenantSqlService

Automatically scopes all CRUD operations to the current tenant:

```python
from svc_infra.db.sql.tenant import TenantSqlService
from svc_infra.db.sql.repository import SqlRepository

# Your model with tenant_id column
class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    name = Column(String)

# Repository setup
repo = SqlRepository(Item)

# Tenant-scoped service
async def get_service(tenant_id: TenantId, session: SqlSessionDep):
    return TenantSqlService(repo, tenant_id=tenant_id, tenant_field="tenant_id")
```

**Automatic Behaviors:**

| Operation | Behavior |
|-----------|----------|
| `list()` | Adds `WHERE tenant_id = :tenant_id` |
| `get()` | Adds tenant filter to prevent cross-tenant reads |
| `create()` | Injects `tenant_id` if not set in data |
| `update()` | Scopes to tenant, prevents cross-tenant updates |
| `delete()` | Scopes to tenant, prevents cross-tenant deletes |
| `search()` | Adds tenant filter to search queries |
| `count()` | Counts only tenant's records |

### Implementation Details

```python
class TenantSqlService(SqlService):
    def __init__(self, repo, *, tenant_id: str, tenant_field: str = "tenant_id"):
        super().__init__(repo)
        self.tenant_id = tenant_id
        self.tenant_field = tenant_field

    def _where(self) -> Sequence[Any]:
        """Build tenant filter clause."""
        model = self.repo.model
        col = getattr(model, self.tenant_field, None)
        if col is None:
            return []
        return [col == self.tenant_id]

    async def create(self, session: AsyncSession, data: dict[str, Any]):
        data = await self.pre_create(data)
        # Auto-inject tenant_id if model has the column
        if self.tenant_field in self.repo._model_columns() and self.tenant_field not in data:
            data[self.tenant_field] = self.tenant_id
        return await self.repo.create(session, data)
```

### SqlResource with Tenant Scoping

Define resources that auto-configure tenant scoping:

```python
from svc_infra.db.sql.resource import SqlResource

class ItemResource(SqlResource):
    model = Item
    read_schema = ItemRead
    create_schema = ItemCreate
    update_schema = ItemUpdate
    tenant_field = "tenant_id"  # Enables tenant CRUD router
```

When `tenant_field` is set, `make_crud_router_tenant` automatically requires `TenantId` and scopes all operations.

---

## CRUD Router Integration

### Tenant-Scoped Router

Use `make_crud_router_tenant` for automatic tenant scoping:

```python
from svc_infra.api.fastapi.db.sql.crud_router import make_crud_router_tenant

router = make_crud_router_tenant(
    model=Item,
    service_factory=lambda: ItemService(),
    read_schema=ItemRead,
    create_schema=ItemCreate,
    update_schema=ItemUpdate,
    prefix="/items",
    tenant_field="tenant_id",
)

# All routes now require TenantId:
# GET  /items       → lists only tenant's items
# POST /items       → creates with tenant_id injected
# GET  /items/{id}  → returns 404 if item belongs to different tenant
# PUT  /items/{id}  → updates only if item belongs to tenant
# DELETE /items/{id} → deletes only if item belongs to tenant
```

### Manual Tenant Injection

For custom routes, inject tenant manually:

```python
from svc_infra.api.fastapi.tenancy.context import TenantId

@router.post("/bulk-import")
async def bulk_import(
    items: list[ItemCreate],
    tenant_id: TenantId,
    session: SqlSessionDep,
):
    svc = TenantSqlService(item_repo, tenant_id=tenant_id)
    results = []
    for item in items:
        created = await svc.create(session, item.model_dump())
        results.append(created)
    await session.commit()
    return {"imported": len(results)}
```

---

## Rate Limiting by Tenant

Apply per-tenant rate limits:

```python
from svc_infra.api.fastapi.dependencies.ratelimit import RateLimiter

# Global limiter with tenant scoping
tenant_limiter = RateLimiter(
    limit=100,
    window=60,
    scope_by_tenant=True,  # Each tenant gets their own bucket
)

# Custom limit per tenant
def tenant_limit_resolver(request, tenant_id: str | None) -> int | None:
    """Return custom limit based on tenant tier."""
    if tenant_id:
        tier = get_tenant_tier(tenant_id)  # Your lookup logic
        return {"free": 10, "pro": 100, "enterprise": 1000}.get(tier, 10)
    return 10  # Default for anonymous

dynamic_limiter = RateLimiter(
    limit=100,  # Fallback
    window=60,
    scope_by_tenant=True,
    limit_resolver=tenant_limit_resolver,
)

@app.get("/api/resource", dependencies=[Depends(tenant_limiter)])
async def rate_limited_endpoint():
    return {"status": "ok"}
```

### How Tenant Rate Limiting Works

```python
class RateLimiter:
    async def __call__(self, request: Request):
        tenant_id = None
        if self.scope_by_tenant:
            tenant_id = await resolve_tenant_id(request)

        key = self.key_fn(request)
        if self.scope_by_tenant and tenant_id:
            key = f"{key}:tenant:{tenant_id}"  # Tenant-scoped key

        # Resolve per-tenant limit if configured
        eff_limit = self.limit
        if self._limit_resolver:
            eff_limit = self._limit_resolver(request, tenant_id) or self.limit

        # Check and enforce limit
        count, _, reset = self.store.incr(str(key), self.window)
        if count > eff_limit:
            raise HTTPException(429, "Rate limit exceeded")
```

---

## Data Export

Export tenant-scoped data via CLI:

```bash
# Export all orders for a tenant
svc-infra sql export-tenant public.orders \
  --tenant-id tenant_abc \
  --output orders.json

# With row limit
svc-infra sql export-tenant public.items \
  --tenant-id tenant_abc \
  --limit 1000

# Custom tenant field name
svc-infra sql export-tenant public.legacy_data \
  --tenant-id tenant_abc \
  --tenant-field organization_id
```

---

## Model Design Patterns

### Standard Tenant Model

```python
from sqlalchemy import Column, String, Integer, DateTime, func
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class TenantMixin:
    """Mixin for tenant-scoped models."""
    tenant_id = Column(String, nullable=False, index=True)

class TimestampMixin:
    """Mixin for audit timestamps."""
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

class Item(Base, TenantMixin, TimestampMixin):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
```

### Composite Index for Query Performance

```python
from sqlalchemy import Index

class Item(Base, TenantMixin):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    status = Column(String)

    __table_args__ = (
        # Composite index for tenant-scoped queries
        Index("ix_items_tenant_status", "tenant_id", "status"),
        Index("ix_items_tenant_created", "tenant_id", "created_at"),
    )
```

### Soft Delete with Tenant Scoping

```python
class SoftDeleteTenantMixin(TenantMixin):
    """Soft delete with tenant isolation."""
    deleted_at = Column(DateTime, nullable=True)

    @classmethod
    def active_filter(cls):
        return [cls.deleted_at.is_(None)]
```

---

## Migration Strategies

### Adding Tenant Column to Existing Table

```python
# migrations/versions/xxx_add_tenant_id.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    # 1. Add column as nullable first
    op.add_column('items', sa.Column('tenant_id', sa.String(), nullable=True))

    # 2. Backfill with default tenant
    op.execute("UPDATE items SET tenant_id = 'default' WHERE tenant_id IS NULL")

    # 3. Make non-nullable
    op.alter_column('items', 'tenant_id', nullable=False)

    # 4. Add index for query performance
    op.create_index('ix_items_tenant_id', 'items', ['tenant_id'])

def downgrade():
    op.drop_index('ix_items_tenant_id', 'items')
    op.drop_column('items', 'tenant_id')
```

### Tenant Data Partitioning

For very large tenants, consider PostgreSQL partitioning:

```sql
-- Create partitioned table
CREATE TABLE items (
    id SERIAL,
    tenant_id VARCHAR NOT NULL,
    name VARCHAR,
    created_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (id, tenant_id)
) PARTITION BY LIST (tenant_id);

-- Create partitions for large tenants
CREATE TABLE items_tenant_large PARTITION OF items
    FOR VALUES IN ('large_tenant_id');

-- Default partition for others
CREATE TABLE items_default PARTITION OF items
    DEFAULT;
```

---

## Testing

### Mocking Tenant Context

```python
import pytest
from fastapi.testclient import TestClient
from svc_infra.api.fastapi.tenancy.context import set_tenant_resolver

@pytest.fixture
def tenant_a_client(app):
    """Client with tenant A context."""
    def resolver(request, identity, header):
        return "tenant_a"
    set_tenant_resolver(resolver)
    yield TestClient(app)
    set_tenant_resolver(None)  # Clean up

@pytest.fixture
def tenant_b_client(app):
    """Client with tenant B context."""
    def resolver(request, identity, header):
        return "tenant_b"
    set_tenant_resolver(resolver)
    yield TestClient(app)
    set_tenant_resolver(None)

def test_tenant_isolation(tenant_a_client, tenant_b_client):
    # Create item as tenant A
    resp = tenant_a_client.post("/items", json={"name": "A's item"})
    item_id = resp.json()["id"]

    # Tenant A can see it
    resp = tenant_a_client.get(f"/items/{item_id}")
    assert resp.status_code == 200

    # Tenant B cannot see it
    resp = tenant_b_client.get(f"/items/{item_id}")
    assert resp.status_code == 404
```

### Header-Based Testing

```python
def test_tenant_via_header(client):
    # Use X-Tenant-Id header
    resp = client.get("/items", headers={"X-Tenant-Id": "test_tenant"})
    assert resp.status_code == 200
```

---

## Production Recommendations

### Security Checklist

- [ ] **Never trust client-provided tenant IDs** in production without verification
- [ ] Use auth identity as primary tenant source, not headers
- [ ] Implement tenant existence validation in custom resolvers
- [ ] Log tenant context in all audit trails
- [ ] Add tenant_id to database indexes for all tenant-scoped tables

### Performance Considerations

```python
# ✅ Good: Composite indexes for common query patterns
Index("ix_items_tenant_status", "tenant_id", "status")
Index("ix_items_tenant_created", "tenant_id", "created_at", postgresql_using="btree")

# ✅ Good: Partition large tables by tenant
# See Migration Strategies section

# ❌ Avoid: Full table scans without tenant filter
# All queries should include tenant_id WHERE clause
```

### Monitoring

Track per-tenant metrics:

```python
from svc_infra.obs.metrics import Counter

tenant_requests = Counter(
    "tenant_requests_total",
    "Total requests per tenant",
    labels=["tenant_id", "endpoint"],
)

@app.middleware("http")
async def track_tenant_requests(request: Request, call_next):
    tenant_id = await resolve_tenant_id(request) or "unknown"
    response = await call_next(request)
    tenant_requests.inc(tenant_id=tenant_id, endpoint=request.url.path)
    return response
```

---

## Troubleshooting

### "tenant_context_missing" Error

**Cause:** Endpoint requires `TenantId` but no tenant could be resolved.

**Solutions:**
1. Ensure client sends `X-Tenant-Id` header
2. Verify auth token includes tenant_id claim
3. Check custom resolver isn't returning None unexpectedly
4. Use `OptionalTenantId` for public endpoints

### Cross-Tenant Data Leakage

**Prevention:**
1. Always use `TenantSqlService` or tenant-scoped routers
2. Never construct raw SQL without tenant filter
3. Add database-level row security if available:

```sql
-- PostgreSQL Row Level Security
ALTER TABLE items ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON items
    USING (tenant_id = current_setting('app.tenant_id'));
```

### Tenant Resolution Not Working

Debug tenant resolution:

```python
from svc_infra.api.fastapi.tenancy.context import resolve_tenant_id

@app.get("/debug/tenant")
async def debug_tenant(request: Request):
    tenant_id = await resolve_tenant_id(request)
    return {
        "resolved_tenant": tenant_id,
        "header": request.headers.get("X-Tenant-Id"),
        "state": getattr(request.state, "tenant_id", None),
    }
```

---

## API Reference

### add_tenancy

```python
def add_tenancy(
    app: FastAPI,
    *,
    resolver: Callable[..., Any] | None = None
) -> None:
    """Wire tenancy resolver for the application.

    Args:
        app: FastAPI application instance
        resolver: Optional (request, identity, header) -> str | None
    """
```

### resolve_tenant_id

```python
async def resolve_tenant_id(
    request: Request,
    tenant_header: str | None = None,
    identity: Any = Depends(OptionalIdentity),
) -> str | None:
    """Resolve tenant id from override, identity, header, or request.state."""
```

### TenantSqlService

```python
class TenantSqlService(SqlService):
    """SQL service wrapper that automatically scopes operations to a tenant."""

    def __init__(
        self,
        repo,
        *,
        tenant_id: str,
        tenant_field: str = "tenant_id"
    ):
        """
        Args:
            repo: SqlRepository instance
            tenant_id: Active tenant identifier
            tenant_field: Column name for tenant filtering
        """
```

### RateLimiter (tenant-aware)

```python
class RateLimiter:
    def __init__(
        self,
        *,
        limit: int,
        window: int = 60,
        key_fn: Callable = lambda r: "global",
        limit_resolver: Callable[[Request, str | None], int | None] | None = None,
        scope_by_tenant: bool = False,
        store: RateLimitStore | None = None,
    ):
        """
        Args:
            limit: Default rate limit count
            window: Time window in seconds
            key_fn: Function to generate rate limit key
            limit_resolver: (request, tenant_id) -> custom limit
            scope_by_tenant: Whether to create per-tenant buckets
            store: Rate limit storage backend
        """
```

---

## See Also

- [Auth Guide](auth.md) — Authentication and identity
- [Database Guide](database.md) — SQL service patterns
- [CLI Reference](cli.md) — export-tenant command
- [Rate Limiting](auth.md#rate-limiting) — Request throttling
