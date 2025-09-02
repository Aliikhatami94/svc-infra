from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent
from typing import Optional, Dict, Any

from alembic.script import ScriptDirectory

import typer
from alembic import command
from alembic.config import Config

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False
)

AL_EMBIC_DIR = "migrations"
ALEMBIC_INI = "alembic.ini"


def _load_config(project_root: Path, database_url: Optional[str]) -> Config:
    cfg = Config(str(project_root / ALEMBIC_INI))
    db_url = database_url or os.getenv("DATABASE_URL")
    if db_url:
        cfg.set_main_option("sqlalchemy.url", db_url)
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
    seen = set()
    out = []
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

def db_init_core(
        *,
        project_root: Path,
        database_url: Optional[str],
        async_db: bool,
        discover_packages: Optional[str],
) -> Dict[str, Any]:
    """Initialize Alembic environment in the given project root."""
    project_root = project_root.resolve()
    (project_root / AL_EMBIC_DIR).mkdir(parents=True, exist_ok=True)

    ini_path = project_root / ALEMBIC_INI
    created = {"alembic_ini": False, "env_py": False, "script_tpl": False, "versions_dir": False}
    notes: list[str] = []

    if not ini_path.exists():
        ini_path.write_text(
            f"""\
[alembic]
script_location = {AL_EMBIC_DIR}
sqlalchemy.url = {database_url or os.getenv('DATABASE_URL', '')}

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
""",
            encoding="utf-8",
        )
        created["alembic_ini"] = True
        notes.append(f"Wrote {ini_path}")

    discover_root_csv = (
        ",".join([p.strip() for p in discover_packages.split(",") if p.strip()])
        if discover_packages
        else ",".join(_infer_default_roots(project_root))
    )

    env_py = project_root / AL_EMBIC_DIR / "env.py"
    if not env_py.exists():
        run_cmd = "asyncio.run(run_migrations_online_async())" if async_db else "run_migrations_online_sync()"
        content = dedent(
            f"""\
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

            ROOT = Path(__file__).resolve().parents[1]
            for p in (ROOT, ROOT / "src"):
                s = str(p)
                if p.exists() and s not in sys.path:
                    sys.path.insert(0, s)

            USE_APP_LOGGING = os.getenv("ALEMBIC_USE_APP_LOGGING", "1") == "1"
            if USE_APP_LOGGING:
                try:
                    from svc_infra.app.logging import setup_logging
                    setup_logging(level=os.getenv("LOG_LEVEL"), fmt=os.getenv("LOG_FORMAT"))
                    logging.getLogger(__name__).debug("Alembic using app logging setup.")
                except Exception as e:
                    USE_APP_LOGGING = False
                    print(f"[alembic] App logging import failed: {{e}}. Falling back to fileConfig.")

            config = context.config
            if not USE_APP_LOGGING and config.config_file_name is not None:
                fileConfig(config.config_file_name)
                logging.getLogger(__name__).debug("Alembic using fileConfig logging.")

            database_url = os.getenv("DATABASE_URL")
            if database_url:
                config.set_main_option("sqlalchemy.url", database_url)

            DISCOVER_PKGS = os.getenv("ALEMBIC_DISCOVER_PACKAGES", "{discover_root_csv}")

            def _iter_pkg_modules(top_pkg_name: str):
                try:
                    top_pkg = importlib.import_module(top_pkg_name)
                except Exception:
                    return []
                if not hasattr(top_pkg, "__path__"):
                    return [top_pkg_name]
                names = []
                for m in pkgutil.walk_packages(top_pkg.__path__, prefix=top_pkg.__name__ + "."):
                    names.append(m.name)
                return names

            def import_all_under_packages(packages):
                for pkg_name in packages:
                    if not pkg_name:
                        continue
                    for mod_name in _iter_pkg_modules(pkg_name):
                        try:
                            importlib.import_module(mod_name)
                        except Exception as e:
                            logging.getLogger(__name__).debug(f"[alembic] Skipped import {{mod_name}}: {{e}}")

            def collect_all_metadatas():
                metas = set()
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
            target_metadata = metadatas

            url_str = config.get_main_option("sqlalchemy.url") or ""
            driver = ""
            try:
                driver = make_url(url_str).get_dialect().driver
            except Exception:
                pass
            is_async = driver in {{"asyncpg", "aiosqlite"}}

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
                {run_cmd}
            """
        )
        env_py.write_text(content, encoding="utf-8")
        created["env_py"] = True
        notes.append(f"Wrote {env_py}")

    script_tpl = dedent(
        """\
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
        """
    )
    script_path = project_root / AL_EMBIC_DIR / "script.py.mako"
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
        database_url: Optional[str],
) -> Dict[str, Any]:
    """Create a new Alembic revision."""
    cfg = _load_config(project_root.resolve(), database_url)
    command.revision(cfg, message=message, autogenerate=autogenerate)
    return {"status": "ok", "message": message, "autogenerate": autogenerate}

