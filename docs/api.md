# FastAPI Integration

svc-infra provides a comprehensive FastAPI integration layer with production-ready patterns for
application setup, dependency management, error handling, pagination, and middleware.

---

## Quick Start with `easy_service_app`

The `easy_service_app` factory creates a fully configured FastAPI application in one call:

```python
from svc_infra.api.fastapi import easy_service_app

app = easy_service_app(
    title="My Service",
    version="1.0.0",
    root_path="/api/v1",
)
```

This handles:

- OpenAPI documentation configuration
- CORS middleware with sensible defaults
- Health and readiness endpoints
- Structured logging integration
- Error handler registration (Problem+JSON)

### Environment Configuration

The application respects standard environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | Deployment environment (development, staging, production) | development |
| `DEBUG` | Enable debug mode | false |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins | * |
| `LOG_LEVEL` | Application log level | INFO |

```python
import os
from svc_infra.api.fastapi import easy_service_app

app = easy_service_app(
    title="My Service",
    version="1.0.0",
    debug=os.getenv("DEBUG", "false").lower() == "true",
)
```

---

## Integration Helpers (add_* Pattern)

svc-infra provides `add_*` helpers to wire up common infrastructure with minimal boilerplate.
Each helper adds routes, dependencies, and/or middleware to your FastAPI app.

### Storage Integration

```python
from svc_infra.api.fastapi import add_storage

add_storage(app, bucket="my-bucket", provider="s3")
# Adds: /upload, /download/{key}, /presign/{key}
```

**Routes added:**

- `POST /upload` — Upload file with optional metadata
- `GET /download/{key}` — Download file by key
- `GET /presign/{key}` — Generate presigned URL

### Document Store Integration

```python
from svc_infra.api.fastapi import add_documents

add_documents(app, collection="docs")
# Adds: /documents CRUD endpoints
```

**Routes added:**

- `POST /documents` — Create document
- `GET /documents/{id}` — Get document by ID
- `PUT /documents/{id}` — Update document
- `DELETE /documents/{id}` — Delete document
- `GET /documents` — List documents with pagination

### SQL Database Integration

```python
from svc_infra.api.fastapi import add_sql_db

add_sql_db(app, database_url="postgresql://...")
# Injects: db session dependency
```

**What it provides:**

- Connection pooling with configurable limits
- Session-per-request lifecycle
- Health check integration
- Automatic retry on transient failures

### Authentication Integration

```python
from svc_infra.api.fastapi import add_auth_users

add_auth_users(app, jwt_secret="...", algorithm="HS256")
# Adds: /auth/*, current_user dependency
```

**Routes added:**

- `POST /auth/login` — Authenticate and get tokens
- `POST /auth/refresh` — Refresh access token
- `POST /auth/logout` — Invalidate tokens
- `GET /auth/me` — Get current user

**Dependencies provided:**

```python
from svc_infra.api.fastapi import require_auth

@app.get("/protected")
async def protected(user = Depends(require_auth)):
    return {"user": user.id}
```

### Observability Integration

```python
from svc_infra.api.fastapi import add_observability

add_observability(app, service_name="my-service")
# Adds: /health, /ready, /metrics
```

**Routes added:**

- `GET /health` — Liveness check
- `GET /ready` — Readiness check with dependency verification
- `GET /metrics` — Prometheus-format metrics

### Webhook Integration

```python
from svc_infra.api.fastapi import add_webhooks

add_webhooks(app, secret="webhook-secret")
# Adds: /webhooks/* management endpoints
```

**Features:**

- Signature verification (HMAC-SHA256)
- Retry with exponential backoff
- Dead letter queue for failed deliveries
- Event filtering by type

### WebSocket Manager

```python
from svc_infra.api.fastapi import add_websocket_manager

manager = add_websocket_manager(app)

@app.websocket("/ws/{room}")
async def ws_endpoint(websocket, room: str):
    await manager.connect(websocket, room)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(room, data)
    finally:
        manager.disconnect(websocket, room)
```

