from __future__ import annotations

import os
import asyncio
from pathlib import Path
from typing import Any, Optional, Sequence, Union, TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import OperationalError

from .constants import DEFAULT_DB_ENV_VARS, ASYNC_DRIVER_HINT

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine as SyncEngine
    from sqlalchemy.ext.asyncio import AsyncEngine as AsyncEngineType
else:
    SyncEngine = Any  # type: ignore
    AsyncEngineType = Any  # type: ignore

try:
    # Runtime import (may be missing if async extras aren’t installed)
    from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine  # type: ignore
except Exception:  # pragma: no cover - optional dep
    _create_async_engine = None  # type: ignore

try:
    from sqlalchemy import create_engine as _create_engine  # type: ignore
except Exception:  # pragma: no cover - optional env
    _create_engine = None  # type: ignore


# ---------- Environment helpers ----------

def get_database_url_from_env(required: bool = True, env_vars: Sequence[str] = DEFAULT_DB_ENV_VARS) -> str | None:
    """Return the first non-empty database URL from environment.

    Env precedence: DATABASE_URL, DB_URL (by default).
    If required and none found, raises RuntimeError.
    """
    for key in env_vars:
        val = os.getenv(key)
        if val and val.strip():
            return val.strip()
    if required:
        raise RuntimeError(
            f"Database URL not set. Expect one of {', '.join(env_vars)} to be defined in environment."
        )
    return None


# ---------- URL utilities ----------

def is_async_url(url: URL | str) -> bool:
    u = make_url(url) if isinstance(url, str) else url
    dn = u.drivername or ""
    return bool(ASYNC_DRIVER_HINT.search(dn))


def with_database(url: URL | str, database: Optional[str]) -> URL:
    """Return a copy of URL with the database name replaced.

    Works for most dialects. For SQLite/DuckDB file URLs, `database` is the file path.
    """
    u = make_url(url) if isinstance(url, str) else url
    return u.set(database=database)


# ---------- Engine creation ----------

def build_engine(url: URL | str, echo: bool = False) -> Union[SyncEngine, AsyncEngineType]:
    u = make_url(url) if isinstance(url, str) else url
    if is_async_url(u):
        if _create_async_engine is None:
            raise RuntimeError("Async driver URL provided but SQLAlchemy async extras are not available.")
        assert _create_async_engine is not None  # for type-checkers
        return _create_async_engine(u, echo=echo, pool_pre_ping=True)
    if _create_engine is None:
        raise RuntimeError("SQLAlchemy create_engine is not available in this environment.")
    assert _create_engine is not None  # for type-checkers
    return _create_engine(u, echo=echo, pool_pre_ping=True)


# ---------- Identifier quoting helpers ----------

def _pg_quote_ident(name: str) -> str:
    """
    Escape embedded double quotes for PostgreSQL identifiers.
    Caller must wrap with double quotes.
    """
    if name is None:
        raise ValueError("Identifier cannot be None")
    return name.replace('"', '""')


def _mysql_quote_ident(name: str) -> str:
    """
    Escape embedded backticks for MySQL/MariaDB identifiers.
    Caller must wrap with backticks.
    """
    if name is None:
        raise ValueError("Identifier cannot be None")
    return name.replace('`', '``')


# ---------- Database bootstrap (per-dialect) ----------

async def _pg_create_database_async(url: URL) -> None:
    assert is_async_url(url)
    target_db = url.database
    if not target_db:
        return

    maintenance_url = with_database(url, "postgres")
    engine: AsyncEngineType = build_engine(maintenance_url)  # type: ignore[assignment]
    async with engine.begin() as conn:
        exists = await conn.scalar(
            text("SELECT 1 AS one FROM pg_database WHERE datname = :name"),
            {"name": target_db},
        )
        if not exists:
            quoted = _pg_quote_ident(target_db)
            await conn.execution_options(isolation_level="AUTOCOMMIT").execute(
                text(f'CREATE DATABASE "{quoted}"')
            )
    await engine.dispose()


