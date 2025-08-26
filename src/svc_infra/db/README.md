# Database CLI (Alembic scaffolding and management)

This CLI helps you scaffold and operate Alembic for your app, with smart model auto-discovery and optional app logging.

Entrypoint
- Poetry script: svc-infra-db

Quickstart
```bash
# 1) Initialize Alembic (creates alembic.ini, migrations/, env.py, script.py.mako, versions/)
poetry run svc-infra-db init
# Optionally specify DB URL or discovery packages
# poetry run svc-infra-db init --database-url postgresql+asyncpg://user:pass@localhost/db \
#   --discover-packages "my_app,another_pkg"

# 2) Create a migration from model diffs
poetry run svc-infra-db revision -m "init schema" --autogenerate

# 3) Apply latest migrations
poetry run svc-infra-db upgrade head

# 4) Roll back last migration
poetry run svc-infra-db downgrade -1

# 5) Status
poetry run svc-infra-db current
poetry run svc-infra-db history
```

Additional commands
- Drop a table (generates a migration that drops a table; optional auto-apply):
```bash
poetry run svc-infra-db drop-table public.users --cascade --if-exists --apply
# flags: --message, --base, --apply
```
- Merge multiple heads into one:
```bash
poetry run svc-infra-db merge-heads -m "merge branches"
```

AI assistant
- Use the ai command to plan and execute DB CLI workflows interactively:
```bash
# Plan and execute with confirmation
poetry run svc-infra-db ai "init alembic and create migrations"

# Auto-confirm plan + run
poetry run svc-infra-db ai "upgrade head" -y

# Fully autonomous (auto-approve plan and tools)
poetry run svc-infra-db ai "upgrade head" --auto

# Specify provider/model
poetry run svc-infra-db ai "show current" --provider openai --model gpt_5_mini
```
- Options (from `svc-infra-db ai --help`)
  - --yes, -y: Auto-confirm plan execution
  - --autoapprove: Auto-approve all tool calls
  - --auto: Fully autonomous (approve plan + tool calls)
  - --db-url TEXT: Set $DATABASE_URL for tools (never printed)
  - --max-lines INTEGER: Max lines when printing tool output (default: 60)
  - --quiet-tools: Hide tool output; show only AI summaries
  - --verbose-tools/--no-verbose-tools: Show detailed tool logs including args (redacted) (default: enabled)
  - --show-error-context/--no-show-error-context: Print partial tool output when a step fails (default: enabled)
  - --provider TEXT: LLM provider (e.g. openai, anthropic, google) (default: openai)
  - --model TEXT: Model name key (e.g. gpt_5_mini, sonnet, gemini_1_5_pro) (default: default)

How init works
- Writes alembic.ini and a migrations/ folder with:
  - env.py that:
    - Adds project root and src/ to sys.path
    - Optionally uses your app logging (ALEMBIC_USE_APP_LOGGING=1) or falls back to fileConfig
    - Auto-discovers Declarative models by importing all modules under chosen packages and collecting all DeclarativeBase metadatas
    - Supports async and sync engines; chooses the online runner you initialized with
  - script.py.mako template to ensure autogenerate works (incl. types from fastapi_users_db_sqlalchemy)
  - versions/ directory for migration files

Discovery of models
- By default, it crawls top-level packages found under:
  - Project root packages (folders with __init__.py)
  - src/ packages (folders with __init__.py)
- Override the packages list with either:
  - init option: --discover-packages "pkg1,pkg2"
  - env var: ALEMBIC_DISCOVER_PACKAGES=pkg1,pkg2

Database URL
- Use env: DATABASE_URL
- Or pass: --database-url postgresql+asyncpg://user:pass@host/db

Logging
- Prefer app logging if ALEMBIC_USE_APP_LOGGING=1 and svc_infra.app.logging.setup_logging is importable
- Otherwise, falls back to Alembic's fileConfig based on alembic.ini

Async vs sync
- init has --async-db / --no-async-db (default: async on)
- The generated env.py provides both async and sync paths; the init flag controls the default call at runtime

Notes
- Autogenerate compares types and server defaults and uses render_as_batch for safer SQLite migrations
- You can run the commands without Poetry if installed globally: svc-infra-db ...
