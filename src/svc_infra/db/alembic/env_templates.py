from __future__ import annotations

import os


def write_async_env_template(cwd: str = ".") -> str:
    """
    Write a production-ready Alembic env.py template that works with async engines
    by using a sync engine for migrations. Returns the path written.
    """
    alembic_env_dir = os.path.join(cwd, "migrations")
    env_py = os.path.join(alembic_env_dir, "env.py")
    os.makedirs(alembic_env_dir, exist_ok=True)
    content = '''
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import create_engine
from alembic import context

from svc_infra.db.settings import get_db_settings
from svc_infra.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def _sync_url_from_cfg() -> str:
    cfg = get_db_settings()
    url = cfg.resolved_database_url
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "")
    if url.startswith("sqlite+aiosqlite"):
        url = url.replace("sqlite+aiosqlite", "sqlite")
    return url

def run_migrations_offline() -> None:
    url = _sync_url_from_cfg()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = create_engine(_sync_url_from_cfg(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
'''
    with open(env_py, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    return env_py

