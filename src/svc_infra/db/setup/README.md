svc_infra.db.setup CLI integration guide

This README covers how to use the database command-line interface exposed by src/svc_infra/db/cli.py. It wraps Alembic utilities and provides scaffolding for SQLAlchemy models and Pydantic schemas.

How to run the CLI
- If the project is installed as a package: python -m svc_infra.db.setup.cli --help
- From a repo checkout:
  - With Poetry: poetry run python -m svc_infra.db.setup.cli --help
  - With venv: python -m svc_infra.db.setup.cli --help

Database URL handling
- Most commands read the database URL from the DATABASE_URL environment variable.
- You can override it per-command with the --database-url option (the CLI sets DATABASE_URL for that process only).
- Examples:
  - export DATABASE_URL=sqlite:///:memory:
  - python -m svc_infra.db.setup.cli upgrade --project-root .
  - python -m svc_infra.db.setup.cli revision -m "init" --database-url sqlite:///./app.db

Alembic lifecycle commands
1) init — create Alembic config and migrations folder
- Creates alembic.ini in the chosen project root and a migrations/ directory with env.py and versions/.
- Options:
  - --project-root PATH: where to create files (default .)
  - --database-url URL: used to infer dialect in alembic.ini (overrides env)
  - --async-db / --no-async-db: generate async env.py (for async drivers like sqlite+aiosqlite, postgresql+asyncpg)
  - --discover-packages PKG ...: packages to import and search for SQLAlchemy metadata
  - --overwrite: replace existing files
- Example (sync sqlite):
  - python -m svc_infra.db.setup.cli init --project-root . --database-url sqlite:///./app.db
- Example (async):
  - python -m svc_infra.db.setup.cli init --project-root . --database-url sqlite+aiosqlite:///./app.db --async-db

2) revision — create a new migration file
- Options:
  - -m/--message TEXT: revision message (required)
  - --project-root PATH: project root that contains alembic.ini
  - --database-url URL: override env for this command
  - --autogenerate: compare metadata to DB and generate operations
  - --head REV: parent head (default head)
  - --branch-label TEXT
  - --version-path PATH: custom versions folder
  - --sql: emit SQL to stdout instead of Python
- Example (empty migration):
  - python -m svc_infra.db.setup.cli revision -m "init" --project-root .
- Example (autogenerate):
  - python -m svc_infra.db.setup.cli revision -m "add widgets" --autogenerate --project-root .

3) upgrade/downgrade — apply or roll back migrations
- upgrade [REV]: default head
  - python -m svc_infra.db.setup.cli upgrade --project-root .
  - python -m svc_infra.db.setup.cli upgrade ae1027a6acf --project-root .
- downgrade [REV]: default -1 (one step)
  - python -m svc_infra.db.setup.cli downgrade --project-root .
  - python -m svc_infra.db.setup.cli downgrade base --project-root .

4) current/history/stamp/merge-heads — utilities
- current: show current DB revision
  - python -m svc_infra.db.setup.cli current --project-root .
  - python -m svc_infra.db.setup.cli current --project-root . --verbose
- history: show migration history
  - python -m svc_infra.db.setup.cli history --project-root .
  - python -m svc_infra.db.setup.cli history --project-root . --verbose
- stamp [REV]: set DB to a revision without running migrations
  - python -m svc_infra.db.setup.cli stamp head --project-root .
- merge-heads: merge divergent heads
  - python -m svc_infra.db.setup.cli merge-heads --project-root . -m "merge branches"

Scaffolding commands
The CLI can scaffold starter SQLAlchemy models and Pydantic schemas. Outputs are simple, editable files.

