from __future__ import annotations

import os, re, asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Any, TYPE_CHECKING, Union
import importlib.resources as pkg

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import OperationalError

if TYPE_CHECKING:
    # Only for the IDE/type checker
    from sqlalchemy.engine import Engine as SyncEngine
    from sqlalchemy.ext.asyncio import AsyncEngine as AsyncEngineType
else:
    SyncEngine = Any  # type: ignore
    AsyncEngineType = Any  # type: ignore

try:
    # Runtime import (may be missing if async extras aren’t installed)
    from sqlalchemy.ext.asyncio import create_async_engine as _create_async_engine  # type: ignore
except Exception:
    _create_async_engine = None  # type: ignore

try:
    from sqlalchemy import create_engine as _create_engine  # type: ignore
except Exception:
    _create_engine = None  # type: ignore

# ---------- Environment helpers ----------

DEFAULT_DB_ENV_VARS: Sequence[str] = (
    "DATABASE_URL",
    # a small fallback alias
    "DB_URL",
)


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

_ASYNC_DRIVER_HINT = re.compile(r"\+(?:async|asyncpg|aiosqlite|aiomysql|asyncmy|aio\w+)")


def is_async_url(url: URL | str) -> bool:
    u = make_url(url) if isinstance(url, str) else url
    dn = u.drivername or ""
    return bool(_ASYNC_DRIVER_HINT.search(dn))


def with_database(url: URL, database: Optional[str]) -> URL:
    """Return a copy of URL with the database name replaced.

    Works for most dialects. For SQLite file URLs, `database` is the file path.
    """
    return url.set(database=database)


# ---------- Engine creation ----------

@dataclass(frozen=True)
class EngineSpec:
    url: URL
    is_async: bool


def build_engine(url: URL | str, echo: bool = False) -> Union[SyncEngine, AsyncEngineType]:
    u = make_url(url) if isinstance(url, str) else url
    if is_async_url(u):
        if _create_async_engine is None:
            raise RuntimeError("Async driver URL provided but SQLAlchemy async extras are not available.")
        return _create_async_engine(u, echo=echo, pool_pre_ping=True)
    if _create_engine is None:
        raise RuntimeError("SQLAlchemy create_engine is not available in this environment.")
    return _create_engine(u, echo=echo, pool_pre_ping=True)


# ---------- Database bootstrap ----------

async def _pg_create_database_async(url: URL) -> None:
    assert is_async_url(url)
    target_db = url.database
    if not target_db:
        return

    maintenance_url = with_database(url, "postgres")
    engine: AsyncEngineType = build_engine(maintenance_url)  # type: ignore[assignment]
    async with engine.begin() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": target_db},
        )
        if not exists:
            quoted = _pg_quote_ident(target_db)
            await conn.execution_options(isolation_level="AUTOCOMMIT").execute(
                text(f'CREATE DATABASE "{quoted}"')
            )
    await engine.dispose()

def _pg_create_database_sync(url: URL) -> None:
    if _create_engine is None:
        raise RuntimeError("SQLAlchemy create_engine is not available.")
    target_db = url.database
    if not target_db:
        return
    maintenance_url = with_database(make_url(url), "postgres")
    engine = _create_engine(maintenance_url, pool_pre_ping=True)
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
    if _create_engine is None:
        raise RuntimeError("SQLAlchemy create_engine is not available.")
    target_db = url.database
    if not target_db:
        return
    base_url = with_database(url, None)
    engine = _create_engine(base_url, pool_pre_ping=True)
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
    if _create_engine is None:
        raise RuntimeError("SQLAlchemy create_engine is not available.")
    target_db = url.database
    if not target_db:
        return
    base_url = with_database(url, None)
    eng = _create_engine(base_url, pool_pre_ping=True)
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
    if _create_engine is None:
        raise RuntimeError("SQLAlchemy create_engine is not available.")
    target_db = url.database
    if not target_db:
        return
    master_url = with_database(url, "master")
    eng = _create_engine(master_url, pool_pre_ping=True)
    try:
        with eng.begin() as conn:
            exists = conn.scalar(text("SELECT 1 FROM sys.databases WHERE name = :name"), {"name": target_db})
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
            exists = await conn.scalar(text("SELECT 1 FROM sys.databases WHERE name = :name"), {"name": target_db})
            if not exists:
                await conn.execute(text(f"CREATE DATABASE [{target_db}]"))
    finally:
        await engine.dispose()