### Background Jobs

```python
from svc_infra.api.fastapi import easy_jobs

job_system = easy_jobs(app, redis_url="redis://localhost")

@job_system.task
async def send_email(to: str, subject: str, body: str):
    # Background email sending
    pass

# Enqueue from endpoint
@app.post("/send-email")
async def trigger_email(to: str, subject: str, body: str):
    await send_email.delay(to=to, subject=subject, body=body)
    return {"status": "queued"}
```

---

## Object Router Pattern

Create full CRUD routers from Pydantic models:

```python
from svc_infra.api.fastapi import router_from_object
from pydantic import BaseModel

class Item(BaseModel):
    id: str
    name: str
    price: float

router = router_from_object(
    Item,
    prefix="/items",
    tags=["items"],
)
app.include_router(router)
```

This generates:

- `POST /items` — Create
- `GET /items/{id}` — Read
- `PUT /items/{id}` — Update
- `DELETE /items/{id}` — Delete
- `GET /items` — List with pagination

---

## Request/Response Validation

### Pydantic Model Patterns

Use strict typing for request validation:

```python
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

class CreateOrderRequest(BaseModel):
    product_id: str = Field(..., min_length=1, max_length=36)
    quantity: int = Field(..., ge=1, le=1000)
    notes: str | None = Field(None, max_length=500)

    @field_validator("product_id")
    @classmethod
    def validate_product_id(cls, v: str) -> str:
        if not v.startswith("prod_"):
            raise ValueError("product_id must start with 'prod_'")
        return v

class OrderResponse(BaseModel):
    id: str
    product_id: str
    quantity: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True  # For ORM model conversion
```

### Response Model Enforcement

Always specify response models for type safety and documentation:

```python
from fastapi import status

@app.post(
    "/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        422: {"description": "Validation error"},
        409: {"description": "Duplicate order"},
    },
)
async def create_order(req: CreateOrderRequest) -> OrderResponse:
    order = await order_service.create(req)
    return OrderResponse.from_orm(order)
```

### Custom Validators

```python
from pydantic import BaseModel, model_validator

class DateRangeRequest(BaseModel):
    start_date: datetime
    end_date: datetime

    @model_validator(mode="after")
    def validate_date_range(self) -> "DateRangeRequest":
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        if (self.end_date - self.start_date).days > 365:
            raise ValueError("Date range cannot exceed 365 days")
        return self
```

---

## Error Handling (Problem+JSON)

svc-infra uses RFC 9457 Problem Details for HTTP APIs for consistent error responses.

### Problem Response Format

All errors return a standardized structure:

```json
{
  "type": "https://api.example.com/errors/validation",
  "title": "Unprocessable Entity",
  "status": 422,
  "detail": "Validation failed.",
  "instance": "/api/v1/orders",
  "code": "VALIDATION_ERROR",
  "trace_id": "abc123",
  "errors": [
    {
      "loc": ["body", "quantity"],
      "msg": "ensure this value is greater than 0",
      "type": "value_error"
    }
  ]
}
```

### Automatic Handler Registration

Error handlers are registered automatically with `easy_service_app`:

```python
from svc_infra.api.fastapi import easy_service_app

app = easy_service_app(title="My Service")
# Problem+JSON handlers registered for:
# - HTTPException (4xx, 5xx)
# - RequestValidationError (422)
# - IntegrityError (409 for duplicates, 400 for null violations)
# - SQLAlchemyError (500)
# - Unhandled Exception (500)
```

### Manual Problem Responses

For custom error scenarios:

```python
from svc_infra.api.fastapi.middleware.errors import problem_response

@app.post("/orders")
async def create_order(req: CreateOrderRequest):
    if await order_service.is_duplicate(req.idempotency_key):
        return problem_response(
            status=409,
            title="Conflict",
            detail="Order already exists with this idempotency key.",
            code="DUPLICATE_ORDER",
            instance="/api/v1/orders",
        )
    # ... create order
```

