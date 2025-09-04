from __future__ import annotations

import os, asyncio
from sqlalchemy import inspect
from pathlib import Path
from typing import Any, Optional, Sequence, Union, TYPE_CHECKING
from alembic.config import Config

from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import OperationalError

from .constants import ASYNC_DRIVER_HINT

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


def prepare_process_env(
        project_root: Path | str,
        discover_packages: Optional[Sequence[str]] = None,
) -> None:
    """
    Prepare process environment so Alembic can import the project cleanly.

    Notes:
        - Does NOT set DATABASE_URL (expect it to be set in your .env / environment).
        - Discovery is automatic via env.py. 'discover_packages' is kept for
          backward-compat only; prefer leaving it None.
    """
    root = Path(project_root).resolve()
    os.environ.setdefault("SKIP_APP_INIT", "1")

    # Make <project>/src importable (env.py also handles this defensively)
    src_dir = root / "src"
    if src_dir.exists():
        sys_path = os.environ.get("PYTHONPATH", "")
        parts = [str(src_dir)] + ([sys_path] if sys_path else [])
        os.environ["PYTHONPATH"] = os.pathsep.join(parts)

    # Optional override (discouraged—automatic discovery is preferred)
    if discover_packages:
        os.environ["ALEMBIC_DISCOVER_PACKAGES"] = ",".join(discover_packages)

def _read_secret_from_file(path: str) -> Optional[str]:
    """Return file contents if path exists, else None."""
    try:
        p = Path(path)
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return None

def _compose_url_from_parts() -> Optional[str]:
    """
    Compose a SQLAlchemy URL from component env vars.
    Supports private DNS hostnames and Unix sockets.

    Recognized envs:
      DB_DIALECT (default: postgresql), DB_DRIVER (optional, e.g. asyncpg, psycopg),
      DB_HOST (hostname or Unix socket dir), DB_PORT,
      DB_NAME, DB_USER, DB_PASSWORD,
      DB_PARAMS (raw query string like 'sslmode=require&connect_timeout=5')
    """
    dialect = os.getenv("DB_DIALECT", "").strip() or "postgresql"
    driver  = os.getenv("DB_DRIVER", "").strip()      # e.g. asyncpg, psycopg, pymysql, aiosqlite
    host    = os.getenv("DB_HOST", "").strip() or None
    port    = os.getenv("DB_PORT", "").strip() or None
    db      = os.getenv("DB_NAME", "").strip() or None
    user    = os.getenv("DB_USER", "").strip() or None
    pwd     = os.getenv("DB_PASSWORD", "").strip() or None
    params  = os.getenv("DB_PARAMS", "").strip() or ""

    if not (host and db):
        return None

    # Build SQLAlchemy URL safely
    drivername = f"{dialect}+{driver}" if driver else dialect
    query = dict(q.split("=", 1) for q in params.split("&") if q) if params else {}

    # URL.create handles unix socket paths when host begins with a slash
    try:
        url = URL.create(
            drivername=drivername,
            username=user or None,
            password=pwd or None,
            host=host if (host and not host.startswith("/")) else None,
            port=int(port) if (port and port.isdigit()) else None,
            database=db,
            query=query,
        )
        # If host is a unix socket dir, place it in query as host param many drivers understand
        if host and host.startswith("/"):
            # e.g. for psycopg/psycopg2: host=/cloudsql/instance; for MySQL: unix_socket=/path
            if "postgresql" in drivername:
                url = url.set(query={**url.query, "host": host})
            elif "mysql" in drivername:
                url = url.set(query={**url.query, "unix_socket": host})
        return str(url)
    except Exception:
        return None


# ---------- Environment helpers ----------

