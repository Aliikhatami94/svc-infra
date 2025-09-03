from __future__ import annotations

import os, re
from pathlib import Path
from textwrap import dedent
from typing import Optional, Dict, Any

from alembic.script import ScriptDirectory
from sqlalchemy.engine.url import make_url
from sqlalchemy import create_engine
from contextlib import closing
from sqlalchemy import text

import typer
from alembic import command
from alembic.config import Config

from .constants import ALEMBIC_INI, AL_EMBIC_DIR
from .utils import (
    _resolve_ini_url_value,
    _normalize_discover_arg,
    _load_dotenv_if_present,
    _get_env_value_from_name,
    _normalize_db_url_for_alembic,
    _ensure_alembic_bootstrap,
    _effective_migration_url,
    _quote_ident,
    _parse_table_identifier,
    _table_exists,
    _connect_engine,
    _get_heads,
    _repair_self_loop_if_present,
    _resolve_down_revision,
)

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False
)


def _load_config(project_root: Path, database_url: Optional[str]) -> Config:
    _load_dotenv_if_present(project_root)  # ensure .env is loaded

    cfg = Config(str(project_root / ALEMBIC_INI))

    # Accept placeholders like "${database_url}" and fall back to env
    effective = _get_env_value_from_name(database_url)
    if not effective:
        effective = os.getenv("DATABASE_URL")

    effective = _normalize_db_url_for_alembic(effective) if effective else effective
    if effective:
        cfg.set_main_option("sqlalchemy.url", effective)

    cfg.set_main_option("script_location", str(project_root / AL_EMBIC_DIR))
    cfg.attributes["configure_logger"] = False
    return cfg

def _infer_default_roots(project_root: Path) -> list[str]:
    roots: list[str] = []
    for base in (project_root, project_root / "src"):
        if not base.exists():
            continue
        for d in base.iterdir():
            if d.is_dir() and (d / "__init__.py").exists():
                roots.append(d.name)
    seen, out = set(), []
    for r in roots:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out

def _versions_dir(project_root: Path) -> Path:
    return project_root / AL_EMBIC_DIR / "versions"

def _latest_version_file(versions_dir: Path) -> Path | None:
    if not versions_dir.exists():
        return None
    candidates = [p for p in versions_dir.iterdir() if p.is_file() and p.suffix == ".py"]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)

def _script_dir(cfg: Config) -> ScriptDirectory:
    return ScriptDirectory.from_config(cfg)

def _single_head_or_none(script: ScriptDirectory) -> str | None:
    heads = script.get_heads()
    if len(heads) == 0:
        return None
    if len(heads) == 1:
        return heads[0]
    raise RuntimeError(f"Multiple heads present: {', '.join(heads)}")

# ---------------- Core (tool-callable) APIs ---------------- #

def db_ping_core(*, project_root: Path, database_url: Optional[str] = None) -> Dict[str, Any]:
    project_root = project_root.resolve()
    _load_dotenv_if_present(project_root)

    eff = _get_env_value_from_name(database_url)
    if not eff:
        eff = os.getenv("DATABASE_URL")
    eff = _normalize_db_url_for_alembic(eff) if eff else eff

    if not eff:
        return {"status": "error", "message": "DATABASE_URL is empty or not set."}

    def _redact(u: str) -> str:
        try:
            m = make_url(u)
            if m.password:
                m = m.set(password="***")
            return str(m)
        except Exception:
            return "<unparseable>"

    redacted = _redact(eff)
    try:
        engine = create_engine(eff, future=True)
        with closing(engine.connect()) as conn:
            conn.exec_driver_sql("SELECT 1")
        engine.dispose()
        return {"status": "ok", "url": redacted}
    except Exception as e:
        return {"status": "error", "url": redacted, "error": str(e)}

