# CLI Reference

**svc-infra** provides a comprehensive command-line interface for infrastructure automation, database migrations, observability setup, SDK generation, and developer experience workflows.

---

## Quick Start

```bash
# Install via pip or poetry
pip install svc-infra

# Check available commands
svc-infra --help

# Alternative invocation
python -m svc_infra.cli --help
```

**Entry Points:**
- `svc-infra` — Installed console script (recommended)
- `python -m svc_infra.cli` — Module invocation
- `poetry run svc-infra` — Poetry environment wrapper

---

## Command Groups

| Group | Purpose |
|-------|---------|
| `sql` | SQL database migrations (Alembic), scaffolding, export |
| `mongo` | MongoDB operations and scaffolding |
| `db` | Database operations (wait, kill-queries) |
| `obs` | Observability stack (Grafana, Prometheus) |
| `jobs` | Background job scheduler |
| `sdk` | Client SDK generation (TypeScript, Python, Postman) |
| `dx` | Developer experience (CI, OpenAPI checks, changelog) |
| `health` | Health endpoint verification |
| `docs` | Interactive documentation browser |

---

## SQL Commands

Alembic-based migration management with auto-detection of sync/async engines.

### setup-and-migrate

End-to-end database setup: creates database if missing, scaffolds Alembic, runs migrations.

```bash
# Basic usage (reads SQL_URL from environment)
svc-infra sql setup-and-migrate

# With explicit database URL
svc-infra sql setup-and-migrate --database-url postgresql+asyncpg://user:pass@host/db

# Include payments models
svc-infra sql setup-and-migrate --with-payments

# Specify packages to discover models
svc-infra sql setup-and-migrate --discover-packages myapp.models --discover-packages myapp.auth
```

**Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--database-url` | `$SQL_URL` | Database connection URL |
| `--overwrite-scaffold` | `false` | Overwrite existing Alembic scaffold |
| `--create-db-if-missing` | `true` | Create database if it doesn't exist |
| `--create-followup-revision` | `true` | Auto-generate revision after initial |
| `--initial-message` | `"initial schema"` | First revision message |
| `--followup-message` | `"autogen"` | Follow-up revision message |
| `--discover-packages` | auto | Packages containing SQLAlchemy models |
| `--with-payments` | `$APF_ENABLE_PAYMENTS` | Include payment models |

### init

Initialize Alembic scaffold with async/sync auto-detection.

```bash
# Initialize with auto-detection
svc-infra sql init

# Specify packages and overwrite
svc-infra sql init --discover-packages myapp.models --overwrite
```

### revision

Create a new migration revision.

```bash
# Empty revision
svc-infra sql revision -m "add users table"

# Auto-generated from model changes
svc-infra sql revision -m "add email column" --autogenerate

# Generate SQL instead of Python
svc-infra sql revision -m "add index" --sql
```

**Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `-m, --message` | required | Revision message |
| `--autogenerate` | `false` | Generate from model diff |
| `--head` | `"head"` | Base revision |
| `--branch-label` | none | Branch label |
| `--version-path` | none | Alternative versions path |
| `--sql` | `false` | Output SQL instead of Python |

### upgrade

Apply migrations to reach target revision.

```bash
# Upgrade to latest
svc-infra sql upgrade

# Upgrade to specific revision
svc-infra sql upgrade abc123

# Upgrade one step
svc-infra sql upgrade +1
```

### downgrade

Roll back migrations.

```bash
# Roll back one step
svc-infra sql downgrade

# Roll back to specific revision
svc-infra sql downgrade abc123

# Roll back all migrations
svc-infra sql downgrade base
```

### current

Display current revision state.

```bash
svc-infra sql current
svc-infra sql current --verbose
```

### history

List migration history in chronological order.

```bash
svc-infra sql history
svc-infra sql history --verbose
```

### stamp

Stamp revision table without running migrations.

```bash
# Mark as fully migrated
svc-infra sql stamp head

# Mark at specific revision
svc-infra sql stamp abc123
```

### merge-heads

Create a merge revision for multiple heads.

```bash
svc-infra sql merge-heads
svc-infra sql merge-heads -m "merge feature branches"
```

### scaffold

Generate starter models and schemas.

```bash
# Entity scaffold
svc-infra sql scaffold \
  --kind entity \
  --entity-name Product \
  --models-dir src/app/models \
  --schemas-dir src/app/schemas