def get_database_url_from_env(
        required: bool = True,
        env_vars: Sequence[str] = ("DATABASE_URL", "PRIVATE_DATABASE_URL", "DB_URL")
) -> Optional[str]:
    """
    Resolve the database connection string, with support for:
      - Primary env vars: DATABASE_URL, PRIVATE_DATABASE_URL, DB_URL (in that order).
      - Secret file pointers: <NAME>_FILE (reads file contents).
      - Well-known locations: DATABASE_URL_FILE, /run/secrets/database_url.
      - Composed from parts: DB_* (host, port, name, user, password, params).
    This works for public or private networks—private DNS/socket addresses are just host strings.
    """
    # 1) Direct envs
    for key in env_vars:
        val = os.getenv(key)
        if val and val.strip():
            s = val.strip()
            # Some platforms inject "file:" or path-like values—read them
            if s.startswith("file:"):
                s = s[5:]
            if os.path.isabs(s) and Path(s).exists():
                file_val = _read_secret_from_file(s)
                if file_val:
                    return file_val
            return s

        # Companion NAME_FILE secret path
        file_key = f"{key}_FILE"
        file_path = os.getenv(file_key)
        if file_path:
            file_val = _read_secret_from_file(file_path)
            if file_val:
                return file_val

    # 2) Conventional secret envs
    for file_key in ("DATABASE_URL_FILE",):
        file_path = os.getenv(file_key)
        if file_path:
            file_val = _read_secret_from_file(file_path)
            if file_val:
                return file_val

    # 3) Docker/K8s default secret mount
    file_val = _read_secret_from_file("/run/secrets/database_url")
    if file_val:
        return file_val

    # 4) Compose from parts (supports private DNS / unix sockets)
    composed = _compose_url_from_parts()
    if composed:
        return composed

    if required:
        raise RuntimeError(
            "Database URL not set. Set DATABASE_URL (or PRIVATE_DATABASE_URL / DB_URL), "
            "or provide DB_* parts (DB_HOST, DB_NAME, etc.), or a *_FILE secret."
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
    """Create a SQLAlchemy Engine or AsyncEngine based on the URL.

    - If the URL uses an async driver, returns an AsyncEngine (requires async extras installed).
    - Otherwise returns a sync Engine.
    - Pass `echo=True` to enable SQL echoing.
    """
    u = make_url(url) if isinstance(url, str) else url
    if is_async_url(u):
        create_async = _create_async_engine
        if create_async is None:
            raise RuntimeError("Async driver URL provided but SQLAlchemy async extras are not available.")
        return create_async(u, echo=echo, pool_pre_ping=True)
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

def repair_alembic_state_if_needed(cfg: Config) -> None:
    """If DB points to a non-existent local revision, reset to base."""
    db_url = cfg.get_main_option("sqlalchemy.url") or os.getenv("DATABASE_URL")
    if not db_url:
        return

    # Collect local revision IDs
    script_location = Path(cfg.get_main_option("script_location"))
    versions_dir = script_location / "versions"
    local_ids = set()
    if versions_dir.exists():
        for p in versions_dir.glob("*.py"):
            try:
                txt = p.read_text(encoding="utf-8")
            except Exception:
                continue
            for line in txt.splitlines():
                line = line.strip()
                if line.startswith("revision ="):
                    rid = line.split("=", 1)[1].strip().strip("'\"")
                    local_ids.add(rid)
                    break

    eng = build_engine(db_url)
    try:
        with eng.begin() as c:
            insp = inspect(c)
            has_version_tbl = insp.has_table("alembic_version")

            rows = []
            if has_version_tbl:
                rows = c.execute(text("SELECT version_num FROM alembic_version")).fetchall()

            missing = any((ver not in local_ids) for (ver,) in rows)

            if missing:
                # safest reset: drop version table, caller will autogen + upgrade
                c.execute(text("DROP TABLE IF EXISTS alembic_version"))
    finally:
        eng.dispose()

__all__ = [
    # env helpers
    "get_database_url_from_env",
    "is_async_url",
    "with_database",
    # engines and db bootstrap
    "build_engine",
    "ensure_database_exists",
]