def db_init_core(
        *,
        project_root: Path,
        database_url: Optional[str] = None,
        discover_packages: Optional[str | bool | list[str]],
) -> Dict[str, Any]:
    """
    Initialize Alembic environment in the given project root.
    Generates sync-only env.py; env.py maps async drivers to sync for migrations.
    """
    project_root = project_root.resolve()
    _load_dotenv_if_present(project_root)  # make DATABASE_URL visible to ini/env generation

    (project_root / AL_EMBIC_DIR).mkdir(parents=True, exist_ok=True)

    ini_path = project_root / ALEMBIC_INI
    created = {"alembic_ini": False, "env_py": False, "script_tpl": False, "versions_dir": False}
    notes: list[str] = []

    # --- Normalize inputs ---
    normalized_discover = _normalize_discover_arg(discover_packages)
    if normalized_discover is None:
        discover_root_csv = ",".join(_infer_default_roots(project_root))
    else:
        discover_root_csv = normalized_discover

    ini_url_value = _resolve_ini_url_value(database_url)

    # 1) alembic.ini
    if not ini_path.exists():
        ini_text = f"""\
[alembic]
script_location = {AL_EMBIC_DIR}
sqlalchemy.url = {ini_url_value}

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers = console
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
"""
        ini_path.write_text(ini_text, encoding="utf-8")
        created["alembic_ini"] = True
        notes.append(f"Wrote {ini_path}")

    # 2) env.py — sync only, async→sync mapping is handled at runtime
    env_py = project_root / AL_EMBIC_DIR / "env.py"
    if not env_py.exists():
        env_template = dedent("""
        from __future__ import annotations
        import os
        import sys
        import logging
        import pkgutil
        import importlib
        import fnmatch
        from pathlib import Path
        from logging.config import fileConfig
        from typing import Iterable, List
        
        from alembic import context
        from sqlalchemy import pool, create_engine
        from sqlalchemy.engine.url import make_url, URL
        from sqlalchemy.orm import DeclarativeBase
        
        # --- Ensure project root and src/ on sys.path ---
        ROOT = Path(__file__).resolve().parents[1]
        for p in (ROOT, ROOT / "src"):
            s = str(p)
            if p.exists() and s not in sys.path:
                sys.path.insert(0, s)
        
        # --- Alembic config & logging ---
        config = context.config
        USE_APP_LOGGING = os.getenv("ALEMBIC_USE_APP_LOGGING", "1") == "1"
        if USE_APP_LOGGING:
            try:
                from svc_infra.app.logging import setup_logging
                setup_logging(level=os.getenv("LOG_LEVEL"), fmt=os.getenv("LOG_FORMAT"))
                logging.getLogger(__name__).debug("Alembic using app logging setup.")
            except Exception as e:
                USE_APP_LOGGING = False
                print(f"[alembic] App logging import failed: {e}. Falling back to fileConfig.")
        
        if not USE_APP_LOGGING and config.config_file_name is not None:
            fileConfig(config.config_file_name)
            logging.getLogger(__name__).debug("Alembic using fileConfig logging.")
        
        # --- Database URL override via env (if ini is blank) ---
        env_url = os.getenv("DATABASE_URL")
        if env_url:
            config.set_main_option("sqlalchemy.url", env_url)
        
        # --- Auto-discover model modules (SAFE) and collect all metadatas ---
        # Inputs:
        #   ALEMBIC_DISCOVER_PACKAGES: CSV of top-level packages to scan
        #   ALEMBIC_IMPORT_ALLOW: CSV of glob patterns to import
        #   ALEMBIC_IMPORT_DENY:  CSV of glob patterns to exclude
        DISCOVER_PKGS = os.getenv("ALEMBIC_DISCOVER_PACKAGES", "__DISCOVER__")
        ALLOW_PATTERNS = [p.strip() for p in (os.getenv("ALEMBIC_IMPORT_ALLOW", "*.models,*.db,*.db.models") or "").split(",") if p.strip()]
        DENY_PATTERNS  = [p.strip() for p in (os.getenv("ALEMBIC_IMPORT_DENY",  "*.api.*,*.routers.*,*.server.*,*.cli.*") or "").split(",") if p.strip()]
        
        def _should_import(mod_name: str) -> bool:
            for pat in DENY_PATTERNS:
                if fnmatch.fnmatch(mod_name, pat):
                    return False
            for pat in ALLOW_PATTERNS:
                if fnmatch.fnmatch(mod_name, pat):
                    return True
            return False
        
        def _iter_pkg_modules(top_pkg_name: str) -> Iterable[str]:
            try:
                top_pkg = importlib.import_module(top_pkg_name)
            except Exception:
                return []
            if not hasattr(top_pkg, "__path__"):
                return [top_pkg_name] if _should_import(top_pkg_name) else []
            names = []
            for m in pkgutil.walk_packages(top_pkg.__path__, prefix=top_pkg.__name__ + "."):
                if _should_import(m.name):
                    names.append(m.name)
            return names
        
        def import_model_modules(packages: Iterable[str]) -> None:
            for pkg_name in packages:
                pkg_name = (pkg_name or "").strip()
                if not pkg_name:
                    continue
                for mod_name in _iter_pkg_modules(pkg_name):
                    try:
                        importlib.import_module(mod_name)
                    except Exception as e:
                        logging.getLogger(__name__).debug(f"[alembic] Skipped import {mod_name}: {e}")
        
        def collect_all_metadatas() -> List:
            metas: set = set()
            try:
                for cls in DeclarativeBase.__subclasses__():
                    md = getattr(cls, "metadata", None)
                    if md is not None:
                        metas.add(md)
            except Exception:
                pass
            return list(metas)
        
        pkgs = [p.strip() for p in (DISCOVER_PKGS or "").split(",") if p.strip()]
        import_model_modules(pkgs)
        target_metadata = collect_all_metadatas()  # may be empty (autogen no-op)
        
        # --- URL normalization: map async drivers to sync + ensure sslmode=require for pg ---
        def _sync_url_for_migrations(url_str: str) -> str:
            if not url_str:
                return url_str
            try:
                u: URL = make_url(url_str)
            except Exception:
                return url_str
        
            drv = (u.drivername or "")
            if drv.endswith("+asyncpg"):
                u = u.set(drivername="postgresql+psycopg2")
            elif drv.endswith("+aiosqlite"):
                u = u.set(drivername="sqlite")
            elif drv.endswith("+asyncmy"):
                u = u.set(drivername="mysql+pymysql")
        
            if u.drivername.startswith("postgresql"):
                q = dict(u.query)
                if "sslmode" not in q:
                    q["sslmode"] = "require"
                u = u.set(query=q)
        
            return str(u)
        
        def run_migrations_offline():
            url = _sync_url_for_migrations(config.get_main_option("sqlalchemy.url"))
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
        
        def run_migrations_online_sync():
            url = _sync_url_for_migrations(config.get_main_option("sqlalchemy.url"))
            engine = create_engine(url, poolclass=pool.NullPool, future=True)
            try:
                with engine.connect() as connection:
                    do_run_migrations(connection)
            finally:
                engine.dispose()
        
        if context.is_offline_mode():
            run_migrations_offline()
        else:
            run_migrations_online_sync()
        """).replace("__DISCOVER__", discover_root_csv)
        env_py.write_text(env_template, encoding="utf-8")
        created["env_py"] = True
        notes.append(f"Wrote {env_py}")
    script_path = project_root / AL_EMBIC_DIR / "script.py.mako"
    if not script_path.exists():
        script_tpl = dedent("""
        \"\"\"${message}
        
        Revision ID: ${up_revision}
        Revises: ${down_revision | comma,n}
        Create Date: ${create_date}
        
        \"\"\"
        from __future__ import annotations
        
        from alembic import op
        import sqlalchemy as sa
        import fastapi_users_db_sqlalchemy  # noqa: F401
        
        revision: str = ${repr(up_revision)}
        down_revision: str | None = ${repr(down_revision)}
        branch_labels: tuple[str, ...] | None = ${repr(branch_labels)}
        depends_on: tuple[str, ...] | None = ${repr(depends_on)}
        
        def upgrade() -> None:
            ${upgrades if upgrades else "pass"}
        
        def downgrade() -> None:
            ${downgrades if downgrades else "pass"}
        """)
        if not script_path.exists():
            script_path.write_text(script_tpl, encoding="utf-8")
            created["script_tpl"] = True
            notes.append(f"Wrote {script_path}")

    versions = _versions_dir(project_root)
    versions.mkdir(exist_ok=True)
    created["versions_dir"] = True
    notes.append(f"Ensured {versions}")

    return {
        "status": "ok",
        "created": created,
        "paths": {
            "project_root": str(project_root),
            "alembic_ini": str(ini_path),
            "env_py": str(env_py),
            "script_tpl": str(script_path),
            "versions_dir": str(versions),
        },
        "notes": notes,
    }