# Auth scaffold
svc-infra sql scaffold \
  --kind auth \
  --entity-name User \
  --models-dir src/app/auth \
  --schemas-dir src/app/auth \
  --same-dir
```

### scaffold-models

Generate only SQLAlchemy models.

```bash
svc-infra sql scaffold-models \
  --dest-dir src/app/models \
  --kind entity \
  --entity-name Order \
  --include-tenant \
  --include-soft-delete
```

### scaffold-schemas

Generate only Pydantic schemas.

```bash
svc-infra sql scaffold-schemas \
  --dest-dir src/app/schemas \
  --kind entity \
  --entity-name Order \
  --include-tenant
```

### export-tenant

Export tenant-scoped data as JSON.

```bash
# Export all items for tenant
svc-infra sql export-tenant public.items --tenant-id tenant_abc

# With limit and output file
svc-infra sql export-tenant public.orders \
  --tenant-id tenant_abc \
  --limit 1000 \
  --output orders.json
```

**Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--tenant-id` | required | Tenant ID to filter by |
| `--tenant-field` | `tenant_id` | Column name for filtering |
| `--output` | stdout | Output file path |
| `--limit` | none | Maximum rows to export |
| `--database-url` | `$SQL_URL` | Database connection URL |

---

## Database Operations

### db wait

Wait for database to be ready before proceeding. Essential for container orchestration.

```bash
# Wait with defaults (60s timeout, 2s interval)
svc-infra db wait

# Custom timeout and interval
svc-infra db wait --timeout 120 --interval 5

# Quiet mode for scripts
svc-infra db wait --quiet
```

**Exit Codes:**
- `0` — Database is ready
- `1` — Timeout reached, database not ready

### db kill-queries

Terminate queries blocking a specific table. Useful for stuck migrations.

```bash
# Preview blocking queries (dry-run)
svc-infra db kill-queries users --dry-run

# Cancel blocking queries (graceful)
svc-infra db kill-queries users

# Terminate immediately (forceful)
svc-infra db kill-queries users --force

# Quiet mode for automation
svc-infra db kill-queries users --quiet
```

**Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--url, -u` | `$SQL_URL` | Database URL |
| `--dry-run, -n` | `false` | Show without killing |
| `--force, -f` | `false` | Use pg_terminate_backend |
| `--quiet, -q` | `false` | Suppress output |

---

## Observability Commands

Setup and manage Grafana + Prometheus stacks for metrics visualization.

### obs up

Start observability stack with auto-detection of local vs cloud mode.

```bash
# Local mode: starts Grafana + Prometheus
svc-infra obs up

# Cloud mode: push dashboards to Grafana Cloud
# (set GRAFANA_CLOUD_URL and GRAFANA_CLOUD_TOKEN)
svc-infra obs up
```

**Environment Variables for Cloud Mode:**
```bash
GRAFANA_CLOUD_URL=https://your-org.grafana.net
GRAFANA_CLOUD_TOKEN=glc_xxx
GRAFANA_CLOUD_PROM_URL=https://prometheus-prod-xx.grafana.net/api/prom
GRAFANA_CLOUD_PROM_USERNAME=12345
GRAFANA_CLOUD_RW_TOKEN=xxx
```

**Local Mode URLs:**
- Grafana: http://localhost:3000 (admin/admin)
- Prometheus: http://localhost:9090

### obs down

Stop observability stack containers.

```bash
svc-infra obs down
```

### obs scaffold

Generate observability sidecar configurations for different platforms.

```bash
svc-infra obs scaffold --target compose
svc-infra obs scaffold --target railway
svc-infra obs scaffold --target k8s
svc-infra obs scaffold --target fly
```

---

## Jobs Commands

Background job scheduler management.

### jobs run

Run the job scheduler and worker loop.

```bash
# Default poll interval (0.5s)
svc-infra jobs run

# Custom poll interval
svc-infra jobs run --poll-interval 1.0

# Limited loops for testing
svc-infra jobs run --max-loops 100
```

**Options:**
| Option | Default | Description |
|--------|---------|-------------|
| `--poll-interval` | `0.5` | Seconds between idle loops |
| `--max-loops` | none | Maximum iterations (for tests) |

**Note:** The default handler is a no-op. Implement your own job handler for actual processing.

---

## SDK Commands

Generate client SDKs from OpenAPI specifications.

### sdk ts

Generate TypeScript SDK using openapi-typescript-codegen.

```bash
# Dry run (print command)
svc-infra sdk ts openapi.json