def _snowflake_create_database_sync(url: URL) -> None:
    if _create_engine is None:
        raise RuntimeError("SQLAlchemy create_engine is not available.")
    target_db = url.database
    if not target_db:
        return
    base_url = with_database(url, None)
    eng = _create_engine(base_url, pool_pre_ping=True)
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
    if _create_engine is None:
        raise RuntimeError("SQLAlchemy create_engine is not available.")
    target_db = url.database
    if not target_db:
        return
    base_url = with_database(url, None)
    try:
        eng = _create_engine(base_url, pool_pre_ping=True)
    except Exception:
        eng = _create_engine(with_database(url, "dev"), pool_pre_ping=True)
    try:
        with eng.begin() as conn:
            exists = conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
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
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": target_db},
            )
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{target_db}"'))
    finally:
        await engine.dispose()


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
    except OperationalError as exc:
        raise RuntimeError(f"Failed to connect to database: {exc}") from exc


# ---------- Alembic config and scaffolding ----------

ALEMBIC_INI_TEMPLATE = """# Alembic configuration file, generated by svc-infra
[alembic]
script_location = {script_location}

# Used only for offline mode; env.py will use DATABASE_URL if set
sqlalchemy.url = {sqlalchemy_url}

dialect_name = {dialect_name}

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
"""


def _render_env_py(packages: Sequence[str]) -> str:
    packages_list = ", ".join(repr(p) for p in packages)
    return f"""# Alembic env.py generated by svc-infra
from __future__ import annotations
import os
import logging
from importlib import import_module
from typing import Iterable, List

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection

# Load logging configuration from alembic.ini
config = context.config
if config.config_file_name is not None:
    import logging.config
    logging.config.fileConfig(config.config_file_name)
logger = logging.getLogger(__name__)

# Discover metadata from packages
DISCOVER_PACKAGES: List[str] = [{packages_list}]
ENV_DISCOVER = os.getenv("ALEMBIC_DISCOVER_PACKAGES")
if ENV_DISCOVER:
    DISCOVER_PACKAGES = [s.strip() for s in ENV_DISCOVER.split(',') if s.strip()]

def _collect_metadata() -> List[object]:
    metadata = []
    for pkg in DISCOVER_PACKAGES:
        try:
            mod = import_module(pkg)
        except Exception as e:  # pragma: no cover
            logger.debug("Failed to import %s: %s", pkg, e)
            continue
        # Common conventions
        for attr in ("metadata", "MetaData", "Base", "base"):
            obj = getattr(mod, attr, None)
            if obj is None:
                # try nested models submodule
                try:
                    sub = import_module(f"{pkg}.models")
                    obj = getattr(sub, attr, None)
                except Exception:
                    obj = None
            if obj is None:
                continue
            md = getattr(obj, "metadata", None) or obj
            # If it's a declarative Base, extract .metadata
            if hasattr(md, "tables") and hasattr(md, "schema"):  # rough check for MetaData
                metadata.append(md)
    return metadata

target_metadata = _collect_metadata()

# Determine URL: prefer env var DATABASE_URL else alembic.ini sqlalchemy.url
env_db_url = os.getenv("DATABASE_URL")
if env_db_url:
    config.set_main_option("sqlalchemy.url", env_db_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={{"paramstyle": "named"}},
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {{}}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            include_schemas=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
"""


