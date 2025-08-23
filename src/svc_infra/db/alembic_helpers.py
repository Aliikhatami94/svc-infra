from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional


def _alembic(cmd: str, *, cwd: str = ".", env: Optional[dict[str, str]] = None) -> int:
    e = os.environ.copy()
    e.setdefault("PYTHONPATH", os.getcwd())
    if env:
        e.update(env)
    return subprocess.check_call([sys.executable, "-m", "alembic"] + cmd.split(), cwd=cwd, env=e)


def init_migrations(cwd: str = ".") -> int:
    return _alembic("init migrations", cwd=cwd)


def make_migration(msg: str = "auto", cwd: str = ".") -> int:
    return _alembic(f"revision --autogenerate -m {msg!r}", cwd=cwd)


def upgrade(head: str = "head", cwd: str = ".") -> int:
    return _alembic(f"upgrade {head}", cwd=cwd)


def downgrade(target: str = "-1", cwd: str = ".") -> int:
    return _alembic(f"downgrade {target}", cwd=cwd)


def write_async_env_template(cwd: str = ".") -> str:
    """
    Write a production-ready Alembic env.py template that works with async engines
    by using a sync engine for migrations. Returns the path written.

    Expects Alembic to be initialized (alembic init migrations). Overwrites
    migrations/env.py if present.
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

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

def _sync_url_from_cfg() -> str:
    cfg = get_db_settings()
    url = cfg.resolved_database_url
    # Replace async driver with sync for Alembic engine
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "")
    if url.startswith("sqlite+aiosqlite"):
        url = url.replace("sqlite+aiosqlite", "sqlite")
    return url

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
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
    """Run migrations in 'online' mode."""
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


def ensure_initted(cwd: str = ".") -> None:
    """Ensure Alembic is initialized and uses the async-friendly env template."""
    ini_path = os.path.join(cwd, "alembic.ini")
    if not os.path.exists(ini_path):
        init_migrations(cwd)
    write_async_env_template(cwd)
