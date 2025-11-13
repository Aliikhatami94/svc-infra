from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Sequence, Set, Union

from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy import inspect, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import DBAPIError, OperationalError

from .constants import ASYNC_DRIVER_HINT, DEFAULT_DB_ENV_VARS

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
        - Does NOT set SQL_URL (expect it to be set in your .env / environment).
        - Discovery is automatic via env.py. 'discover_packages' is kept for
          backward-compat only; prefer leaving it None.
    """
    root = Path(project_root).resolve()
    load_dotenv(dotenv_path=root / ".env", override=False)
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
    driver = os.getenv("DB_DRIVER", "").strip()  # e.g. asyncpg, psycopg, pymysql, aiosqlite
    host = os.getenv("DB_HOST", "").strip() or None
    port = os.getenv("DB_PORT", "").strip() or None
    db = os.getenv("DB_NAME", "").strip() or None
    user = os.getenv("DB_USER", "").strip() or None
    pwd = os.getenv("DB_PASSWORD", "").strip() or None
    params = os.getenv("DB_PARAMS", "").strip() or ""

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
    env_vars: Sequence[str] = DEFAULT_DB_ENV_VARS,
) -> Optional[str]:
    """
    Resolve the database connection string, with support for:
      - Primary env vars (in order): DEFAULT_DB_ENV_VARS (e.g. SQL_URL, PRIVATE_SQL_URL, DB_URL).
      - Secret file pointers: <NAME>_FILE (reads file contents).
      - Well-known locations: SQL_URL_FILE, /run/secrets/database_url.
      - Composed from parts: DB_* (host, port, name, user, password, params).
    When a value is found, it is also written back into os.environ["SQL_URL"] for downstream code.
    """
    # Load .env without clobbering existing process env
    load_dotenv(override=False)

    # 1) Direct envs (and support "file:" or absolute path values)
    for key in env_vars:
        val = os.getenv(key)
        if val and val.strip():
            s = val.strip()
            # Some platforms inject a file-pointer-like value
            if s.startswith("file:"):
                s = s[5:]
            if os.path.isabs(s) and Path(s).exists():
                file_val = _read_secret_from_file(s)
                if file_val:
                    os.environ["SQL_URL"] = file_val
                    return file_val
            os.environ["SQL_URL"] = s
            return s

        # Companion NAME_FILE secret path (e.g., SQL_URL_FILE)
        file_key = f"{key}_FILE"
        file_path = os.getenv(file_key)
        if file_path:
            file_val = _read_secret_from_file(file_path)
            if file_val:
                os.environ["SQL_URL"] = file_val
                return file_val

    # 2) Conventional secret envs
    file_path = os.getenv("SQL_URL_FILE")
    if file_path:
        file_val = _read_secret_from_file(file_path)
        if file_val:
            os.environ["SQL_URL"] = file_val
            return file_val

    # 3) Docker/K8s default secret mount
    file_val = _read_secret_from_file("/run/secrets/database_url")
    if file_val:
        os.environ["SQL_URL"] = file_val
        return file_val

    # 4) Compose from parts (DB_DIALECT/DB_DRIVER/DB_HOST/.../DB_PARAMS)
    composed = _compose_url_from_parts()
    if composed:
        os.environ["SQL_URL"] = composed
        return composed

    if required:
        raise RuntimeError(
            "Database URL not set. Set SQL_URL (or PRIVATE_SQL_URL / DB_URL), "
            "or provide DB_* parts (DB_HOST, DB_NAME, etc.), or a *_FILE secret."
        )
    return None


def _ensure_timeout_default(u: URL) -> URL:
    """
    Ensure a conservative connection timeout is present for libpq-based drivers.
    For psycopg/psycopg2, 'connect_timeout' is honored via the query string.
    For asyncpg, timeout is set via connect_args (not query string).
    """
    backend = (u.get_backend_name() or "").lower()
    if backend not in ("postgresql", "postgres"):
        return u

    # asyncpg doesn't support connect_timeout in query string - use connect_args instead
    dn = (u.drivername or "").lower()
    if "+asyncpg" in dn:
        return u

    if "connect_timeout" in u.query:
        return u
    # Default 10s unless overridden
    t = int(os.getenv("DB_CONNECT_TIMEOUT", "10"))
    return u.set(query={**u.query, "connect_timeout": str(t)})


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


def _coerce_to_async_url(url: str) -> str:
    """Coerce common sync driver URLs to async-capable URLs.

    - postgresql:// or postgres://        -> postgresql+asyncpg://
    - postgresql+psycopg2:// or +psycopg  -> postgresql+asyncpg://
    - mysql:// or mysql+pymysql://        -> mysql+aiomysql://
    - sqlite://                           -> sqlite+aiosqlite://
    If already async (contains +asyncpg/+aiomysql/+aiosqlite), leave unchanged.
    """
    low = url.lower()
    if "+asyncpg" in low or "+aiomysql" in low or "+aiosqlite" in low:
        return url
    if low.startswith("postgresql+psycopg2://"):
        return "postgresql+asyncpg://" + url.split("://", 1)[1]
    if low.startswith("postgresql+psycopg://"):
        return "postgresql+asyncpg://" + url.split("://", 1)[1]
    if low.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.split("://", 1)[1]
    if low.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.split("://", 1)[1]
    if low.startswith("mysql+pymysql://") or low.startswith("mysql://"):
        return "mysql+aiomysql://" + url.split("://", 1)[1]
    if low.startswith("sqlite://") and not low.startswith("sqlite+aiosqlite://"):
        return "sqlite+aiosqlite://" + url.split("://", 1)[1]
    return url


def _is_mod_available(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def _coerce_sync_driver(u: URL) -> URL:
    """
    If URL has no explicit sync driver, pick one that’s available.
    Postgres preference: psycopg (v3) → psycopg2
    Optional override: DB_FORCE_DRIVER=psycopg|psycopg2
    """
    dn = (u.drivername or "").lower()
    if "+" in dn:
        return u

    backend = (u.get_backend_name() or "").lower()
    if backend in ("postgresql", "postgres"):
        force = (os.getenv("DB_FORCE_DRIVER") or "").strip().lower()
        if force in {"psycopg", "psycopg2"}:
            return u.set(drivername=f"postgresql+{force}")

        # prefer psycopg v3 if present; else psycopg2; else leave bare (SA default)
        if _is_mod_available("psycopg"):
            return u.set(drivername="postgresql+psycopg")
        if _is_mod_available("psycopg2"):
            return u.set(drivername="postgresql+psycopg2")
        return u

    if backend == "mysql":
        if _is_mod_available("pymysql"):
            return u.set(drivername="mysql+pymysql")
        return u

    if backend == "sqlite":
        return u

    if backend in ("mssql",):
        if _is_mod_available("pyodbc"):
            return u.set(drivername="mssql+pyodbc")
        return u

    return u


def _coerce_pg_maintenance_driver(u: URL) -> URL:
    """
    Ensure the maintenance connection for Postgres uses a sync driver that is installed,
    because ensure_database_exists() often needs a *sync* connection for CREATE DATABASE.
    """
    # If async → leave to async branch; this is for sync path only.
    if "+" in (u.drivername or ""):
        # If explicit async driver was given, leave it (caller decides).
        return u
    backend = (u.get_backend_name() or "").lower()
    if backend in ("postgresql", "postgres"):
        # prefer psycopg, then psycopg2
        if _is_mod_available("psycopg"):
            return u.set(drivername="postgresql+psycopg")
        if _is_mod_available("psycopg2"):
            return u.set(drivername="postgresql+psycopg2")
    return u


def _ensure_ssl_default(u: URL) -> URL:
    backend = (u.get_backend_name() or "").lower()
    if backend not in ("postgresql", "postgres"):
        return u

    driver = (u.drivername or "").lower()

    # If any SSL hint already present, do nothing
    if any(k in u.query for k in ("sslmode", "ssl", "sslrootcert", "sslcert", "sslkey")):
        return u

    # Allow env override; support both common spellings
    mode_env = os.getenv("DB_SSLMODE_DEFAULT") or os.getenv("PGSSLMODE") or os.getenv("PGSSL_MODE")
    mode = (mode_env or "").strip()

    if "+asyncpg" in driver:
        # asyncpg: SSL is handled in connect_args in build_engine(), not in URL query
        # Do not add ssl parameter to URL query for asyncpg
        return u
    else:
        # libpq-based drivers: use sslmode (default 'require' for hosted PG)
        mode = mode or "require"
        return u.set(query={**u.query, "sslmode": mode})


def _ensure_ssl_default_async(u: URL) -> URL:
    backend = (u.get_backend_name() or "").lower()
    if backend in ("postgresql", "postgres"):
        # asyncpg prefers 'ssl=true' via SQLAlchemy param; if already present, keep it
        if any(k in u.query for k in ("ssl", "sslmode", "sslrootcert", "sslcert", "sslkey")):
            return u
        return u.set(query={**u.query, "ssl": "true"})
    return u


def _certifi_ca() -> str | None:
    try:
        import certifi

        return certifi.where()
    except Exception:
        return None


def build_engine(url: URL | str, echo: bool = False) -> Union[SyncEngine, AsyncEngineType]:
    u = make_url(url) if isinstance(url, str) else url

    # Keep your existing PG helpers
    u = _ensure_ssl_default(u)
    u = _ensure_timeout_default(u)

    connect_args: dict[str, Any] = {}

    # ----------------- ASYNC -----------------
    if is_async_url(u):
        if _create_async_engine is None:
            raise RuntimeError(
                "Async driver URL provided but SQLAlchemy async extras are not available."
            )

        # asyncpg: honor connection timeout only (NOT connect_timeout)
        if "+asyncpg" in (u.drivername or ""):
            connect_args["timeout"] = int(os.getenv("DB_CONNECT_TIMEOUT", "10"))

            # asyncpg doesn't accept sslmode or ssl=true in query params
            # Remove these and set ssl='require' in connect_args
            if "ssl" in u.query or "sslmode" in u.query:
                new_query = {k: v for k, v in u.query.items() if k not in ("ssl", "sslmode")}
                u = u.set(query=new_query)
            # Set ssl in connect_args - 'require' is safest for hosted databases
            connect_args["ssl"] = "require"

        # NEW: aiomysql SSL default
        if "+aiomysql" in (u.drivername or "") and not any(
            k in u.query for k in ("ssl", "ssl_ca", "sslmode")
        ):
            # aiomysql accepts an ssl.SSLContext or True
            try:
                import ssl

                ca = _certifi_ca()
                ctx = ssl.create_default_context(cafile=ca) if ca else ssl.create_default_context()
                # if your host uses a public CA, verification works;
                # if not, you can relax verification (not recommended):
                #   ctx.check_hostname = False
                #   ctx.verify_mode = ssl.CERT_NONE
                connect_args["ssl"] = ctx
            except Exception:
                connect_args["ssl"] = True  # minimal hint to enable TLS

        kwargs: dict[str, Any] = {"echo": echo, "pool_pre_ping": True}
        if connect_args:
            kwargs["connect_args"] = connect_args
        return _create_async_engine(u, **kwargs)

    # ----------------- SYNC -----------------
    u = _coerce_sync_driver(u)
    if _create_engine is None:
        raise RuntimeError("SQLAlchemy create_engine is not available in this environment.")

    dn = (u.drivername or "").lower()

    # psycopg v3 quirk (optional)
    if dn.startswith("postgresql+psycopg") and u.password:
        connect_args["password"] = u.password

    # NEW: pymysql SSL default
    if dn.startswith("mysql+pymysql") and not any(
        k in u.query for k in ("ssl", "ssl_ca", "sslmode")
    ):
        ca = _certifi_ca()
        if ca:
            # PyMySQL expects a dict of SSL args; 'ca' is the common one
            connect_args["ssl"] = {"ca": ca}
        else:
            # Fallback: empty dict enables TLS without CA pinning (works on many hosts)
            connect_args["ssl"] = {}

        # Optional: if your provider requires it, you can also add:
        # connect_args.setdefault("client_flag", 0)

    kwargs: dict[str, Any] = {"echo": echo, "pool_pre_ping": True}
    if connect_args:
        kwargs["connect_args"] = connect_args
    return _create_engine(u, **kwargs)


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
    return name.replace("`", "``")


# ---------- Database bootstrap (per-dialect) ----------


async def _pg_create_database_async(url: URL) -> None:
    assert is_async_url(url)
    target_db = url.database
    if not target_db:
        return

    u = _ensure_ssl_default(make_url(url))
    maintenance_url = with_database(u, "postgres")
    engine: AsyncEngineType = build_engine(maintenance_url)  # type: ignore[assignment]

    try:
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
    except DBAPIError as e:
        if "permission denied" in str(e).lower():
            pass
        else:
            raise
    finally:
        await engine.dispose()


def _pg_create_database_sync(url: URL) -> None:
    target_db = url.database
    if not target_db:
        return

    # Build a maintenance URL pointing at the 'postgres' DB
    u = _ensure_ssl_default(make_url(url))
    maintenance_url = with_database(u, "postgres")

    # Make sure it has an installed *sync* driver (psycopg or psycopg2)
    maintenance_url = _coerce_pg_maintenance_driver(maintenance_url)

    # Try connecting to 'postgres'; if that fails (some hosts restrict it), try 'template1'
    try:
        engine: SyncEngine = build_engine(maintenance_url)  # type: ignore[assignment]
    except Exception:
        alt_url = with_database(maintenance_url, "template1")
        engine = build_engine(alt_url)  # type: ignore[assignment]

    try:
        with engine.begin() as conn:
            exists = conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": target_db},
            )
            if not exists:
                quoted = _pg_quote_ident(target_db)
                conn.execution_options(isolation_level="AUTOCOMMIT").execute(
                    text(f'CREATE DATABASE "{quoted}"')
                )
    except DBAPIError as e:
        # If permission error, log and continue (DB likely pre-provisioned on the host)
        if "permission denied" in str(e).lower():
            pass
        else:
            raise
    finally:
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
            exists = conn.scalar(
                text("SELECT 1 AS one FROM sys.databases WHERE name = :name"),
                {"name": target_db},
            )
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
            exists = await conn.scalar(
                text("SELECT 1 AS one FROM sys.databases WHERE name = :name"),
                {"name": target_db},
            )
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
    if url is None:
        raise RuntimeError(
            "ensure_database_exists: database URL is required but None was provided."
        )
    u = make_url(url) if isinstance(url, str) else url
    backend = (u.get_backend_name() or "").lower()

    if backend.startswith("sqlite"):
        _sqlite_prepare_filesystem(u)
        return
    if backend.startswith("duckdb"):
        _duckdb_prepare_filesystem(u)
        return

    if backend.startswith(("postgresql", "postgres")):
        return (
            asyncio.run(_pg_create_database_async(u))
            if is_async_url(u)
            else _pg_create_database_sync(u)
        )
    if backend.startswith(("mysql", "mariadb")):
        return (
            asyncio.run(_mysql_create_database_async(u))
            if is_async_url(u)
            else _mysql_create_database_sync(u)
        )
    if backend.startswith(("cockroach", "cockroachdb")):
        return (
            asyncio.run(_cockroach_create_database_async(u))
            if is_async_url(u)
            else _cockroach_create_database_sync(u)
        )
    if backend.startswith("mssql"):
        return (
            asyncio.run(_mssql_create_database_async(u))
            if is_async_url(u)
            else _mssql_create_database_sync(u)
        )
    if backend.startswith("snowflake"):
        return (
            asyncio.run(_snowflake_create_database_async(u))
            if is_async_url(u)
            else _snowflake_create_database_sync(u)
        )
    if backend.startswith("redshift"):
        return (
            asyncio.run(_redshift_create_database_async(u))
            if is_async_url(u)
            else _redshift_create_database_sync(u)
        )

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
    """If DB points to a non-existent local revision, reset to base (drop alembic_version)."""
    db_url = cfg.get_main_option("sqlalchemy.url") or os.getenv("SQL_URL")
    if not db_url:
        return

    # Gather local revision ids from versions/
    script_location = Path(cfg.get_main_option("script_location"))
    versions_dir = script_location / "versions"
    local_ids: Set[str] = set()
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

    url_obj = make_url(db_url)
    if is_async_url(url_obj):

        async def _run() -> None:
            eng = build_engine(url_obj)  # AsyncEngine
            try:
                async with eng.begin() as conn:
                    # Do sync-y inspector / SQL via run_sync
                    def _check_and_maybe_drop(sync_conn):
                        insp = inspect(sync_conn)
                        if not insp.has_table("alembic_version"):
                            return
                        rows = list(
                            sync_conn.execute(
                                text("SELECT version_num FROM alembic_version")
                            ).fetchall()
                        )
                        missing = any((ver not in local_ids) for (ver,) in rows)
                        if missing:
                            sync_conn.execute(text("DROP TABLE IF EXISTS alembic_version"))

                    await conn.run_sync(_check_and_maybe_drop)
            finally:
                await eng.dispose()

        asyncio.run(_run())
    else:
        eng = build_engine(url_obj)  # sync Engine
        try:
            with eng.begin() as c:
                insp = inspect(c)
                if not insp.has_table("alembic_version"):
                    return
                rows = list(c.execute(text("SELECT version_num FROM alembic_version")).fetchall())
                missing = any((ver not in local_ids) for (ver,) in rows)
                if missing:
                    c.execute(text("DROP TABLE IF EXISTS alembic_version"))
        finally:
            eng.dispose()


def render_env_py(packages: Sequence[str], *, async_db: bool | None = None) -> str:
    """Render Alembic env.py content from packaged templates.

    - If async_db is None, detect from SQL_URL; default to sync if unknown.
    """
    import importlib.resources as pkg

    from sqlalchemy.engine import make_url as _make_url

    if async_db is None:
        try:
            db_url = get_database_url_from_env(required=False)
            async_db = bool(db_url and is_async_url(_make_url(db_url)))
        except Exception:
            async_db = False

    pkg_list = ", ".join(repr(p) for p in packages)
    tmpl_root = pkg.files("svc_infra.db.sql.templates.setup")
    name = "env_async.py.tmpl" if async_db else "env_sync.py.tmpl"
    txt = tmpl_root.joinpath(name).read_text(encoding="utf-8")
    return txt.replace("__PACKAGES_LIST__", pkg_list)


def build_alembic_config(
    project_root: Path | str, *, script_location: str = "migrations"
) -> Config:
    from alembic.config import Config as _Config

    root = Path(project_root).resolve()
    cfg_path = root / "alembic.ini"
    cfg = _Config(str(cfg_path)) if cfg_path.exists() else _Config()
    cfg.set_main_option("script_location", str((root / script_location).resolve()))

    env_db_url = os.getenv("SQL_URL", "").strip()
    if env_db_url:
        u = make_url(env_db_url)
        u = _ensure_ssl_default(u)
        if not is_async_url(u):
            u = _coerce_sync_driver(u)
        cfg.set_main_option("sqlalchemy.url", u.render_as_string(hide_password=False))

    # >>> ADD THIS GUARD <<<
    if not cfg.get_main_option("sqlalchemy.url"):
        raise RuntimeError(
            "No SQLAlchemy URL resolved. Pass `database_url` to the calling function "
            "or set SQL_URL in the environment."
        )

    cfg.set_main_option("path_separator", "os")
    cfg.set_main_option("prepend_sys_path", str(root))
    return cfg


def ensure_db_at_head(cfg: Config) -> None:
    """Idempotently bring the database to head; safe if already current."""
    from alembic import command as _command

    _command.upgrade(cfg, "head")


__all__ = [
    # env helpers
    "get_database_url_from_env",
    "is_async_url",
    "with_database",
    # engines and db bootstrap
    "build_engine",
    "ensure_database_exists",
    # setup helpers
    "render_env_py",
    "build_alembic_config",
    "ensure_db_at_head",
]