# Generate SDK
svc-infra sdk ts openapi.json --dry-run false --outdir sdk-ts
```

### sdk py

Generate Python SDK using openapi-generator-cli.

```bash
# Dry run
svc-infra sdk py openapi.json

# Generate SDK
svc-infra sdk py openapi.json --dry-run false --package-name my_sdk
```

### sdk postman

Convert OpenAPI to Postman collection.

```bash
# Dry run
svc-infra sdk postman openapi.json

# Generate collection
svc-infra sdk postman openapi.json --dry-run false --out postman.json
```

---

## DX Commands

Developer experience utilities for CI/CD workflows.

### dx ci

Print or run CI steps locally to mirror GitHub Actions workflow.

```bash
# Dry run (print steps)
svc-infra dx ci

# Actually run CI steps
svc-infra dx ci --run

# With OpenAPI validation
svc-infra dx ci --run --openapi openapi.json
```

**CI Steps:**
1. `flake8 --select=E,F` — Lint
2. `mypy src` — Type check
3. `svc-infra dx openapi` — OpenAPI validation (if specified)
4. `svc-infra dx migrations` — Migration check
5. `pytest -q -W error` — Tests

### dx openapi

Validate OpenAPI specification for problem schema compliance.

```bash
svc-infra dx openapi openapi.json
```

### dx migrations

Check that migrations are up to date.

```bash
svc-infra dx migrations
svc-infra dx migrations --project-root ./backend
```

### dx changelog

Generate changelog section from commit messages (Conventional Commits format).

```bash
# Show expected format
svc-infra dx changelog 0.1.604

# Generate from commits file
svc-infra dx changelog 0.1.604 --commits-file commits.jsonl
```

**Commits File Format (JSONL):**
```json
{"sha": "abc123", "subject": "feat: add user authentication"}
{"sha": "def456", "subject": "fix: resolve race condition"}
```

---

## Health Commands

Verify endpoint health status.

### health check

Check health of a URL endpoint.

```bash
# Basic check
svc-infra health check http://localhost:8000/health

# With timeout
svc-infra health check http://api:8080/ready --timeout 5

# JSON output
svc-infra health check http://localhost:8000/health --json

# Verbose with details
svc-infra health check http://localhost:8000/health --verbose
```

**Exit Codes:**
- `0` — Healthy (HTTP 2xx)
- `1` — Unhealthy or unreachable

### health wait

Wait for a health endpoint to become ready.

```bash
svc-infra health wait http://localhost:8000/health
svc-infra health wait http://api:8080/ready --timeout 120 --interval 5
```

---

## Docs Commands

Interactive documentation browser.

```bash
# List available topics
svc-infra docs --help

# Show a specific topic
svc-infra docs auth
svc-infra docs database
svc-infra docs show tenancy
```

Topics are discovered from:
1. `$SVC_INFRA_DOCS_DIR` environment variable
2. Project's `docs/` directory (when inside svc-infra repo)
3. Installed package's embedded documentation

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SQL_URL` | — | Primary database connection URL |
| `DATABASE_URL` | — | Fallback database URL |
| `APF_ENABLE_PAYMENTS` | `false` | Enable payments model discovery |
| `SVC_INFRA_DOCS_DIR` | — | Custom docs directory |
| `SVC_INFRA_METRICS_URL` | `http://host.docker.internal:8000/metrics` | Metrics endpoint |
| `GRAFANA_PORT` | `3000` | Local Grafana port |
| `PROM_PORT` | `9090` | Local Prometheus port |
| `GRAFANA_CLOUD_URL` | — | Grafana Cloud URL |
| `GRAFANA_CLOUD_TOKEN` | — | Grafana Cloud API token |
| `GRAFANA_CLOUD_PROM_URL` | — | Prometheus remote write URL |
| `GRAFANA_CLOUD_PROM_USERNAME` | — | Prometheus remote write username |
| `GRAFANA_CLOUD_RW_TOKEN` | — | Prometheus remote write token |
| `SVC_INFRA_CLOUD_FOLDER` | `"Service Infrastructure"` | Dashboard folder name |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error or unhealthy status |
| `2` | Invalid arguments or missing required configuration |

---

## See Also

- [Database Guide](database.md) — SQL and MongoDB integration details
- [Observability Guide](observability.md) — Metrics, tracing, and dashboards
- [Jobs Guide](jobs.md) — Background task scheduling
- [Tenancy Guide](tenancy.md) — Multi-tenant architecture