def _render_env_py_async(packages: Sequence[str]) -> str:
    packages_list = ", ".join(repr(p) for p in packages)
    return f"""# Alembic async env.py generated by svc-infra
from __future__ import annotations
import os
import logging
from importlib import import_module
from typing import List

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

config = context.config
if config.config_file_name is not None:
    import logging.config
    logging.config.fileConfig(config.config_file_name)
logger = logging.getLogger(__name__)

DISCOVER_PACKAGES: List[str] = [{packages_list}]
ENV_DISCOVER = os.getenv("ALEMBIC_DISCOVER_PACKAGES")
if ENV_DISCOVER:
    DISCOVER_PACKAGES = [s.strip() for s in ENV_DISCOVER.split(',') if s.strip()]

def _collect_metadata() -> List[object]:
    from importlib import import_module
    metadata = []
    for pkg in DISCOVER_PACKAGES:
        try:
            mod = import_module(pkg)
        except Exception as e:
            logger.debug("Failed to import %s: %s", pkg, e)
            continue
        for attr in ("metadata", "MetaData", "Base", "base"):
            obj = getattr(mod, attr, None)
            if obj is None:
                try:
                    sub = import_module(f"{pkg}.models")
                    obj = getattr(sub, attr, None)
                except Exception:
                    obj = None
            if obj is None:
                continue
            md = getattr(obj, "metadata", None) or obj
            if hasattr(md, "tables") and hasattr(md, "schema"):
                metadata.append(md)
    return metadata

target_metadata = _collect_metadata()

env_db_url = os.getenv("DATABASE_URL")
if env_db_url:
    config.set_main_option("sqlalchemy.url", env_db_url)

def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    connectable = create_async_engine(config.get_main_option("sqlalchemy.url"))
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

if context.is_offline_mode():
    raise SystemExit("Run offline migrations with a sync env.py or set offline to False.")
else:
    import asyncio as _asyncio
    _asyncio.run(run_migrations_online())
"""


def init_alembic(
    project_root: Path | str,
    *,
    script_location: str = "migrations",
    async_db: bool = False,
    discover_packages: Optional[Sequence[str]] = None,
    overwrite: bool = False,
) -> Path:
    """Initialize Alembic in the target project directory.

    - Creates alembic.ini (or overwrites if requested).
    - Creates migrations/ with env.py and versions/.
    - env.py will read DATABASE_URL from environment at runtime, and
      discover model metadata from the provided packages or ALEMBIC_DISCOVER_PACKAGES.

    Returns the Path to the created migrations directory.
    """
    root = Path(project_root).resolve()
    root.mkdir(parents=True, exist_ok=True)

    migrations_dir = root / script_location
    versions_dir = migrations_dir / "versions"

    # Create alembic.ini
    alembic_ini = root / "alembic.ini"
    sqlalchemy_url = os.getenv("DATABASE_URL", "")
    dialect_name = (make_url(sqlalchemy_url).get_backend_name() if sqlalchemy_url else "")
    ini_contents = ALEMBIC_INI_TEMPLATE.format(
        script_location=script_location,
        sqlalchemy_url=sqlalchemy_url,
        dialect_name=dialect_name,
    )
    if alembic_ini.exists() and not overwrite:
        pass
    else:
        alembic_ini.write_text(ini_contents, encoding="utf-8")

    # Create migrations structure
    migrations_dir.mkdir(parents=True, exist_ok=True)
    versions_dir.mkdir(parents=True, exist_ok=True)

    # Render env.py
    pkgs = list(discover_packages or [])
    if not pkgs:
        # Common default; user can override via ALEMBIC_DISCOVER_PACKAGES
        # Keep empty to avoid import errors by default
        pkgs = []

    env_py = _render_env_py_async(pkgs) if async_db else _render_env_py(pkgs)
    env_path = migrations_dir / "env.py"
    if env_path.exists() and not overwrite:
        pass
    else:
        env_path.write_text(env_py, encoding="utf-8")

    return migrations_dir