def _pg_create_database_sync(url: URL) -> None:
    target_db = url.database
    if not target_db:
        return
    maintenance_url = with_database(make_url(url), "postgres")
    engine: SyncEngine = build_engine(maintenance_url)  # type: ignore[assignment]
    with engine.begin() as conn:
        exists = conn.scalar(
            text("SELECT 1 AS one FROM pg_database WHERE datname = :name"),
            {"name": target_db},
        )
        if not exists:
            quoted = _pg_quote_ident(target_db)
            conn.execution_options(isolation_level="AUTOCOMMIT").execute(
                text(f'CREATE DATABASE "{quoted}"')
            )
    engine.dispose()


async def _mysql_create_database_async(url: URL) -> None:
    target_db = url.database
    if not target_db:
        return
    base_url = with_database(url, None)
    engine: AsyncEngineType = build_engine(base_url)  # type: ignore[assignment]
    async with engine.begin() as conn:
        exists = await conn.scalar(
            text("SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = :name"),
            {"name": target_db},
        )
        if not exists:
            quoted = _mysql_quote_ident(target_db)
            await conn.execute(text(f"CREATE DATABASE `{quoted}`"))
    await engine.dispose()


def _mysql_create_database_sync(url: URL) -> None:
    target_db = url.database
    if not target_db:
        return
    base_url = with_database(url, None)
    engine: SyncEngine = build_engine(base_url)  # type: ignore[assignment]
    with engine.begin() as conn:
        exists = conn.scalar(
            text("SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = :name"),
            {"name": target_db},
        )
        if not exists:
            quoted = _mysql_quote_ident(target_db)
            conn.execute(text(f"CREATE DATABASE `{quoted}`"))
    engine.dispose()


def _sqlite_prepare_filesystem(url: URL) -> None:
    # file-based sqlite path e.g., sqlite:////tmp/file.db or sqlite+pysqlite:////path
    database = url.database
    if not database or database in {":memory:", "memory:"}:
        return
    try:
        path = Path(database)
    except Exception:
        return
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


# ---- Extra dialect helpers (best-effort) ------------------------------------


def _duckdb_prepare_filesystem(url: URL) -> None:
    # duckdb:///path/to/file.duckdb (or :memory:)
    database = url.database
    if not database or database in {":memory:", "memory:"}:
        return
    try:
        path = Path(database)
    except Exception:
        return
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


def _cockroach_create_database_sync(url: URL) -> None:
    target_db = url.database
    if not target_db:
        return
    base_url = with_database(url, None)
    eng: SyncEngine = build_engine(base_url)  # type: ignore[assignment]
    try:
        with eng.begin() as conn:
            conn.execute(text(f'CREATE DATABASE IF NOT EXISTS "{target_db}"'))
    finally:
        eng.dispose()


async def _cockroach_create_database_async(url: URL) -> None:
    target_db = url.database
    if not target_db:
        return
    base_url = with_database(url, None)
    engine: AsyncEngineType = build_engine(base_url)  # type: ignore[assignment]
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f'CREATE DATABASE IF NOT EXISTS "{target_db}"'))
    finally:
        await engine.dispose()


def _mssql_create_database_sync(url: URL) -> None:
    target_db = url.database
    if not target_db:
        return
    master_url = with_database(url, "master")
    eng: SyncEngine = build_engine(master_url)  # type: ignore[assignment]
    try:
        with eng.begin() as conn:
            exists = conn.scalar(text("SELECT 1 AS one FROM sys.databases WHERE name = :name"), {"name": target_db})
            if not exists:
                conn.execute(text(f"CREATE DATABASE [{target_db}]"))
    finally:
        eng.dispose()


async def _mssql_create_database_async(url: URL) -> None:
    target_db = url.database
    if not target_db:
        return
    master_url = with_database(url, "master")
    engine: AsyncEngineType = build_engine(master_url)  # type: ignore[assignment]
    try:
        async with engine.begin() as conn:
            exists = await conn.scalar(text("SELECT 1 AS one FROM sys.databases WHERE name = :name"), {"name": target_db})
            if not exists:
                await conn.execute(text(f"CREATE DATABASE [{target_db}]"))
    finally:
        await engine.dispose()


