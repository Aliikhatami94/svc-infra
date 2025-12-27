# Logging Guide

Structured logging utilities optimized for containerized environments like Railway, Render, and Kubernetes.

## Overview

svc-infra provides logging utilities designed for production deployments:

- **JSON Structured Logging**: Machine-readable logs for aggregation systems
- **Context Injection**: Request ID, tenant ID, user ID in every log line
- **Container Optimization**: Immediate flush for log visibility
- **Multiple Formatters**: JSON for production, human-readable for development

## Quick Start

### Basic Setup

```python
from svc_infra.logging import configure_for_container, get_logger, flush

# Configure logging at app startup
configure_for_container()

# Get a logger
logger = get_logger(__name__)
logger.info("Application started", extra={"version": "1.0.0"})

# Force flush after critical operations (for container visibility)
flush()
```

### FastAPI Integration

```python
from fastapi import FastAPI, Request
from svc_infra.logging import configure_for_container, get_logger, with_context
import uuid

app = FastAPI()

# Configure on startup
@app.on_event("startup")
async def startup():
    configure_for_container()

logger = get_logger(__name__)

@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    with with_context(request_id=request_id, path=request.url.path):
        logger.info("Request started")
        response = await call_next(request)
        logger.info("Request completed", extra={"status": response.status_code})
        return response
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `LOG_FORMAT` | `json` | `text` for human-readable, anything else for JSON |
| `PYTHONUNBUFFERED` | — | Set to `1` automatically for unbuffered output |

### Programmatic Configuration

```python
from svc_infra.logging import configure_for_container

# Default: JSON format, INFO level
configure_for_container()

# Custom configuration
configure_for_container(
    level="DEBUG",           # Log level
    json_format=False,       # Use text format
    stream=sys.stdout,       # Output stream (default: stderr)
)
```

---

## JSON Formatter

### Output Format

When `LOG_FORMAT` is not `text` (default), logs are formatted as JSON:

```json
{
    "timestamp": "2024-01-15T10:30:45.123456+00:00",
    "level": "INFO",
    "logger": "myapp.api",
    "message": "Request completed",
    "request_id": "abc-123",
    "user_id": 42,
    "status": 200
}
```

### Extra Fields

Pass additional fields using the `extra` parameter:

```python
logger.info(
    "User action",
    extra={
        "user_id": 123,
        "action": "login",
        "ip": "192.168.1.1",
    }
)
```

### Exception Logging

Exceptions are automatically captured:

```python
try:
    risky_operation()
except Exception:
    logger.exception("Operation failed")
    # Logs include "exception" field with full traceback
```

---

## Text Formatter

For local development, use text format:

```bash
LOG_FORMAT=text python app.py
```

Output:

```
2024-01-15 10:30:45 [INFO] myapp.api: Request completed [request_id=abc-123 user_id=42]
```

---

## Context Management

### Scoped Context (`with_context`)

Add context to all logs within a scope:

```python
from svc_infra.logging import with_context, get_logger

logger = get_logger(__name__)

async def handle_request(request_id: str, user_id: int):
    with with_context(request_id=request_id, user_id=user_id):
        logger.info("Starting request")
        # All logs here include request_id and user_id
        await process_request()
        logger.info("Request completed")

    # Context is cleared after the block
    logger.info("No context here")
```

### Persistent Context (`set_context`)

For context that persists across multiple operations:

```python
from svc_infra.logging import set_context, clear_context, get_logger

logger = get_logger(__name__)

async def request_middleware(request, call_next):
    # Set context for entire request lifecycle
    set_context(
        request_id=request.headers.get("X-Request-ID"),
        tenant_id=request.state.tenant_id,
    )

    try:
        return await call_next(request)
    finally:
        # Clear context at end of request
        clear_context()
```

### Get Current Context

```python
from svc_infra.logging import get_context, set_context

set_context(request_id="abc-123")
ctx = get_context()
print(ctx)  # {"request_id": "abc-123"}
```

---

## Container Optimization

### Force Flush

In containerized environments, Python buffers output. Use `flush()` to ensure logs are immediately visible:

```python
from svc_infra.logging import flush, get_logger

logger = get_logger(__name__)

logger.info("Starting database migration...")
perform_migration()
logger.info("Migration complete")
flush()  # Ensure logs are visible in container logs
```

### Uvicorn Integration

`configure_for_container()` automatically configures uvicorn loggers:

```python
from svc_infra.logging import configure_for_container

# Configures both root logger and uvicorn loggers
configure_for_container()

# Uvicorn logs now use the same format
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## Multi-Tenant Logging

Add tenant context to all logs:

```python
from svc_infra.logging import set_context, with_context, get_logger

logger = get_logger(__name__)

@app.middleware("http")
async def tenant_context_middleware(request: Request, call_next):
    tenant_id = request.state.tenant_id

    with with_context(tenant_id=tenant_id):
        return await call_next(request)
```

Now all logs include `tenant_id`:

```json
{
    "timestamp": "...",
    "level": "INFO",
    "message": "Created invoice",
    "tenant_id": "tenant-abc123",
    "invoice_id": "inv-456"
}
```

---

## Log Aggregation

### Datadog

```python
# Set standard Datadog fields
with with_context(
    dd={"trace_id": trace_id, "span_id": span_id},
    service="my-service",
    env="production",
):
    logger.info("Operation completed")
```

### Elastic / ELK

JSON output is directly compatible with Elasticsearch ingest.

### CloudWatch

AWS CloudWatch Logs parses JSON automatically:

```python
# Logs appear in CloudWatch with structured fields
logger.info(
    "Lambda invoked",
    extra={
        "request_id": context.aws_request_id,
        "function_name": context.function_name,
    }
)
```

---

## Full Example

```python
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from svc_infra.logging import (
    configure_for_container,
    get_logger,
    with_context,
    flush,
)
from svc_infra.deploy import is_containerized
import uuid

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if is_containerized():
        configure_for_container()
    else:
        configure_for_container(json_format=False, level="DEBUG")

    logger.info("Application started")
    yield

    # Shutdown
    logger.info("Application shutting down")
    flush()

app = FastAPI(lifespan=lifespan)

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    with with_context(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    ):
        logger.info("Request received")
        response = await call_next(request)
        logger.info(
            "Request completed",
            extra={"status_code": response.status_code}
        )
        return response

@app.get("/users/{user_id}")
async def get_user(user_id: int):
    with with_context(user_id=user_id):
        logger.info("Fetching user")
        user = await fetch_user(user_id)
        logger.info("User found", extra={"email": user.email})
        return user
```

---

## API Reference

### Functions

| Function | Description |
|----------|-------------|
| `configure_for_container(...)` | Configure logging for containerized environments |
| `get_logger(name)` | Get a pre-configured logger instance |
| `flush()` | Force flush stdout/stderr for immediate visibility |
| `with_context(**kwargs)` | Context manager for scoped log context |
| `set_context(**kwargs)` | Set persistent log context |
| `clear_context()` | Clear all log context |
| `get_context()` | Get current log context as dict |

### Classes

| Class | Description |
|-------|-------------|
| `JsonFormatter` | JSON log formatter for structured logging |
| `TextFormatter` | Human-readable text formatter |
