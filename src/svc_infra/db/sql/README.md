# svc_infra.db — CLI Guide

Lightweight wrapper around Alembic that standardizes env setup, scaffold generation, and common migration workflows. It also includes simple generators for SQLAlchemy models and Pydantic schemas.

## Running the CLI

### Installed as a package
```bash
python -m svc_infra.db --help
```

### From a checkout
- **Poetry**: `poetry run python -m svc_infra.db --help`
- **venv**: `python -m svc_infra.db --help`

> **Tip**: Most commands need a project root (where alembic.ini and migrations/ live). Pass `--project-root .` if you're already in that folder.
>
> **Note**: In this CLI the default `--project-root` is `..`, so be explicit if you're running from the project root.

## Database URL Handling

- By design, `alembic.ini` has `sqlalchemy.url` blank. The runtime url comes from the environment.
- Primary source is the `SQL_URL` env var.
- You can override it per command with `--database-url`, which sets `SQL_URL` for that process only.

### Examples:

```bash
export SQL_URL="postgresql://user:pass@host:5432/dbname"
poetry run python -m svc_infra.db upgrade --project-root .
```

```bash
poetry run python -m svc_infra.db revision \
  -m "init" \
  --database-url "sqlite:///./app.db" \
  --project-root .
```

## Async vs. Sync

You don't pass a flag. The CLI/env template auto-detects async from the URL:

- **Async examples**: `postgresql+asyncpg://…`, `sqlite+aiosqlite://…`, `mysql+aiomysql://…`
- **Sync examples**: `postgresql://…`, `postgresql+psycopg://…`, `mysql+pymysql://…`

Postgres sync driver selection is automatic (prefers psycopg, falls back to psycopg2 if installed). You can force with `DB_FORCE_DRIVER=psycopg|psycopg2` if needed.

---

## Core Alembic Workflow

### 1) init — create Alembic scaffold

Creates `alembic.ini` and `migrations/` with an `env.py` tailored to your URL (async or sync) and a `versions/` folder.

#### Options:
- `--project-root PATH` (default `..`)
- `--database-url URL` (optional override for this command)
- `--discover-packages PKG …` (optional; usually omit and let auto-discovery handle it)
- `--overwrite` (rewrite files if they exist)

#### Examples:

```bash
# Sync sqlite
poetry run python -m svc_infra.db init \
  --project-root . \
  --database-url "sqlite:///./app.db"
```

```bash
# Async postgres
poetry run python -m svc_infra.db init \
  --project-root . \
  --database-url "postgresql+asyncpg://user:pass@host/db"
```

### 2) revision — create a new migration file

#### Options:
- `-m/--message TEXT` (required)
- `--project-root PATH`
- `--database-url URL`
- `--autogenerate`
- `--head REV` (default head)
- `--branch-label TEXT`
- `--version-path PATH`
- `--sql` (emit SQL to stdout instead of Python)

#### Examples:

```bash
# Empty revision
poetry run python -m svc_infra.db revision \
  -m "init" \
  --project-root .
```

```bash
# Autogenerate from models metadata
poetry run python -m svc_infra.db revision \
  -m "add widgets" \
  --autogenerate \
  --project-root .
```

### 3) upgrade / downgrade

```bash
# Upgrade to latest
poetry run python -m svc_infra.db upgrade head --project-root .

# Upgrade to a specific revision
poetry run python -m svc_infra.db upgrade abcdef123456 --project-root .

# Step back one revision
poetry run python -m svc_infra.db downgrade -1 --project-root .

# Downgrade to base
poetry run python -m svc_infra.db downgrade base --project-root .
```

### 4) Utilities: current / history / stamp / merge-heads

```bash
# Show current DB revision
poetry run python -m svc_infra.db current --project-root .
poetry run python -m svc_infra.db current --project-root . --verbose

# Show history
poetry run python -m svc_infra.db history --project-root .
poetry run python -m svc_infra.db history --project-root . --verbose

# Set the DB marker without running migrations
poetry run python -m svc_infra.db stamp head --project-root .

# Merge divergent heads
poetry run python -m svc_infra.db merge-heads \
  --project-root . \
  -m "merge branches"
```

> **Note**: If `migrations/` doesn't exist yet, run `init` or the one-shot `setup-and-migrate` (below) first.

---

## One-shot: setup-and-migrate

End-to-end helper: ensure DB exists, create Alembic scaffold if missing, create an initial autogen revision if none exist, upgrade, and (optionally) add a follow-up autogen revision.

### Common runs:

```bash
# Minimal (relies on SQL_URL in env)
poetry run python -m svc_infra.db setup-and-migrate --project-root .
```

```bash
# With explicit messages and no scaffold overwrite
poetry run python -m svc_infra.db setup-and-migrate \
  --project-root . \
  --no-overwrite-scaffold \
  --initial-message "initial schema with user auth" \
  --followup-message "autogen after setup"
```

```bash
# Don't attempt DB creation (use existing DB only)
poetry run python -m svc_infra.db setup-and-migrate \
  --project-root . \
  --create-db-if-missing false
```

```bash
# Skip follow-up revision
poetry run python -m svc_infra.db setup-and-migrate \
  --project-root . \
  --create-followup-revision false
```

You can also pass `--database-url` to this command to avoid exporting `SQL_URL` globally.

---

## Scaffolding Commands

Generate simple, editable starter files.

### scaffold — models and schemas

#### Separate dirs (default filenames from entity name):

```bash
poetry run python -m svc_infra.db scaffold \
  --kind entity \
  --entity-name WidgetThing \
  --models-dir ./app/models \
  --schemas-dir ./app/schemas
```

#### Same dir:

```bash
poetry run python -m svc_infra.db scaffold \
  --kind entity \
  --entity-name Account \
  --models-dir ./app/account \
  --schemas-dir ./app/account \
  --same-dir
```

#### Auth starter:

```bash
poetry run python -m svc_infra.db scaffold \
  --kind auth \
  --models-dir ./app/auth \
  --schemas-dir ./app/auth
```

#### Flags:
- `--models-filename`, `--schemas-filename`
- `--overwrite`
- `--same-dir/--no-same-dir`

### scaffold-models — only models

```bash
poetry run python -m svc_infra.db scaffold-models \
  --dest-dir ./app/models \
  --kind entity \
  --entity-name FooBar \
  --include-tenant \
  --include-soft-delete
```

#### Flags:
- `--table-name`
- `--include-tenant/--no-include-tenant`
- `--include-soft-delete/--no-include-soft-delete`
- `--models-filename`
- `--overwrite`

### scaffold-schemas — only schemas

```bash
poetry run python -m svc_infra.db scaffold-schemas \
  --dest-dir ./app/schemas \
  --kind entity \
  --entity-name FooBar \
  --no-include-tenant
```

#### Flags:
- `--include-tenant/--no-include-tenant`
- `--schemas-filename`
- `--overwrite`

### Conventions

- `WidgetThing` → class `WidgetThing`, table `widget_things`, default filename `widget_thing.py`.
- Models include: id, name, description, is_active, timestamps, extra JSON; optional tenant_id, optional soft delete (deleted_at).
- Schemas include: Base/Create/Update/Read and timestamp mixin; optional tenant fields.
- `__init__.py` is created to make packages importable and (when `--same-dir`) to re-export models and schemas.

---

## Typical End-to-End (SQLite, sync)

```bash
# 1) Init scaffold
poetry run python -m svc_infra.db init \
  --project-root . \
  --database-url "sqlite:///./app.db"

# 2) First revision
poetry run python -m svc_infra.db revision \
  -m "init" \
  --project-root .

# 3) Apply
poetry run python -m svc_infra.db upgrade --project-root .

# 4) Scaffold an entity
poetry run python -m svc_infra.db scaffold \
  --entity-name WidgetThing \
  --models-dir ./app/models \
  --schemas-dir ./app/schemas
```

---

## Troubleshooting

### Path doesn't exist: …/migrations
Run `init` (or `setup-and-migrate`) for that `--project-root`.

### SQL_URL not set / could not parse URL
Export `SQL_URL` or pass `--database-url` to the command.

**Example:**
```bash
export SQL_URL="postgresql://user:pass@host:5432/db"
```
or
```bash
--database-url "sqlite:///./app.db"
```

### Driver not installed (e.g., psycopg/psycopg2)
For Postgres sync URLs, the env script will try psycopg, then psycopg2. Install one of them or set `DB_FORCE_DRIVER` to the one you've installed.

### Async URLs without async extras
If you use `postgresql+asyncpg://` (etc.), ensure the async driver is installed (asyncpg, aiomysql, aiosqlite) and SQLAlchemy's async extras are available.

### Autogenerate finds nothing
Make sure your models are importable from the Alembic env (our env adds `<project>/src` to `PYTHONPATH`). If you have a non-standard layout, you can hint with `ALEMBIC_DISCOVER_PACKAGES` or pass `--discover-packages` to `init` (one-time).

---