### Error Code Standards

Use consistent error codes across your API:

| Code | Status | When to Use |
|------|--------|-------------|
| `VALIDATION_ERROR` | 422 | Request body/params failed validation |
| `NOT_FOUND` | 404 | Resource doesn't exist |
| `CONFLICT` | 409 | Duplicate or state conflict |
| `UNAUTHORIZED` | 401 | Missing or invalid credentials |
| `FORBIDDEN` | 403 | Valid credentials but insufficient permissions |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

## Pagination

svc-infra provides both cursor-based and page-based pagination.

### Cursor-Based Pagination (Recommended)

Best for large datasets and real-time data:

```python
from svc_infra.api.fastapi.pagination import (
    make_pagination_injector,
    use_pagination,
    Paginated,
)

paginate = make_pagination_injector(
    envelope=True,
    allow_cursor=True,
    allow_page=False,
    default_limit=20,
    max_limit=100,
)

@app.get("/items", dependencies=[Depends(paginate)])
async def list_items() -> Paginated[Item]:
    ctx = use_pagination()

    items = await item_service.list(
        cursor=ctx.cursor,
        limit=ctx.limit,
    )

    next_cursor = ctx.next_cursor_from_last(items, key=lambda x: x.id)

    return ctx.wrap(items, next_cursor=next_cursor)
```

**Response format:**

```json
{
  "items": [...],
  "next_cursor": "eyJhZnRlciI6ICIxMjM0NSJ9",
  "total": null
}
```

### Page-Based Pagination

For smaller datasets where total count is useful:

```python
paginate = make_pagination_injector(
    envelope=True,
    allow_cursor=False,
    allow_page=True,
    default_limit=20,
    max_limit=100,
)

@app.get("/items", dependencies=[Depends(paginate)])
async def list_items() -> Paginated[Item]:
    ctx = use_pagination()

    items, total = await item_service.list_with_count(
        page=ctx.page,
        page_size=ctx.page_size,
    )

    return ctx.wrap(items, total=total)
```

**Request:**

```
GET /items?page=2&page_size=20
```

### Filtering and Sorting

Enable filters with `include_filters=True`:

```python
paginate = make_pagination_injector(
    envelope=True,
    allow_cursor=True,
    allow_page=False,
    include_filters=True,
)

@app.get("/items", dependencies=[Depends(paginate)])
async def list_items() -> Paginated[Item]:
    ctx = use_pagination()
    filters = ctx.filters

    query = select(Item)

    if filters.q:
        query = query.where(Item.name.ilike(f"%{filters.q}%"))

    if filters.created_after:
        query = query.where(Item.created_at >= filters.created_after)

    if filters.sort:
        field, direction = parse_sort(filters.sort)
        query = query.order_by(getattr(Item, field).desc() if direction == "desc" else getattr(Item, field))

    # Execute and paginate...
```

**Available filter parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `q` | string | Text search query |
| `sort` | string | Sort field and direction (e.g., `created_at:desc`) |
| `created_after` | ISO8601 | Filter by creation date |
| `created_before` | ISO8601 | Filter by creation date |
| `updated_after` | ISO8601 | Filter by update date |
| `updated_before` | ISO8601 | Filter by update date |

### Utility Functions

```python
from svc_infra.api.fastapi.pagination import text_filter, sort_by, cursor_window

# In-memory text filtering
results = text_filter(items, q="search term", lambda x: x.name, lambda x: x.description)

# In-memory sorting
sorted_items = sort_by(items, key=lambda x: x.created_at, desc=True)

# Cursor window extraction
window, next_cursor = cursor_window(
    items,
    cursor=ctx.cursor,
    limit=ctx.limit,
    key=lambda x: x.id,
    descending=False,
)
```

---

## API Versioning

### URL Path Versioning (Recommended)

