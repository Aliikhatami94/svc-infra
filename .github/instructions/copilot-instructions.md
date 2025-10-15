# copilot-instructions.md

## What this repo is
- `svc-infra` is a shared infrastructure library for FastAPI services: API scaffolding, DB migrations, caching, observability, logging, and auth helpers.
- Supported Python: 3.11–3.13. Publish-ready package via Poetry; CLI entrypoint `svc-infra` and module CLIs under `python -m svc_infra.*`.

## Dev setup and checks
- Install with Poetry: `poetry install` (ensure Python ≥3.11). Activate via `poetry shell` or prefix `poetry run`.
- Enable hooks once: `poetry run pre-commit install`.
- Format: `poetry run black . --line-length 100` and `poetry run isort . --profile black --line-length 100`.
- Lint: `poetry run flake8 --select=E,F` (see `.flake8`, max line length 120; tests ignore some F* by design).
- Type check: `poetry run mypy src`.
- Tests: `poetry run pytest -q -W error` (async tests use pytest-asyncio; HTTP tests use FastAPI TestClient).

## Architecture map (key modules)
- API scaffolding (`src/svc_infra/api/fastapi`)
	- Easy builders: `easy_service_app`/`easy_service_api` and `setup_service_api` mount versioned routers and apply middlewares (RequestId, CatchAllException, Idempotency, SimpleRateLimit). See tests in `tests/api/`.
	- SQL CRUD: `api/fastapi/db/sql` exposes `SqlResource` + `include_resources(app, [SqlResource(...)])` mounting under `/_sql{prefix}` with search/order/pagination and optional soft-delete (requires `deleted_at`).
- DB migrations CLI (`src/svc_infra/db`)
	- Typer CLI at `python -m svc_infra.db` with commands: `init`, `revision`, `upgrade/downgrade`, `current/history`, `setup-and-migrate`, scaffolds for models/schemas.
	- Database URL from env `SQL_URL` (override per-command `--database-url`). Async auto-detected from URL (`postgresql+asyncpg://` etc.). Default `--project-root` is `..`; when running from project root pass `--project-root .`.
- Caching (`src/svc_infra/cache`)
	- Initialize once: `init_cache(url=..., prefix=..., version=...)`. Decorators: `cache_read`, `cache_write`; sugar: `resource(name, id_param)` with `@resource.cache_read(...)` and `@resource.cache_write()`.
	- Tags-based invalidation and optional recache: `@cache_write(tags=[...], recache=[recache(func, include=[...])])`. Use keyword-only args for key stability (tests rely on this).
- Observability (`src/svc_infra/obs`)
	- In-app: `add_observability(app, db_engines=[...], metrics_path="/metrics", skip_metric_paths=[...])` returns a `shutdown()` cleanup. Instruments requests/httpx and SQLAlchemy pool metrics.
	- CLI: `svc-infra obs-up|obs-down` picks mode from `.env` (local Grafana+Prometheus or local Agent pushing to Grafana Cloud). See module README for required `GRAFANA_CLOUD_*` envs.
- Logging (`src/svc_infra/app` + `src/svc_infra/logging`)
	- `setup_logging(level=..., fmt=..., filter_envs=("prod","test"), drop_paths=["/metrics",...])`. Defaults: INFO+JSON in prod, DEBUG+plain elsewhere; access-log drop for `/metrics` in prod/test.
	- Env detected via `APP_ENV` (or `RAILWAY_ENVIRONMENT_NAME`). `LOG_LEVEL`, `LOG_FORMAT`, `LOG_DROP_PATHS` supported.

## External deps and extras
- Core: FastAPI, SQLAlchemy 2.x, Alembic, Typer, httpx, Pydantic Settings.
- Optional drivers/extras via Poetry extras: `pg`, `pg2`, `sqlite`, `mysql`, `mssql`, `snowflake`, `redshift`, `duckdb`, `metrics`.
- Observability: OpenTelemetry libs and `prometheus-client`. Caching: `redis` + `cashews`.

## Typical workflows (copy/paste ready)
- Run SQL migrations end-to-end: `poetry run python -m svc_infra.db setup-and-migrate --project-root .` (uses `SQL_URL`).
- Mount CRUD for a model: `include_resources(app, [SqlResource(model=Project, prefix="/projects", search_fields=["name"], soft_delete=True)])` → endpoints under `/_sql/projects`.
- Wire metrics: `shutdown = add_observability(app, db_engines=[engine])`; local dashboards: `svc-infra obs-up` (stop with `svc-infra obs-down`).
- Enable caching: `init_cache(...); user = resource("user", "user_id"); @user.cache_read(suffix="profile") ...; @user.cache_write() ...`.
- Logging one-liner: `from svc_infra.logging import setup_logging; setup_logging()`.

## Contribution expectations
- Keep templates/config in `src/svc_infra/**` in sync with code changes.
- Add/update tests for behavioral changes; keep `pytest` clean of warnings, `flake8` and `mypy` passing before merge.

## Agent workflow expectations
- Plan first: before any edits, write a clear, step-by-step task plan and keep it updated as you progress.
- Tests are mandatory for changes: if you modify existing code or add new code, add or update tests in `tests/**` to cover the behavior you touched.
- Always run tests locally before finishing: at minimum run `pytest -q` (prefer `poetry run pytest -q -W error` to match repo policy).
- Wrap up each task with a brief quality gates summary (Build, Lint/Typecheck, Tests): report PASS/FAIL and address failures before concluding.
