# Observability Quickstart

This guide shows you how to turn on metrics + dashboards in three easy modes:

1. Local app → local Grafana + Prometheus (fully offline)
2. Local app → Grafana Cloud (via local Grafana Agent)
3. Deployed app → Grafana Cloud (Railway example)

It's "one button": run `svc-infra obs-up` and you're good. The CLI will read your `.env` automatically and do the right thing.

> ℹ️ A complete list of observability-related environment variables lives in [Environment Reference](../../../docs/environment.md).

---

## 0) Install & instrument your app (once)

Add the middleware and (optionally) DB/HTTP client metrics:

```python
# main.py (FastAPI / Starlette)
from fastapi import FastAPI
from svc_infra.obs.add import add_observability

app = FastAPI()

# optional: pass SQLAlchemy engines for pool metrics
shutdown = add_observability(app, db_engines=[/* your_engine(s) */])

# your routes here...
```

Environment vars (defaults shown):

```bash
# Core observability vars
METRICS_ENABLED=true
METRICS_PATH=/metrics
SCRAPE_INTERVAL=60s  # how often the agent scrapes (default 60s)

# Prometheus histogram buckets (optional)
# METRICS_DEFAULT_BUCKETS="0.005,0.01,0.025,0.05,0.1,0.25,0.5,1,2,5,10"
```

Exposed metrics include:

- `http_server_requests_total` (by method/route/code)
- `http_server_request_duration_seconds` (histogram)
- `http_server_inflight_requests`
- `http_client_requests_total`, `http_client_request_duration_seconds`
- `db_pool_in_use`, `db_pool_available`, `db_pool_checkedout_total`, `db_pool_checkedin_total`

---

## 1) Local → Local (Grafana + Prometheus on your laptop)

Use this when you don't want Cloud during dev.

### Steps

