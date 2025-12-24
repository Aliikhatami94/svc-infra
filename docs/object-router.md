# Object Router — Convert Objects to FastAPI Endpoints

> **Module**: `svc_infra.api.fastapi.object_router`
>
> **Purpose**: Automatically generate FastAPI router endpoints from any Python object's methods.

---

## Overview

`router_from_object()` is a generic utility that converts any Python object into a FastAPI router by:
1. Discovering callable methods on the object
2. Inferring HTTP verbs from method name prefixes
3. Generating URL paths from method names
4. Creating Pydantic request/response models from type hints
5. Mapping exceptions to proper HTTP status codes

This eliminates boilerplate when exposing object methods as REST APIs.

---

## Quick Start

```python
from fastapi import FastAPI
from svc_infra.api.fastapi import router_from_object

class Calculator:
    """A simple calculator service."""

    def add(self, a: float, b: float) -> float:
        """Add two numbers together."""
        return a + b

    def multiply(self, a: float, b: float) -> float:
        """Multiply two numbers."""
        return a * b

    def get_history(self) -> list[str]:
        """Get calculation history."""
        return ["1 + 2 = 3", "4 * 5 = 20"]

app = FastAPI()
calc = Calculator()
router = router_from_object(calc, prefix="/calculator")
app.include_router(router)

# Generated endpoints:
# POST /calculator/add       - { "a": 1, "b": 2 } -> 3.0
# POST /calculator/multiply  - { "a": 4, "b": 5 } -> 20.0  
# GET  /calculator/history   - [] -> ["1 + 2 = 3", ...]
```

---

## API Reference

### `router_from_object()`

```python
def router_from_object(
    obj: Any,
    *,
    methods: dict[str, str] | None = None,  # method_name -> HTTP verb mapping
    exclude: list[str] | None = None,        # Methods to exclude
    prefix: str = "",                         # URL prefix
    tags: list[str] | None = None,           # OpenAPI tags
    auth_required: bool = False,             # Use user_router vs public_router
    include_private: bool = False,           # Include _underscore methods
    exception_handlers: dict[type[Exception], int] | None = None,  # Custom exc mapping
) -> DualAPIRouter:
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `obj` | `Any` | required | The object whose methods become endpoints |
| `methods` | `dict[str, str]` | `None` | Override HTTP verb for specific methods. Keys are method names, values are verbs ("GET", "POST", etc.) |
| `exclude` | `list[str]` | `None` | Methods to exclude from the router |
| `prefix` | `str` | `""` | URL prefix for all endpoints |
| `tags` | `list[str]` | `None` | OpenAPI tags (defaults to class name) |
| `auth_required` | `bool` | `False` | If `True`, uses `user_router` requiring JWT auth. If `False`, uses `public_router` |
| `include_private` | `bool` | `False` | Include methods starting with `_` (excluded by default) |
| `exception_handlers` | `dict[type, int]` | `None` | Custom exception to HTTP status mapping |

#### Returns

A `DualAPIRouter` instance from svc-infra with:
- Dual route registration (handles trailing slashes)
- Proper auth dependencies (if `auth_required=True`)
- OpenAPI schema generation

---

## HTTP Verb Inference

Methods are automatically mapped to HTTP verbs based on their name prefix:

| Prefix Pattern | HTTP Verb | Example |
|----------------|-----------|---------|
| `get_*`, `list_*`, `read_*`, `fetch_*` | GET | `get_user()` → `GET /user` |
| `create_*`, `add_*`, `insert_*` | POST | `create_user()` → `POST /user` |
| `update_*`, `modify_*`, `edit_*` | PUT | `update_user()` → `PUT /user` |
| `patch_*` | PATCH | `patch_user()` → `PATCH /user` |
| `delete_*`, `remove_*`, `destroy_*` | DELETE | `delete_user()` → `DELETE /user` |
| (no prefix match) | POST | `process()` → `POST /process` |

Override automatic inference with the `methods` parameter:
```python
router = router_from_object(
    service,
    methods={"compute": "GET", "clear": "DELETE"}
)
```

---

## Path Generation

Method names are converted to URL paths:

| Method Name | Generated Path | HTTP Verb |
|-------------|----------------|-----------|
| `get_user` | `/user` | GET |
| `create_order` | `/order` | POST |
| `update_settings` | `/settings` | PUT |
| `delete_item` | `/item` | DELETE |
| `process_payment` | `/process-payment` | POST |
| `run` | `/run` | POST |

**Path Generation Rules**:
1. Strip verb prefix (`get_`, `create_`, etc.)
2. Convert to kebab-case (`process_payment` → `process-payment`)
3. Prepend the router prefix

---

## Request/Response Models

### Request Models

For POST/PUT/PATCH methods, request bodies are auto-generated from method parameters:

```python
def create_user(self, name: str, email: str, age: int = 18) -> User:
    ...