A) scaffold — generate models and schemas together
- Usage patterns:
  - Separate dirs (default filenames derived from entity):
    - python -m svc_infra.db.setup.cli scaffold \
      --kind entity \
      --entity-name WidgetThing \
      --models-dir ./app/models \
      --schemas-dir ./app/schemas
  - Separate dirs with custom filenames:
    - python -m svc_infra.db.setup.cli scaffold \
      --kind entity \
      --entity-name Gizmo \
      --models-dir ./app/models --models-filename m_gizmo.py \
      --schemas-dir ./app/schemas --schemas-filename s_gizmo.py
  - Same dir (paired models.py and schemas.py with a paired __init__.py):
    - python -m svc_infra.db.setup.cli scaffold \
      --kind entity \
      --entity-name Account \
      --models-dir ./app/account \
      --schemas-dir ./app/account \
      --same-dir
- Options:
  - --kind [entity|auth]: auth uses built-in templates; entity renders generic model/schema from the entity name
  - --entity-name TEXT: used to derive class names and default table/filenames (e.g., WidgetThing -> widget_things)
  - --models-dir PATH, --schemas-dir PATH: target directories; created if missing
  - --same-dir / --no-same-dir: put both files in one folder (models.py, schemas.py)
  - --models-filename TEXT, --schemas-filename TEXT: when separate dirs, override default <snake(entity)>.py
  - --overwrite: allow overwriting existing files

B) scaffold-models — generate only a model file
- Example:
  - python -m svc_infra.db.setup.cli scaffold-models \
    --dest-dir ./app/models \
    --entity-name FooBar \
    --include-tenant \
    --include-soft-delete
- Options:
  - --kind [entity|auth]
  - --entity-name TEXT
  - --table-name TEXT: override default table name (defaults to snake_case(entity)+s)
  - --include-tenant/--no-include-tenant: include tenant_id field and related constraints/index
  - --include-soft-delete/--no-include-soft-delete: include deleted_at in addition to is_active
  - --models-filename TEXT: filename override (default <snake(entity)>.py)
  - --overwrite

C) scaffold-schemas — generate only a schema file
- Example:
  - python -m svc_infra.db.setup.cli scaffold-schemas \
    --dest-dir ./app/schemas \
    --entity-name FooBar \
    --no-include-tenant
- Options:
  - --kind [entity|auth]
  - --entity-name TEXT
  - --include-tenant/--no-include-tenant
  - --schemas-filename TEXT
  - --overwrite

Conventions and outputs
- Entity naming:
  - The CLI normalizes the entity name: WidgetThing -> class WidgetThing, default table widget_things, default filename widget_thing.py.
- Outputs:
  - Model includes id, name, description, is_active, timestamps, and JSON extra; optional tenant_id and soft-delete fields per flags.
  - Schemas include Base/Create/Update/Read with Timestamped mixin; optional tenant_id per flags.
- __init__.py:
  - When using --same-dir, the folder’s __init__.py re-exports models and schemas.
  - Otherwise, each target dir gets a minimal package marker __init__.py.
- Print format:
  - Scaffold commands print a Python dict (not JSON). If you’re parsing the output, account for single quotes.

Typical end-to-end workflow (SQLite example)
1) Initialize migrations (sync driver):
   - python -m svc_infra.db.setup.cli init --project-root . --database-url sqlite:///./app.db
2) Create an initial revision:
   - python -m svc_infra.db.setup.cli revision -m "init" --project-root .
3) Apply migrations to the database:
   - python -m svc_infra.db.setup.cli upgrade --project-root .
4) Scaffold a new entity’s model and schema:
   - python -m svc_infra.db.setup.cli scaffold \
     --entity-name WidgetThing \
     --models-dir ./app/models \
     --schemas-dir ./app/schemas

Notes and tips
- Use an async URL (e.g., sqlite+aiosqlite:///./app.db, postgresql+asyncpg://...) together with --async-db during init if your app uses async engines.
- For SQLite file URLs, the CLI creates parent directories when needed. Ensure the executing user can write to the chosen path.
- Aim to keep models importable during autogenerate; use --discover-packages to tell the env script where to find your ModelBase metadata.
- If you see multiple heads (diverged history), use merge-heads with an appropriate message, then upgrade.

