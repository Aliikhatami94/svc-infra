# svc_infra.auth CLI

Scaffold FastAPI Users essentials into your app. You can generate files one-by-one or all at once.

## Install / Run

- Installed with this package. The CLI entrypoint is `svc-auth`.
- Typical usage with Poetry:

```bash
poetry run svc-auth --help
```

## One-by-one scaffolding (recommended)

Generate only what you need, where you want it. Use `--overwrite` to replace existing files.

- Models
  - `poetry run svc-auth scaffold-auth-models --dest-dir src/my_app/auth`
  - Creates: `models.py`

- Schemas
  - `poetry run svc-auth scaffold-auth-schemas --dest-dir src/my_app/auth`
  - Creates: `schemas.py`

- Settings
  - `poetry run svc-auth scaffold-auth-settings --dest-dir src/my_app/auth`
  - Creates: `settings.py`

Notes
- `--overwrite` is supported on every command.

## Batch scaffolding (all at once)

```bash
poetry run svc-auth scaffold-auth \
  --models-dir src/my_app/models \
  --schemas-dir src/my_app/schemas \
  --settings-dir src/my_app/auth
```

Creates
- `models.py`, `schemas.py`, `settings.py`

## Wire it into your FastAPI app

- DB helper (packaged, no scaffolding needed):
  - `from svc_infra.api.fastapi.db import attach_to_app, health_router`
  - Attach DB on startup: `attach_to_app(app, dsn_env="DATABASE_URL")`
  - Optional health route: `app.include_router(health_router())  # default "/_db/health"`
  - `include_auth(app)`

## Requirements

- Register DB lifecycle once at startup: `attach_to_app(app, dsn_env="DATABASE_URL")`
- Auth settings via env (examples):
  - `AUTH_JWT_SECRET`, `AUTH_JWT_LIFETIME_SECONDS`
  - Optional OAuth: `AUTH_GOOGLE_CLIENT_ID`, `AUTH_GOOGLE_CLIENT_SECRET`, etc.

## Troubleshooting

- Async driver errors (psycopg2, pymysql, sqlite)
  - When using the packaged DB helpers, sync URLs are coerced to async (asyncpg/aiomysql/aiosqlite).
  - If writing your own integration, use async drivers: `postgresql+asyncpg://`, `mysql+aiomysql://`, `sqlite+aiosqlite://`.
