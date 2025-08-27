## svc_infra db CLI

Alembic helper CLI for init and migrations.

Usage
- Script: svc-infra db
- Poetry: poetry run svc-infra db --help

Quick start
- init:
  poetry run svc-infra db init --database-url postgresql+asyncpg://user:pass@localhost/db --discover-packages my_app --async-db
- revision:
  poetry run svc-infra db revision -m "init" --autogenerate
- upgrade:
  poetry run svc-infra db upgrade head

Commands
- init [--project-root PATH] [--database-url URL] [--async-db|--no-async-db] [--discover-packages pkgs]
- revision -m MSG [--autogenerate] [--project-root PATH] [--database-url URL]
- upgrade [REV]
- downgrade [REV]
- current [--verbose]
- history [--verbose]
- stamp [REV]
- drop-table TABLE [--cascade] [--if-exists] [-m MSG] [--base REV] [--apply]
- merge-heads [-m MSG]

Notes
- Run in your app root (where alembic.ini/migrations/ live) or pass --project-root.
- Set DATABASE_URL or pass --database-url.
- Autogenerate discovers models under packages in --discover-packages or ALEMBIC_DISCOVER_PACKAGES.