def _snowflake_create_database_sync(url: URL) -> None:
    target_db = url.database
    if not target_db:
        return
    base_url = with_database(url, None)
    eng: SyncEngine = build_engine(base_url)  # type: ignore[assignment]
    try:
        with eng.begin() as conn:
            conn.execute(text(f'CREATE DATABASE IF NOT EXISTS "{target_db}"'))
    finally:
        eng.dispose()


async def _snowflake_create_database_async(url: URL) -> None:
    target_db = url.database
    if not target_db:
        return
    base_url = with_database(url, None)
    engine: AsyncEngineType = build_engine(base_url)  # type: ignore[assignment]
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f'CREATE DATABASE IF NOT EXISTS "{target_db}"'))
    finally:
        await engine.dispose()


def _redshift_create_database_sync(url: URL) -> None:
    target_db = url.database
    if not target_db:
        return
    base_url = with_database(url, None)
    try:
        eng: SyncEngine = build_engine(base_url)  # type: ignore[assignment]
    except Exception:
        eng = build_engine(with_database(url, "dev"))  # type: ignore[assignment]
    try:
        with eng.begin() as conn:
            exists = conn.scalar(
                text("SELECT 1 AS one FROM pg_database WHERE datname = :name"),
                {"name": target_db},
            )
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{target_db}"'))
    finally:
        eng.dispose()


async def _redshift_create_database_async(url: URL) -> None:
    target_db = url.database
    if not target_db:
        return
    base_url = with_database(url, None)
    try:
        engine: AsyncEngineType = build_engine(base_url)  # type: ignore[assignment]
    except Exception:
        engine = build_engine(with_database(url, "dev"))  # type: ignore[assignment]
    try:
        async with engine.begin() as conn:
            exists = await conn.scalar(
                text("SELECT 1 AS one FROM pg_database WHERE datname = :name"),
                {"name": target_db},
            )
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{target_db}"'))
    finally:
        await engine.dispose()


# ---------- Entry: ensure database ----------

def ensure_database_exists(url: URL | str) -> None:
    u = make_url(url) if isinstance(url, str) else url
    backend = (u.get_backend_name() or "").lower()

    if backend.startswith("sqlite"):
        _sqlite_prepare_filesystem(u)
        return
    if backend.startswith("duckdb"):
        _duckdb_prepare_filesystem(u)
        return

    if backend.startswith(("postgresql", "postgres")):
        return asyncio.run(_pg_create_database_async(u)) if is_async_url(u) else _pg_create_database_sync(u)
    if backend.startswith(("mysql", "mariadb")):
        return asyncio.run(_mysql_create_database_async(u)) if is_async_url(u) else _mysql_create_database_sync(u)
    if backend.startswith(("cockroach", "cockroachdb")):
        return asyncio.run(_cockroach_create_database_async(u)) if is_async_url(u) else _cockroach_create_database_sync(u)
    if backend.startswith("mssql"):
        return asyncio.run(_mssql_create_database_async(u)) if is_async_url(u) else _mssql_create_database_sync(u)
    if backend.startswith("snowflake"):
        return asyncio.run(_snowflake_create_database_async(u)) if is_async_url(u) else _snowflake_create_database_sync(u)
    if backend.startswith("redshift"):
        return asyncio.run(_redshift_create_database_async(u)) if is_async_url(u) else _redshift_create_database_sync(u)

    # Fallback: just ping
    try:
        eng = build_engine(u)
        if is_async_url(u):
            async def _ping_and_dispose():
                async with eng.begin() as conn:  # type: ignore[call-arg]
                    await conn.execute(text("SELECT 1"))
                await eng.dispose()  # type: ignore[attr-defined]
            asyncio.run(_ping_and_dispose())
        else:
            with eng.begin() as conn:  # type: ignore[call-arg]
                conn.execute(text("SELECT 1"))
            eng.dispose()  # type: ignore[attr-defined]
    except OperationalError as exc:  # pragma: no cover (depends on env)
        raise RuntimeError(f"Failed to connect to database: {exc}") from exc


__all__ = [
    # env helpers
    "get_database_url_from_env",
    "is_async_url",
    "with_database",
    # engines and db bootstrap
    "build_engine",
    "ensure_database_exists",
]
