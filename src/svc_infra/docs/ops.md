# SLOs & Ops

This guide explains how to use svc-infra’s probes, circuit breaker, and metrics for SLOs.

## Probes

- `add_probes(app, prefix="/_ops")` exposes:
  - `GET /_ops/live` — liveness
  - `GET /_ops/ready` — readiness
  - `GET /_ops/startup` — startup

## Circuit breaker (placeholder)

- `circuit_breaker_dependency()` returns a dependency that returns 503 when `CIRCUIT_OPEN` is truthy.
- Use it per-route: `@app.get("/x", dependencies=[Depends(circuit_breaker_dependency())])`.

## Metrics and route classification

- `add_observability(app, ...)` enables Prometheus metrics and optional DB pool metrics.
- You can pass an optional `route_classifier(base_path, method) -> class` callable. When provided, the metrics middleware encodes the resolved route label as `"{base}|{class}"`. Dashboards can split this label to filter public/internal/admin routes.

## Dashboards

- A minimal Grafana dashboard JSON is provided at `src/svc_infra/obs/grafana/dashboards/http-overview.json` (import into Grafana).
- It shows:
  - Success rate over 5 minutes
  - p99 latency
  - Top routes by 5xx rate

## Defaults & environment

- Prometheus middleware is enabled unless `SVC_INFRA_DISABLE_PROMETHEUS=1`.
- Observability settings: `METRICS_ENABLED`, `METRICS_PATH`, and optional histogram buckets.

## See also

- Timeouts & Resource Limits: `./timeouts-and-resource-limits.md` — request/body/handler timeouts, outbound client timeouts, DB statement timeouts, jobs/webhooks, and graceful shutdown.
