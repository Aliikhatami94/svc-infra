# FastAPI helper guide

The `svc_infra.api.fastapi` package provides a one-call bootstrap (`easy_service_app`) that wires request IDs, idempotency, rate limiting, and shared docs defaults for every mounted version. 【F:src/svc_infra/api/fastapi/ease.py†L176-L220】【F:src/svc_infra/api/fastapi/setup.py†L55-L129】

```python
from svc_infra.api.fastapi.ease import easy_service_app

app = easy_service_app(
    name="Payments",
    release="1.0.0",
    versions=[("v1", "myapp.api.v1", None)],
    public_cors_origins=["https://app.example.com"],
)
```

### Environment

`easy_service_app` merges explicit flags with `EasyAppOptions.from_env()` so you can flip behavior without code changes:

- `ENABLE_LOGGING`, `LOG_LEVEL`, `LOG_FORMAT` – control structured logging defaults. 【F:src/svc_infra/api/fastapi/ease.py†L67-L104】
- `ENABLE_OBS`, `METRICS_PATH`, `OBS_SKIP_PATHS` – opt into Prometheus/OTEL middleware and tweak metrics exposure. 【F:src/svc_infra/api/fastapi/ease.py†L67-L111】
- `CORS_ALLOW_ORIGINS` – add allow-listed origins when you don’t pass `public_cors_origins`. 【F:src/svc_infra/api/fastapi/setup.py†L47-L88】

## Quickstart

Use `easy_service_app` for a batteries-included FastAPI with sensible defaults:

Inputs
- name: service display name used in docs and logs
- release: version string (shown in docs and headers)
- versions: list of tuples of (prefix, import_path, router_name_or_None)
- public_cors_origins: list of allowed origins for CORS (default deny if omitted)

Defaults
- Logging: enabled with JSON or plain format based on `LOG_FORMAT`; level from `LOG_LEVEL`
- Observability: Prometheus metrics and OTEL when `ENABLE_OBS=true`; metrics path from `METRICS_PATH` (default `/metrics`)
- Security headers: strict defaults; CORS disabled unless allowlist provided or `CORS_ALLOW_ORIGINS` set
- Health: `/ping`, `/healthz`, `/readyz`, `/startupz` are wired

Example
```python
from svc_infra.api.fastapi.ease import easy_service_app

app = easy_service_app(
    name="Example API",
    release="1.0.0",
    versions=[("v1", "example.api.v1", None)],
    public_cors_origins=["https://app.example.com"],
)
```

Override with environment
```bash
export ENABLE_LOGGING=true
export LOG_LEVEL=INFO
export ENABLE_OBS=true
export METRICS_PATH=/metrics
export CORS_ALLOW_ORIGINS=https://app.example.com,https://admin.example.com
```

## Integration Helpers

svc-infra provides one-line `add_*` helpers to integrate common functionality into your FastAPI application. Each helper follows the same pattern: wire dependencies, register lifecycle hooks, and expose via `app.state` for dependency injection.

### Storage (`add_storage`)

Add file storage backend with auto-detection or explicit configuration.

```python
from fastapi import FastAPI, Depends, UploadFile
from svc_infra.storage import add_storage, get_storage, StorageBackend

app = FastAPI()

# Auto-detect backend from environment (Railway, S3, etc.)
storage = add_storage(app)

# Or explicit backend
from svc_infra.storage import easy_storage
backend = easy_storage(backend="s3", bucket="my-uploads")
storage = add_storage(app, backend)

# With file serving for LocalBackend
backend = easy_storage(backend="local")
storage = add_storage(app, backend, serve_files=True)

# Use in routes via dependency injection
@app.post("/upload")
async def upload_file(
    file: UploadFile,
    storage: StorageBackend = Depends(get_storage),
):
    content = await file.read()
    url = await storage.put(
        key=f"uploads/{file.filename}",
        data=content,
        content_type=file.content_type or "application/octet-stream",
        metadata={"user": "current_user"}
    )
    return {"url": url}
```

**Environment variables**:
- `STORAGE_BACKEND`: Backend type (`local`, `s3`, `memory`) or auto-detect
- `STORAGE_S3_BUCKET`, `STORAGE_S3_REGION`: S3 configuration
- `STORAGE_BASE_PATH`: Local backend directory (default: `/data/uploads`)
- Auto-detects Railway volumes via `RAILWAY_VOLUME_MOUNT_PATH`

**See**: [Storage Guide](storage.md) for comprehensive documentation.

### Documents (`add_documents`)

Add generic document management with upload, list, get, and delete endpoints.

```python
from svc_infra.documents import add_documents

app = FastAPI()
manager = add_documents(app)  # Adds protected /documents/* routes

# Programmatic access
doc = await manager.upload(
    user_id="user_123",
    file=file_bytes,
    filename="contract.pdf",
    metadata={"category": "legal"}
)
```

**Routes added** (all protected, require authentication):
- `POST /documents/upload`: Upload document with metadata
- `GET /documents/{document_id}`: Get document metadata
- `GET /documents/list`: List user's documents (paginated)
- `DELETE /documents/{document_id}`: Delete document

**Environment variables**: Inherits from [Storage](#storage-add_storage) configuration.

**See**: [Documents Guide](documents.md) for extension patterns and examples.

### Database (`add_sql_db`)

Wire SQLAlchemy connection with health checks and lifecycle management.

```python
from svc_infra.api.fastapi.db.sql.add import add_sql_db

app = FastAPI()
add_sql_db(app)  # Reads SQL_URL or DB_* environment variables
```

**See**: [Database Guide](database.md)

### Auth (`add_auth_users`)

Wire FastAPI Users with sessions, OAuth, MFA, and API keys.

```python
from svc_infra.api.fastapi.auth.add import add_auth_users

app = FastAPI()
add_auth_users(app, User, UserCreate, UserRead, UserUpdate)
```

**See**: [Auth Guide](auth.md)

### Observability (`add_observability`)

Add Prometheus metrics, request tracking, and health endpoints.

```python
from svc_infra.obs.add import add_observability

app = FastAPI()
add_observability(app)  # Honors ENABLE_OBS, METRICS_PATH environment variables
```

**See**: [Observability Guide](observability.md)

### Webhooks (`add_webhooks`)

Wire webhook producer and verification middleware.

```python
from svc_infra.webhooks.add import add_webhooks

app = FastAPI()
add_webhooks(app)  # Mounts /_webhooks routes and verification middleware
```

**See**: [Webhooks Guide](webhooks.md)

### Jobs (`easy_jobs`)

Initialize job queue and scheduler.

```python
from svc_infra.jobs.easy import easy_jobs

queue, scheduler = easy_jobs()  # Reads JOBS_DRIVER, REDIS_URL
```

**See**: [Jobs Guide](jobs.md)

### Pattern

All integration helpers follow this pattern:

1. **Accept app instance**: `add_*(app, ...)`
2. **Auto-configure from environment**: Read from env vars with sensible defaults
3. **Store in app.state**: Make available via `app.state.storage`, `app.state.db`, etc.
4. **Provide dependency**: Export `get_*` function for route injection
5. **Register lifecycle hooks**: Handle startup/shutdown (connection pools, cleanup)
6. **Add health checks**: Integrate with `/healthz` endpoints

This enables one-line integration with zero configuration in most cases, while supporting explicit overrides when needed.
