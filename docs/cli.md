# CLI Quick Reference

The `svc-infra` CLI wraps common database, observability, jobs, docs, and DX workflows using Typer.

- Entry points:
  - Global: `svc-infra ...` (installed via Poetry scripts)
  - Module: `python -m svc_infra.cli ...` (works in editable installs and containers)

## Top-level help

Run:

```
svc-infra --help
```

You should see groups for SQL, Mongo, Observability, DX, Jobs, and SDK.

## Database (Alembic) commands

- End-to-end setup and migrate (detects async from URL):
  - Environment variables (commonly): `SQL_URL` or compose parts `DB_*`.

Example with SQLite for quick smoke tests:

```
python -m svc_infra.cli sql setup-and-migrate --database-url sqlite+aiosqlite:///./accept.db \
  --discover-packages "app.models" --with-payments false
```

- Current revision, history, upgrade/downgrade:

```
python -m svc_infra.cli sql current
python -m svc_infra.cli sql-history
python -m svc_infra.cli sql upgrade head
python -m svc_infra.cli sql downgrade -1
```

- Seed fixtures/reference data with your callable:

```
python -m svc_infra.cli sql seed path.to.module:seed_func
```

Notes:
- The target must be in the format `module.path:callable`.
- If you previously referenced legacy test modules under `tests.db.*`, the CLI shims import to `tests.unit.db.*` when possible.

## Jobs

Start the local jobs runner loop:

```
svc-infra jobs run
```

## DX helpers

- Generate CI workflow and checks template:

```
python -m svc_infra.cli dx ci --openapi openapi.json
```

- Lint OpenAPI and Problem+JSON samples:

```
python -m svc_infra.cli dx openapi openapi.json
```

## SDKs

Generate SDKs from OpenAPI (dry-run by default): see `docs/docs-and-sdks.md` for full examples.
