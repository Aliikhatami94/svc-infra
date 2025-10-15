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
