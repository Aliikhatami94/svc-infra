# ADR-0006: Ops SLOs, SLIs, and Metrics Naming

Date: 2025-10-16

## Status
Accepted

## Context
We already expose Prometheus metrics via `svc_infra.obs.add.add_observability`, which mounts the `PrometheusMiddleware` and exports:
- `http_server_requests_total{method,route,code}`
- `http_server_request_duration_seconds_bucket{route,method}` + _sum/_count
- `http_server_inflight_requests{route}`
- `http_server_response_size_bytes_bucket` + _sum/_count (where available)
- `http_server_exceptions_total{route,exception}` (where available)

We also optionally expose SQLAlchemy pool metrics and instrument `requests`/`httpx`. Logging is configured via `svc_infra.app.logging.setup_logging`.

## Decision
1. Metric naming and labels
   - Keep `http_server_*` naming aligned with Prometheus and OpenTelemetry conventions.
   - Labels: `route` uses normalized FastAPI route pattern (e.g., `/users/{id}`); `method` is uppercase HTTP verb; `code` is the 3-digit status.
   - Add DB pool metrics with `db_pool_*` prefix when bound (labels: `engine`/`pool_name`).
2. SLIs
   - Request Success Rate: 1 - error_ratio, where errors are 5xx by default; optionally include 429/499 as errors per service config.
   - Request Latency: p50/p90/p99 on `http_server_request_duration_seconds` by `route` and overall.
   - Availability (Probes): uptime of `/_ops/live` and `/_ops/ready` endpoints.
3. SLOs
   - Default SLOs per service class:
     - Public API: 99.9% success, p99 < 500ms.
     - Internal API/Jobs control plane: 99.5% success, p99 < 1000ms.
   - Error Budget: monthly window; alert on burn rates of 2h (fast) and 24h (slow). Budgets computed from success SLI.
4. Dashboards & Alerts
   - Provide Grafana JSON dashboard templates referencing the above metrics and labels.
   - Include alert rules for budget burn (fast/slow).

## Consequences
- Developers can rely on consistent metrics and labels for dashboards.
- SLO targets are explicit and can be overridden per service.
- Future work: Emit `http_server_exceptions_total` where missing; provide helper to register per-route classes (public/internal/admin) to pick default SLOs.

## Alternatives Considered
- OpenTelemetry SDK direct instrumentation was considered but deferred to keep dependency surface minimal; we keep the naming aligned for easy migration.

## References
- `src/svc_infra/obs/metrics/asgi.py`
- `src/svc_infra/api/fastapi/ops/add.py`
- Google SRE Workbook: SLOs and Error Budgets
