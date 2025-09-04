## svc_infra db CLI

Manage database setup and Alembic migrations.

### Usage

- Script: `svc-infra db`
- Poetry: `poetry run svc-infra db --help`
- Python module (alternative): `python -m svc_infra.cli.run db --help`

The CLI reads DATABASE_URL from the environment by default. You can override it per-command with `--database-url`.

### Quick start

- Initialize Alembic in your project (creates `alembic.ini` and `migrations/`):

  ```bash
  poetry run svc-infra db init --project-root . --database-url sqlite:///./app.db
  ```

- Create a revision file:

  ```bash
  poetry run svc-infra db revision -m "init"
  ```

- Apply migrations:

  ```bash
  poetry run svc-infra db upgrade
  ```

- Show current head and history:

  ```bash
  poetry run svc-infra db current
  poetry run svc-infra db history
  ```

- Downgrade one step and restamp to head:

  ```bash
  poetry run svc-infra db downgrade -1
  poetry run svc-infra db stamp head
  ```

- Merge multiple heads (if your repo diverged):

  ```bash
  poetry run svc-infra db merge-heads -m "merge heads"
  ```

### Commands

- `init`
  - Options:
    - `--project-root PATH` (default `.`) – where `alembic.ini` and `migrations/` are created
    - `--database-url TEXT` – overrides env `DATABASE_URL` for this command
    - `--async-db/--no-async-db` – generate async `env.py` (for async drivers like aiosqlite/asyncpg)
    - `--discover-packages TEXT...` – list of Python packages to search for SQLAlchemy metadata
    - `--overwrite/--no-overwrite` – overwrite existing files

- `revision`
  - Options:
    - `-m, --message TEXT` (required)
    - `--project-root PATH` (default `.`)
    - `--database-url TEXT`
    - `--autogenerate/--no-autogenerate`
    - `--head TEXT` (default `head`)
    - `--branch-label TEXT`
    - `--version-path TEXT`
    - `--sql/--no-sql`

- `upgrade [REVISION]` (default `head`)
  - Options: `--project-root PATH`, `--database-url TEXT`

- `downgrade [REVISION]` (default `-1`)
  - Options: `--project-root PATH`, `--database-url TEXT`

- `current` / `history`
  - Options: `--project-root PATH`, `--database-url TEXT`, `--verbose`

- `stamp [REVISION]` (default `head`)
  - Options: `--project-root PATH`, `--database-url TEXT`

- `merge-heads`
  - Options: `--project-root PATH`, `--database-url TEXT`, `-m, --message TEXT`

### Environment

- `DATABASE_URL` – primary source for DB connection URL
- `DB_URL` – fallback if `DATABASE_URL` is not set
- `ALEMBIC_DISCOVER_PACKAGES` – optional comma-separated list of packages for metadata discovery in generated `env.py`

Examples:

```bash
# Use env-driven config
export DATABASE_URL=sqlite:///./app.db
export ALEMBIC_DISCOVER_PACKAGES=my_app.models,another_app.models
poetry run svc-infra db init --project-root .
```

Notes:
- The generated `alembic.ini` and runtime config include `path_separator = os` so Alembic can parse `prepend_sys_path` portably.
- A local `migrations/script.py.mako` template is written to ensure `revision` works without global templates.

### Programmatic API

You can also use the functions directly:

```python
from svc_infra.db import (
    init_alembic,
    ensure_database_exists,
    build_engine,
    init_database_structure,
)

# Ensure DB exists and scaffold alembic
init_database_structure(project_root=".")

# Or granular control
init_alembic(project_root=".", async_db=False, discover_packages=["my_app.models"])  # creates alembic files
```

### MCP server

An MCP server exposing db management functions is available:
- Name: `db-management-mcp`
- Functions: `init_alembic`, `revision`, `upgrade`, `downgrade`, `current`, `history`, `stamp`, `merge_heads`
- Transport: stdio

Integrate it with an MCP-compatible client to drive migrations programmatically.

### Troubleshooting

- SQLAlchemy 2.0 requires `sqlalchemy.text("...")` for textual SQL in tests or scripts.
- For SQLite file URLs (e.g., `sqlite:///./data/app.db`), parent directories are created when ensuring the database exists.