# Generated Pydantic model:
class CreateUserRequest(BaseModel):
    name: str
    email: str
    age: int = 18
```

**Rules**:
- `self` is automatically excluded
- Type hints are preserved
- Default values become optional fields
- Complex types (Pydantic models, dataclasses) are embedded

### Response Models

Return type annotations become response models:

```python
def get_user(self, user_id: str) -> User:
    ...

# Response model: User (your Pydantic model)
```

**Supported Return Types**:
- Pydantic `BaseModel` subclasses
- `dict`, `list`, `str`, `int`, `float`, `bool`
- `None` (204 No Content)
- Dataclasses (converted to dict)

---

## GET Method Query Parameters

For GET methods, parameters become query parameters:

```python
def get_users(self, page: int = 1, limit: int = 10, search: str | None = None) -> list[User]:
    ...

# Generated: GET /users?page=1&limit=10&search=foo
```

---

## Exception Handling

Exceptions are automatically mapped to HTTP status codes:

| Exception Type | HTTP Status | Title |
|----------------|-------------|-------|
| `ValueError`, `TypeError` | 400 | Validation Error |
| `KeyError`, `LookupError` | 404 | Not Found |
| `PermissionError` | 403 | Forbidden |
| `TimeoutError` | 504 | Gateway Timeout |
| `NotImplementedError` | 501 | Not Implemented |
| `ConnectionError` | 503 | Service Unavailable |
| Other exceptions | 500 | Internal Error |

### Custom Exception Mapping

```python
class RateLimitError(Exception):
    pass

router = router_from_object(
    service,
    exception_handlers={
        RateLimitError: 429,
        MyCustomError: 422,
    }
)
```

### Public Exception Utilities

The exception mapping is also available as standalone utilities:

```python
from svc_infra.api.fastapi.object_router import (
    map_exception_to_http,
    DEFAULT_EXCEPTION_MAP,
    STATUS_TITLES,
)

# Map any exception to HTTP status
status, title, detail = map_exception_to_http(ValueError("bad input"))
print(status, title)  # 400 Validation Error

# Customize the mapping
custom_map = {**DEFAULT_EXCEPTION_MAP, MyError: 422}
status, title, detail = map_exception_to_http(exc, custom_handlers=custom_map)
```

---

## Decorators

### `@endpoint` — Custom Endpoint Configuration

Override automatic inference for specific methods:

```python
from svc_infra.api.fastapi.object_router import endpoint

class Service:
    @endpoint(method="GET", path="/custom-path", summary="Custom summary")
    def my_action(self, value: int) -> str:
        """Original docstring (overridden by summary)."""
        return f"value: {value}"
```

**Parameters**:
- `method`: HTTP verb ("GET", "POST", etc.)
- `path`: Custom URL path (overrides auto-generation)
- `summary`: OpenAPI summary (overrides docstring)
- `description`: OpenAPI description
- `response_model`: Override response model
- `status_code`: Override success status code

### `@endpoint_exclude` — Exclude Methods

Prevent a method from becoming an endpoint:

```python
from svc_infra.api.fastapi.object_router import endpoint_exclude

class Service:
    def public_action(self) -> str:
        return "public"

    @endpoint_exclude
    def internal_helper(self) -> str:
        """This won't be exposed as an endpoint."""
        return "internal"
```

---

## Authentication

### Public Endpoints (Default)

```python
router = router_from_object(service)  # No auth required
```

Uses `public_router` from svc-infra — no JWT token required.

### Authenticated Endpoints

```python
router = router_from_object(service, auth_required=True)
```

Uses `user_router` from svc-infra — requires valid JWT token.

---

## Method Filtering

### Include Only Specific Methods

```python
router = router_from_object(
    service,
    methods={"get_status": "GET", "process": "POST"}  # Only these two
)
```

### Exclude Methods

```python
router = router_from_object(
    service,
    exclude=["internal_method", "debug_helper"]
)
```

### Include Private Methods

```python
router = router_from_object(
    service,
    include_private=True  # Include _underscore methods
)
```

---

## Async Methods

Both sync and async methods are supported:

```python
class Service:
    async def async_action(self, data: str) -> dict:
        """This is already async."""
        await asyncio.sleep(0.1)
        return {"data": data}

    def sync_action(self, value: int) -> str:
        """Sync methods work in FastAPI's async context."""
        return f"value: {value}"