def db_revision_core(
        *,
        message: str,
        autogenerate: bool,
        project_root: Path,
        database_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new Alembic revision."""
    project_root = project_root.resolve()
    _load_dotenv_if_present(project_root)
    cfg = _load_config(project_root, database_url)
    command.revision(cfg, message=message, autogenerate=autogenerate)
    return {"status": "ok", "message": message, "autogenerate": autogenerate}

def db_upgrade_core(
        *,
        revision: str,
        project_root: Path,
        database_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Upgrade to a later Alembic revision."""
    project_root = project_root.resolve()
    _load_dotenv_if_present(project_root)
    cfg = _load_config(project_root, database_url)
    command.upgrade(cfg, revision)
    return {"status": "ok", "to": revision}

def db_downgrade_core(
        *,
        revision: str,
        project_root: Path,
        database_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Downgrade to an earlier Alembic revision."""
    project_root = project_root.resolve()
    _load_dotenv_if_present(project_root)
    cfg = _load_config(project_root, database_url)
    command.downgrade(cfg, revision)
    return {"status": "ok", "to": revision}

def db_current_core(
        *,
        verbose: bool,
        project_root: Path,
        database_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Show the current Alembic revision."""
    project_root = project_root.resolve()
    _load_dotenv_if_present(project_root)
    cfg = _load_config(project_root, database_url)
    command.current(cfg, verbose=verbose)
    return {"status": "ok", "verbose": verbose}

def db_history_core(*, verbose: bool, project_root: Path, database_url: Optional[str] = None) -> Dict[str, Any]:
    """Show the full Alembic revision history."""
    project_root = project_root.resolve()
    _load_dotenv_if_present(project_root)
    _repair_self_loop_if_present(project_root)  # <— add
    cfg = _load_config(project_root, database_url)
    command.history(cfg, verbose=verbose)
    return {"status": "ok", "verbose": verbose}

def db_stamp_core(
        *,
        revision: str,
        project_root: Path,
        database_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Stamp the database with a given Alembic revision without running migrations."""
    project_root = project_root.resolve()
    _load_dotenv_if_present(project_root)
    cfg = _load_config(project_root, database_url)
    command.stamp(cfg, revision)
    return {"status": "ok", "revision": revision}

def db_drop_table_core(
        *,
        table: str,
        cascade: bool,
        if_exists: bool,
        message: Optional[str],
        base: Optional[str],
        apply: bool,
        project_root: Path,
        database_url: Optional[str],
) -> Dict[str, Any]:
    """
    Create and optionally apply a migration that drops a specified table.
    Safe against Alembic self-loops; supports base=None/"head"/<rev_id>.
    """
    project_root = project_root.resolve()

    # 0) Ensure Alembic is bootstrapped (idempotent)
    _ensure_alembic_bootstrap(project_root=project_root, database_url=database_url)

    # 1) Effective DB url & ping
    eff_url = _effective_migration_url(project_root, database_url)
    engine = _connect_engine(eff_url)
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")  # SQLA 2.0-safe ping
    except Exception as e:
        engine.dispose()
        raise RuntimeError(f"DB ping failed: {e}") from e

    # Determine schema/table existence BEFORE
    schema, tbl = _parse_table_identifier(table)
    existed_before = _table_exists(engine, schema, tbl)

    # 2) Prepare Alembic config & resolve down_revision *BEFORE* creating the new revision
    cfg = _load_config(project_root, database_url)
    script = _script_dir(cfg)

    try:
        down_rev = _resolve_down_revision(script, base)
    except RuntimeError as e:
        engine.dispose()
        # Preserve the helpful message about multiple heads
        raise

    # 3) Create an empty revision file (autogenerate=False)
    msg = message or f"drop table {table}"
    command.revision(cfg, message=msg, autogenerate=False)

    # 4) Open the newest file and write our content with the resolved down_revision
    versions_dir = project_root / AL_EMBIC_DIR / "versions"
    rev_file = _latest_version_file(versions_dir)
    if rev_file is None:
        engine.dispose()
        raise RuntimeError("Could not locate newly created revision file.")

    rev_id = rev_file.stem.split("_", 1)[0]

    # Build safe SQL
    qschema = (_quote_ident(schema) + ".") if schema else ""
    qtable = _quote_ident(tbl)
    sql = f'DROP TABLE {"IF EXISTS " if if_exists else ""}{qschema}{qtable}{" CASCADE" if cascade else ""};'

    if down_rev == rev_id:
        # This should never happen now; bail loudly if it does.
        raise RuntimeError(
            f"Refusing to write self-referencing revision: down_revision == revision ({rev_id})."
        )

    content = (
        f'''""" {msg} """\n\n'''
        f'''from __future__ import annotations\n\n'''
        f'''from alembic import op\nimport sqlalchemy as sa\n\n'''
        f'''revision = "{rev_id}"\n'''
        f'''down_revision = {repr(down_rev) if down_rev else "None"}\n'''
        f'''branch_labels = None\n'''
        f'''depends_on = None\n\n'''
        f'''def upgrade() -> None:\n'''
        f'''    op.execute({sql!r})\n\n'''
        f'''def downgrade() -> None:\n'''
        f'''    # Irreversible without full table definition\n'''
        f'''    pass\n'''
    )
    rev_file.write_text(content, encoding="utf-8")

    # 5) Apply if requested
    applied = False
    if apply:
        try:
            command.upgrade(cfg, "head")
            applied = True
        except Exception:
            engine.dispose()
            raise

    # 6) Verify AFTER
    exists_after = _table_exists(engine, schema, tbl)
    engine.dispose()

    return {
        "status": "ok",
        "wrote": str(rev_file),
        "applied": bool(applied),
        "table": {"raw": table, "schema": schema, "name": tbl},
        "cascade": cascade,
        "if_exists": if_exists,
        "existed_before": bool(existed_before),
        "exists_after": bool(exists_after),
        "note": "If exists_after is True, your DB user may lack privileges or the table is in a different schema.",
    }

def db_merge_heads_core(*, message: str, project_root: Path, database_url: Optional[str] = None) -> Dict[str, Any]:
    """Merge all current heads into one new head."""
    project_root = project_root.resolve()
    _load_dotenv_if_present(project_root)
    _repair_self_loop_if_present(project_root)  # <— add
    cfg = _load_config(project_root, database_url)
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    if len(heads) <= 1:
        return {"status": "noop", "heads": heads}
    command.merge(cfg, revisions=heads, message=message)
    return {"status": "ok", "merged": heads, "message": message}