# ---------- Alembic command helpers ----------

def _build_alembic_config(project_root: Path | str, script_location: str = "migrations", database_url: Optional[str] = None) -> Config:
    root = Path(project_root).resolve()
    cfg_path = root / "alembic.ini"
    cfg = Config(str(cfg_path)) if cfg_path.exists() else Config()
    # ensure absolute
    cfg.set_main_option("script_location", str((root / script_location).resolve()))
    db_url = database_url or get_database_url_from_env(required=False) or cfg.get_main_option("sqlalchemy.url")
    if db_url:
        cfg.set_main_option("sqlalchemy.url", db_url)
    # harmless custom option; can remove if you prefer
    cfg.set_main_option("prepend_sys_path", str(root))
    return cfg


def revision(
    project_root: Path | str,
    message: str,
    *,
    autogenerate: bool = False,
    head: str | None = "head",
    branch_label: str | None = None,
    version_path: str | None = None,
    sql: bool = False,
) -> None:
    cfg = _build_alembic_config(project_root)
    command.revision(
        cfg,
        message=message,
        autogenerate=autogenerate,
        head=head,
        branch_label=branch_label,
        version_path=version_path,
        sql=sql,
    )


def upgrade(project_root: Path | str, revision_target: str = "head") -> None:
    cfg = _build_alembic_config(project_root)
    command.upgrade(cfg, revision_target)


def downgrade(project_root: Path | str, revision_target: str = "-1") -> None:
    cfg = _build_alembic_config(project_root)
    command.downgrade(cfg, revision_target)


def current(project_root: Path | str, verbose: bool = False) -> None:
    cfg = _build_alembic_config(project_root)
    command.current(cfg, verbose=verbose)


def history(project_root: Path | str, verbose: bool = False) -> None:
    cfg = _build_alembic_config(project_root)
    command.history(cfg, verbose=verbose)


def stamp(project_root: Path | str, revision_target: str = "head") -> None:
    cfg = _build_alembic_config(project_root)
    command.stamp(cfg, revision_target)


def merge_heads(project_root: Path | str, message: Optional[str] = None) -> None:
    cfg = _build_alembic_config(project_root)
    command.merge(cfg, "heads", message=message)


# ---------- High-level convenience API ----------

@dataclass(frozen=True)
class DBSetupResult:
    project_root: Path
    migrations_dir: Path
    alembic_ini: Path


def init_database_structure(
    *,
    project_root: Path | str,
    discover_packages: Optional[Sequence[str]] = None,
    async_db: bool = False,
    overwrite: bool = False,
    create_db_if_missing: bool = True,
) -> DBSetupResult:
    """High-level one-shot setup.

    - Ensures database exists (best-effort by dialect) using DATABASE_URL.
    - Initializes Alembic scaffolding (alembic.ini and migrations/ env.py).
    """
    db_url = get_database_url_from_env(required=True)
    if create_db_if_missing:
        ensure_database_exists(db_url)
    mig_dir = init_alembic(
        project_root,
        async_db=async_db or (db_url and is_async_url(db_url)),
        discover_packages=discover_packages,
        overwrite=overwrite,
    )
    return DBSetupResult(
        project_root=Path(project_root).resolve(),
        migrations_dir=mig_dir,
        alembic_ini=Path(project_root).resolve() / "alembic.ini",
    )


__all__ = [
    # env helpers
    "get_database_url_from_env",
    "is_async_url",
    # engines and db bootstrap
    "build_engine",
    "ensure_database_exists",
    # alembic init and commands
    "init_alembic",
    "revision",
    "upgrade",
    "downgrade",
    "current",
    "history",
    "stamp",
    "merge_heads",
    # high-level
    "init_database_structure",
    "DBSetupResult",
]