```

Sync methods are automatically wrapped for async compatibility using FastAPI's default behavior.

---

## Path Parameters

Parameters ending with `_id` or named `id` are automatically treated as path parameters:

```python
class UserService:
    def get_user(self, user_id: str) -> User:
        """Get a user by ID."""
        return self.users[user_id]

    def get_order_item(self, order_id: str, item_id: str) -> Item:
        """Get an item from an order."""
        return self.orders[order_id].items[item_id]

# Generated endpoints:
# GET /user/{user_id}
# GET /order-item/{order_id}/{item_id}
```

---

## WebSocket Endpoints

For streaming data, use the `@websocket_endpoint` decorator:

```python
from svc_infra.api.fastapi.object_router import (
    router_from_object_with_websocket,
    websocket_endpoint,
)

class StreamService:
    def get_status(self) -> dict:
        """Regular HTTP endpoint."""
        return {"status": "ok"}

    @websocket_endpoint(path="/stream")
    async def stream_data(self):
        """Stream data over WebSocket."""
        while True:
            yield {"timestamp": time.time()}
            await asyncio.sleep(1.0)

# Create both HTTP and WebSocket routers
http_router, ws_router = router_from_object_with_websocket(
    StreamService(),
    prefix="/api"
)

app.include_router(http_router)
app.include_router(ws_router)

# HTTP: GET /api/status
# WebSocket: ws://host/api/stream
```

---

## Complete Example

```python
from fastapi import FastAPI
from pydantic import BaseModel
from svc_infra.api.fastapi import router_from_object, endpoint, endpoint_exclude

class User(BaseModel):
    id: str
    name: str
    email: str

class UserService:
    """User management service."""

    def __init__(self):
        self._users: dict[str, User] = {}

    def get_user(self, user_id: str) -> User:
        """Get a user by ID."""
        if user_id not in self._users:
            raise KeyError(f"User {user_id} not found")
        return self._users[user_id]

    def list_users(self, limit: int = 10) -> list[User]:
        """List all users with optional limit."""
        return list(self._users.values())[:limit]

    def create_user(self, name: str, email: str) -> User:
        """Create a new user."""
        user_id = str(len(self._users) + 1)
        user = User(id=user_id, name=name, email=email)
        self._users[user_id] = user
        return user

    def update_user(self, user_id: str, name: str | None = None, email: str | None = None) -> User:
        """Update an existing user."""
        user = self.get_user(user_id)
        if name:
            user.name = name
        if email:
            user.email = email
        return user

    def delete_user(self, user_id: str) -> None:
        """Delete a user."""
        if user_id not in self._users:
            raise KeyError(f"User {user_id} not found")
        del self._users[user_id]

    @endpoint(method="POST", path="/batch-import", summary="Import multiple users")
    def batch_import(self, users: list[dict]) -> dict:
        """Import users in batch."""
        count = 0
        for u in users:
            self.create_user(u["name"], u["email"])
            count += 1
        return {"imported": count}

    @endpoint_exclude
    def _validate_email(self, email: str) -> bool:
        """Internal validation (not exposed)."""
        return "@" in email

# Create FastAPI app
app = FastAPI(title="User Service")
service = UserService()

# Generate router
router = router_from_object(
    service,
    prefix="/users",
    tags=["Users"],
    auth_required=False,
)

app.include_router(router)

# Generated endpoints:
# GET    /users/user?user_id=...           - get_user
# GET    /users/users?limit=10             - list_users
# POST   /users/user                       - create_user
# PUT    /users/user                       - update_user
# DELETE /users/user?user_id=...           - delete_user
# POST   /users/batch-import               - batch_import (custom)
```

---

## Integration with Other svc-infra Features

### With Caching

```python
from svc_infra.cache import cache_read

class CachedService:
    @cache_read(ttl=300)
    def get_data(self, key: str) -> dict:
        return expensive_operation(key)

router = router_from_object(CachedService())
```

### With Rate Limiting

Apply rate limiting at the router level:
```python
from svc_infra.rate import RateLimitMiddleware

router = router_from_object(service)
# Rate limiting is applied via middleware in FastAPI app
```

---

## Best Practices

1. **Use Type Hints**: Always add type hints for proper OpenAPI schema generation
2. **Write Docstrings**: Method docstrings become endpoint descriptions
3. **Handle Exceptions**: Raise appropriate exceptions (`ValueError`, `KeyError`) for proper HTTP status
4. **Keep Methods Focused**: One method = one endpoint = one responsibility
5. **Use Decorators Sparingly**: Auto-inference works for most cases; use `@endpoint` only when needed

---

## See Also

- [ai-infra: tools_from_object()](../../ai-infra/docs/tools/object-tools.md) — Convert objects to AI agent tools
- [Dual Routers](./api.md) — svc-infra router documentation
- [Error Handling](./error-handling.md) — Exception handling patterns
