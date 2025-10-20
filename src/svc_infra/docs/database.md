# Database guide

svc-infra exposes helpers for SQLAlchemy and Mongo so APIs get lifecycle management, migrations, and connection URLs from environment variables.

## SQL

- `add_sql_db(app, url=None, dsn_env="SQL_URL")` wires the session and raises if the URL env is missing. 【F:src/svc_infra/api/fastapi/db/sql/add.py†L55-L114】
- Build URLs piecemeal with `DB_DIALECT`, `DB_DRIVER`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PARAMS`, or point at `SQL_URL_FILE`/`DB_PASSWORD_FILE`. 【F:src/svc_infra/db/sql/utils.py†L85-L206】
- Alembic templates respect overrides such as `ALEMBIC_DISCOVER_PACKAGES`, `ALEMBIC_INCLUDE_SCHEMAS`, and `ALEMBIC_SKIP_DROPS`. 【F:src/svc_infra/db/sql/utils.py†L274-L347】

## Mongo

- `add_mongo_db(app, dsn_env="MONGO_URL")` validates the URL and optional db name. 【F:src/svc_infra/api/fastapi/db/nosql/mongo/add.py†L28-L53】
- Configure via `MONGO_URL`, `MONGO_DB`, `MONGO_APPNAME`, `MONGO_MIN_POOL`, `MONGO_MAX_POOL`, or point at `MONGO_URL_FILE`. 【F:src/svc_infra/db/nosql/mongo/settings.py†L9-L13】【F:src/svc_infra/db/nosql/utils.py†L56-L113】