1. Make sure your app is running and exposing `/metrics` (default: http://localhost:8000/metrics).
2. Run:

```bash
svc-infra obs-up
```

If you have nothing Cloud-related in `.env`, the CLI spins up local Grafana & Prometheus under `.obs/`.

3. Open:
   - Grafana: http://localhost:3000 (admin / admin)
   - Prometheus: http://localhost:9090
4. Stop when done:

```bash
svc-infra obs-down
```

The CLI provisions a Prometheus datasource and copies our default "Service Observability (RED & USE)" dashboard into local Grafana automatically.

---

## 2) Local → Grafana Cloud (push from a local Agent)

Use this when you want Cloud dashboards while developing locally.

**What you need from Grafana Cloud (your Metrics Instance page):**

- Remote write URL (looks like `https://prometheus-prod-XX.../api/prom/push`)
- Username / Instance ID (an integer)
- API token for metrics `remote_write` (we'll call it `GRAFANA_CLOUD_RW_TOKEN`)
- Grafana URL + API token for dashboard sync (we'll call them `GRAFANA_CLOUD_URL` + `GRAFANA_CLOUD_TOKEN`)

### .env example

```bash
# Dashboard sync (browseable Grafana API)
GRAFANA_CLOUD_URL=https://your-stack.grafana.net
GRAFANA_CLOUD_TOKEN=glsa_...   # dashboard sync

# Remote write to Metrics
GRAFANA_CLOUD_PROM_URL=https://prometheus-prod-XX.grafana.net/api/prom/push
GRAFANA_CLOUD_PROM_USERNAME=1234567
GRAFANA_CLOUD_RW_TOKEN=glc_... # metrics write

# Where your app's metrics live (scraped by the local Agent)
SVC_INFRA_METRICS_URL=http://host.docker.internal:8000/metrics
SCRAPE_INTERVAL=15s
```

### Steps

1. Start your app locally.
2. Run:

```bash
svc-infra obs-up
```

The CLI will:
- Push dashboards once to your Cloud folder "Service Infrastructure" (idempotent; no duplicates).
- Start a local Grafana Agent container (under `.obs/`) that scrapes your app and remote_writes to Grafana Cloud.

3. To stop the local Agent:

```bash
svc-infra obs-down
```

The CLI writes `.obs/agent.yaml` and `.obs/docker-compose.cloud.yml` for you and mounts the config at `/etc/agent.yaml` inside the container, using the exact layout we verified.

---

## 3) Deployed app → Grafana Cloud (Railway example)

Use this when your app is deployed and you want Cloud dashboards + metrics.

We ship a ready-made Railway sidecar:

- Template files live under: `obs/templates/sidecars/railway/`
  (You'll see a Dockerfile and agent.yaml that match the working config.)

**Railway variables to set (Project Settings → Variables):**

```bash
APP_HOST=<your-app>.up.railway.app
METRICS_PATH=/metrics
SCRAPE_INTERVAL=15s

# Metrics remote_write creds
GRAFANA_CLOUD_PROM_URL=https://prometheus-prod-XX.grafana.net/api/prom/push
GRAFANA_CLOUD_PROM_USERNAME=<stack_id>
GRAFANA_CLOUD_RW_TOKEN=glc_...

# Optional (for dashboard sync)
GRAFANA_CLOUD_URL=https://your-stack.grafana.net
GRAFANA_CLOUD_TOKEN=glsa_...
```

### How to run it

1. Deploy your app on Railway (ensure it serves `/metrics`).
2. Add another service to the same project using the provided Dockerfile:
   - Context: `obs/templates/sidecars/railway/`
   - This builds grafana/agent with our agent.yaml and runs it as a sidecar service.
3. The agent will scrape `https://${APP_HOST}${METRICS_PATH}` and remote_write to Cloud.

### Dashboards in Cloud

- From your laptop (once), run:

```bash
# uses your Grafana browser API token
export GRAFANA_CLOUD_URL=https://your-stack.grafana.net
export GRAFANA_CLOUD_TOKEN=glsa_...
svc-infra obs-up
```

This syncs dashboards (idempotent) into the "Service Infrastructure" folder.
You can also wire this into CI if you prefer.

---

## Commands recap

```bash
# Start local stack or local→cloud agent depending on your .env
svc-infra obs-up

# Stop whatever was started
svc-infra obs-down

# Generate sidecar templates for other targets (compose|railway|k8s|fly)
svc-infra obs-scaffold --target railway
```

---

## What the CLI does for you

- Detects mode automatically based on your `.env`:
  - If `GRAFANA_CLOUD_URL` + `GRAFANA_CLOUD_TOKEN` exist ⇒ sync dashboards to Cloud.
  - If remote write creds (`GRAFANA_CLOUD_PROM_URL`, `GRAFANA_CLOUD_PROM_USERNAME`, `GRAFANA_CLOUD_RW_TOKEN`) exist ⇒ start local Grafana Agent to push metrics to Cloud.
  - Otherwise ⇒ start local Grafana + Prometheus.
- Loads `.env` automatically (using python-dotenv if available).
- Avoids duplicate dashboards by using stable dashboard UIDs and `overwrite: true`.
- Uses the exact Agent setup that works (mounting `/etc/agent.yaml`, `grafana/agent:v0.38.1`, `extra_hosts` mapping to reach your host app, etc.).

---

## Default dashboard & alerts

- Dashboard: "Service Observability (RED & USE)"
  (request rate, error ratio, p95 latency, DB pool usage)
- Example Prometheus alert rules are provided in `obs/templates/prometheus_rules.yml` (optional for Cloud; useful if you run your own Prometheus).

---

## Minimal checklists

### Local → Local

- App running on http://localhost:8000
- `svc-infra obs-up`
- Grafana at http://localhost:3000

### Local → Cloud

- `.env` has `GRAFANA_CLOUD_URL` + `GRAFANA_CLOUD_TOKEN`
- `.env` has `GRAFANA_CLOUD_PROM_URL`, `GRAFANA_CLOUD_PROM_USERNAME`, `GRAFANA_CLOUD_RW_TOKEN`
- App running locally
- `svc-infra obs-up`
- Check Cloud dashboard folder "Service Infrastructure"

### Railway (Deployed) → Cloud

- Set Railway variables (`APP_HOST`, `METRICS_PATH`, `SCRAPE_INTERVAL`, PROM URL, USERNAME, RW_TOKEN)
- Deploy agent sidecar from `obs/templates/sidecars/railway/`
- Run `svc-infra obs-up` locally once to sync dashboards to Cloud

---

## .env examples

### Local → Cloud

```bash
GRAFANA_CLOUD_URL=https://your-stack.grafana.net
GRAFANA_CLOUD_TOKEN=glsa_...   # dashboard sync

GRAFANA_CLOUD_PROM_URL=https://prometheus-prod-XX.grafana.net/api/prom/push
GRAFANA_CLOUD_PROM_USERNAME=1234567
GRAFANA_CLOUD_RW_TOKEN=glc_... # metrics write

SVC_INFRA_METRICS_URL=http://host.docker.internal:8000/metrics
SCRAPE_INTERVAL=15s
```

### Local → Local (no Cloud keys)

```bash
# leave Cloud values unset
SVC_INFRA_METRICS_URL=http://localhost:8000/metrics
SCRAPE_INTERVAL=30s
```

---

## Done!

That's all most devs need:

- Add `add_observability(app)`
- Pick a mode with `.env`
- Run `svc-infra obs-up`

You'll get metrics scraped, dashboards populated, and (if configured) data flowing into Grafana Cloud with zero copy-paste or manual setup.