def db_upgrade_core(
        *,
        revision: str,
        project_root: Path,
        database_url: Optional[str],
) -> Dict[str, Any]:
    """Upgrade to a later Alembic revision."""
    cfg = _load_config(project_root.resolve(), database_url)
    command.upgrade(cfg, revision)
    return {"status": "ok", "to": revision}

def db_downgrade_core(
        *,
        revision: str,
        project_root: Path,
        database_url: Optional[str],
) -> Dict[str, Any]:
    """Downgrade to an earlier Alembic revision."""
    cfg = _load_config(project_root.resolve(), database_url)
    command.downgrade(cfg, revision)
    return {"status": "ok", "to": revision}

def db_current_core(
        *,
        verbose: bool,
        project_root: Path,
        database_url: Optional[str],
) -> Dict[str, Any]:
    """Show the current Alembic revision."""
    cfg = _load_config(project_root.resolve(), database_url)
    # Alembic prints to stdout; for tools we return a marker
    command.current(cfg, verbose=verbose)
    return {"status": "ok", "verbose": verbose}

def db_history_core(
        *,
        verbose: bool,
        project_root: Path,
        database_url: Optional[str],
) -> Dict[str, Any]:
    """Show the history of Alembic revisions."""
    cfg = _load_config(project_root.resolve(), database_url)
    command.history(cfg, verbose=verbose)
    return {"status": "ok", "verbose": verbose}

def db_stamp_core(
        *,
        revision: str,
        project_root: Path,
        database_url: Optional[str],
) -> Dict[str, Any]:
    """Stamp the database with a given Alembic revision without running migrations."""
    cfg = _load_config(project_root.resolve(), database_url)
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
    """Create and optionally apply a migration that drops a specified table."""
    cfg = _load_config(project_root.resolve(), database_url)
    script = _script_dir(cfg)

    msg = message or f"drop table {table}"
    command.revision(cfg, message=msg, autogenerate=False)

    versions_dir = project_root.resolve() / AL_EMBIC_DIR / "versions"
    rev_file = _latest_version_file(versions_dir)
    if rev_file is None:
        raise RuntimeError("Could not locate newly created revision file.")

    try:
        down_rev = base or _single_head_or_none(script)
    except RuntimeError as e:
        raise RuntimeError(str(e) + " Tip: re-run with base=<rev> or merge heads first.") from e

    fq_table = table.strip()
    sql = f'DROP TABLE {"IF EXISTS " if if_exists else ""}{fq_table}{" CASCADE" if cascade else ""};'
    rev_id = rev_file.stem.split("_", 1)[0]

    content = f'''""" {msg} """\n\nfrom __future__ import annotations\n\nfrom alembic import op\nimport sqlalchemy as sa\n\nrevision = "{rev_id}"\ndown_revision = {repr(down_rev) if down_rev else "None"}\nbranch_labels = None\ndepends_on = None\n\n\ndef upgrade() -> None:\n    op.execute({sql!r})\n\n\ndef downgrade() -> None:\n    # Irreversible without full table definition\n    pass\n'''
    rev_file.write_text(content, encoding="utf-8")

    if apply:
        command.upgrade(cfg, "head")

    return {
        "status": "ok",
        "wrote": str(rev_file),
        "applied": bool(apply),
        "table": table,
        "cascade": cascade,
        "if_exists": if_exists,
    }

def db_merge_heads_core(
        *,
        message: str,
        project_root: Path,
        database_url: Optional[str],
) -> Dict[str, Any]:
    """Merge multiple Alembic heads into a single revision."""
    cfg = _load_config(project_root.resolve(), database_url)
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    if len(heads) <= 1:
        return {"status": "noop", "heads": heads}
    command.merge(cfg, revisions=heads, message=message)
    return {"status": "ok", "merged": heads, "message": message}