from __future__ import annotations
import os
import sys
import asyncio
import logging
import pkgutil
import importlib
from pathlib import Path
from logging.config import fileConfig
from typing import Iterable, List, Set

from alembic import context
from sqlalchemy import pool
from sqlalchemy import engine_from_config
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import DeclarativeBase

# --- Ensure project root and src/ on sys.path ---
ROOT = Path(__file__).resolve().parents[1]  # migrations/ -> project root
for p in (ROOT, ROOT / "src"):
    s = str(p)
    if p.exists() and s not in sys.path:
        sys.path.insert(0, s)

# --- App logging (optional) ---
USE_APP_LOGGING = os.getenv("ALEMBIC_USE_APP_LOGGING", "1") == "1"
if USE_APP_LOGGING:
    try:
        from svc_infra.app.logging import setup_logging
        setup_logging(level=os.getenv("LOG_LEVEL"), fmt=os.getenv("LOG_FORMAT"))
        logging.getLogger(__name__).debug("Alembic using app logging setup.")
    except Exception as e:
        USE_APP_LOGGING = False
        print(f"[alembic] App logging import failed: {e}. Falling back to fileConfig.")

# --- Alembic config & logging ---
config = context.config
if not USE_APP_LOGGING and config.config_file_name is not None:
    fileConfig(config.config_file_name)
    logging.getLogger(__name__).debug("Alembic using fileConfig logging.")

# --- Database URL override via env ---
database_url = os.getenv("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

# --- Auto-discover model modules and collect all metadatas ---
# Comma-separated list of top-level packages to crawl. If empty, no-op.
DISCOVER_PKGS = os.getenv("ALEMBIC_DISCOVER_PACKAGES", "tests,svc_infra")

def _iter_pkg_modules(top_pkg_name: str) -> Iterable[str]:
    try:
        top_pkg = importlib.import_module(top_pkg_name)
    except Exception:
        return []
    if not hasattr(top_pkg, "__path__"):
        # it's a module, not a package
        return [top_pkg_name]
    names = []
    for m in pkgutil.walk_packages(top_pkg.__path__, prefix=top_pkg.__name__ + "."):
        names.append(m.name)
    return names

def import_all_under_packages(packages: Iterable[str]) -> None:
    # Import everything under the listed packages so Declarative models register with their Bases.
    for pkg_name in packages:
        if not pkg_name:
            continue
        for mod_name in _iter_pkg_modules(pkg_name):
            try:
                importlib.import_module(mod_name)
            except Exception as e:
                # Keep discovery resilient; noisy modules shouldn't break migrations
                logging.getLogger(__name__).debug(f"[alembic] Skipped import {mod_name}: {e}")

def collect_all_metadatas() -> List:
    # After imports, gather every DeclarativeBase subclass metadata.
    # This supports multiple Bases across packages.
    metas: Set = set()
    try:
        for cls in DeclarativeBase.__subclasses__():
            md = getattr(cls, "metadata", None)
            if md is not None:
                metas.add(md)
    except Exception:
        pass
    return list(metas)

pkgs = [p.strip() for p in (DISCOVER_PKGS or "").split(",") if p.strip()]
import_all_under_packages(pkgs)
metadatas = collect_all_metadatas()

# If nothing found, keep a harmless empty list; Alembic will no-op autogenerate.
target_metadata = metadatas

# --- Choose async/sync path from URL automatically ---
url_str = config.get_main_option("sqlalchemy.url") or ""
driver = ""
try:
    driver = make_url(url_str).get_dialect().driver  # 'asyncpg', 'psycopg2', etc.
except Exception:
    pass
is_async = driver in {"asyncpg", "aiosqlite"}

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online_async():
    from sqlalchemy.ext.asyncio import create_async_engine
    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
        future=True,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online_sync():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )
    with connectable.connect() as connection:
        do_run_migrations(connection)
    connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online_async())