```python
from fastapi import APIRouter

v1_router = APIRouter(prefix="/v1")
v2_router = APIRouter(prefix="/v2")

@v1_router.get("/items")
async def list_items_v1():
    return {"version": 1, "items": [...]}

@v2_router.get("/items")
async def list_items_v2():
    # New response format
    return {"version": 2, "data": {"items": [...]}}

app.include_router(v1_router)
app.include_router(v2_router)
```

### Header-Based Versioning

```python
from fastapi import Header

@app.get("/items")
async def list_items(api_version: str = Header("2024-01-01", alias="X-API-Version")):
    if api_version < "2024-06-01":
        return legacy_format()
    return new_format()
```

### Deprecation Headers

Signal API deprecation to clients:

```python
from fastapi import Response

@app.get("/v1/legacy-endpoint")
async def legacy_endpoint(response: Response):
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Sat, 01 Jan 2025 00:00:00 GMT"
    response.headers["Link"] = '</v2/new-endpoint>; rel="successor-version"'
    return {"data": "..."}
```

---

## Performance Optimization

### Response Compression

```python
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)
```

### Caching Headers

```python
from fastapi import Response

@app.get("/static-data")
async def get_static_data(response: Response):
    response.headers["Cache-Control"] = "public, max-age=3600"
    response.headers["ETag"] = compute_etag(data)
    return data

@app.get("/dynamic-data")
async def get_dynamic_data(response: Response):
    response.headers["Cache-Control"] = "private, no-cache"
    return data
```

### Connection Pooling

Configure database connections efficiently:

```python
from svc_infra.api.fastapi import add_sql_db

add_sql_db(
    app,
    database_url="postgresql://...",
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before use
)
```

### Async Best Practices

```python
import asyncio

# Good: Concurrent I/O operations
async def fetch_data():
    user, orders, notifications = await asyncio.gather(
        user_service.get(user_id),
        order_service.list(user_id),
        notification_service.list(user_id),
    )
    return {"user": user, "orders": orders, "notifications": notifications}

# Bad: Sequential I/O
async def fetch_data_slow():
    user = await user_service.get(user_id)  # Wait
    orders = await order_service.list(user_id)  # Wait
    notifications = await notification_service.list(user_id)  # Wait
    return {"user": user, "orders": orders, "notifications": notifications}
```

### Streaming Responses

For large payloads:

```python
from fastapi.responses import StreamingResponse

async def generate_csv():
    yield "id,name,price\n"
    async for item in item_service.stream_all():
        yield f"{item.id},{item.name},{item.price}\n"

@app.get("/export/items")
async def export_items():
    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=items.csv"},
    )
```

---

## Testing Patterns

### Test Client Setup

```python
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from myapp import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
async def async_client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
```

### Testing Error Responses

```python
def test_validation_error(client):
    response = client.post("/orders", json={"quantity": -1})
    assert response.status_code == 422
    body = response.json()
    assert body["type"] == "about:blank"
    assert body["code"] == "VALIDATION_ERROR"
    assert "errors" in body

def test_not_found(client):
    response = client.get("/orders/nonexistent")
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "NOT_FOUND"
```

### Testing Pagination

```python
def test_cursor_pagination(client):
    # Create test data
    for i in range(25):
        client.post("/items", json={"name": f"Item {i}"})

    # First page
    response = client.get("/items?limit=10")
    data = response.json()
    assert len(data["items"]) == 10
    assert data["next_cursor"] is not None

    # Second page
    response = client.get(f"/items?cursor={data['next_cursor']}&limit=10")
    data = response.json()
    assert len(data["items"]) == 10

    # Last page
    response = client.get(f"/items?cursor={data['next_cursor']}&limit=10")
    data = response.json()
    assert len(data["items"]) == 5
    assert data["next_cursor"] is None
```

---

## See Also

- [Idempotency](idempotency.md) — Idempotent request handling
- [Billing](billing.md) — Usage-based billing integration
- [Authentication](auth.md) — JWT and OAuth patterns
- [Observability](observability.md) — Metrics, logging, tracing
