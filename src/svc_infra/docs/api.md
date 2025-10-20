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
