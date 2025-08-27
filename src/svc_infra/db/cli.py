from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent
from typing import Optional

from alembic.script import ScriptDirectory

import typer
from alembic import command
from alembic.config import Config

app = typer.Typer(no_args_is_help=True, add_completion=False)

AL_EMBIC_DIR = "migrations"
ALEMBIC_INI = "alembic.ini"


def _load_config(project_root: Path, database_url: Optional[str]) -> Config:
    cfg = Config(str(project_root / ALEMBIC_INI))
    db_url = database_url or os.getenv("DATABASE_URL")
    if db_url:
        cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("script_location", str(project_root / AL_EMBIC_DIR))
    # let env.py decide logging (app logger vs fileConfig)
    cfg.attributes["configure_logger"] = False
    return cfg


def _infer_default_roots(project_root: Path) -> list[str]:
    """
    Find top-level importable packages under project root and src/.
    Returns a list of package names (directories with __init__.py).
    """
    roots: list[str] = []
    for base in (project_root, project_root / "src"):
        if not base.exists():
            continue
        for d in base.iterdir():
            if d.is_dir() and (d / "__init__.py").exists():
                roots.append(d.name)
    # de-dupe but keep order
    seen = set()
    out = []
    for r in roots:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


@app.command("init")
def init(
        project_root: Path = typer.Option(Path.cwd(), help="Root of your app (where alembic.ini should live)"),
        database_url: Optional[str] = typer.Option(None, help="Override DATABASE_URL; defaults to env"),
        async_db: bool = typer.Option(True, help="Use async engine (postgresql+asyncpg)"),
        discover_packages: Optional[str] = typer.Option(
            None,
            help="Comma-separated top-level packages to crawl for models (defaults to packages under project root and src/)",
        ),
):
    """
    Scaffold alembic (alembic.ini, migrations/, env.py, script.py.mako) wired to *all* Declarative Bases discovered.
    """
    project_root = project_root.resolve()
    (project_root / AL_EMBIC_DIR).mkdir(parents=True, exist_ok=True)

    # 1) alembic.ini
    ini_path = project_root / ALEMBIC_INI
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
        typer.echo(f"Wrote {ini_path}")
    else:
        typer.echo(f"SKIP {ini_path} (exists)")

    # Figure out which packages to walk for model discovery
    if discover_packages:
        discover_root_csv = ",".join([p.strip() for p in discover_packages.split(",") if p.strip()])
    else:
        discover_root_csv = ",".join(_infer_default_roots(project_root))  # e.g. "apiframeworks_api,svc_infra"

    # 2) env.py (async-aware, app-logging-aware, model auto-discovery)
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
                    print(f"[alembic] App logging import failed: {{e}}. Falling back to fileConfig.")

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
            DISCOVER_PKGS = os.getenv("ALEMBIC_DISCOVER_PACKAGES", "{discover_root_csv}")

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
                            logging.getLogger(__name__).debug(f"[alembic] Skipped import {{mod_name}}: {{e}}")

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
        typer.echo(f"Wrote {env_py}")
    else:
        typer.echo(f"SKIP {env_py} (exists)")

    # 2.5) script.py.mako (needed for `revision --autogenerate`)
    # Keep fastapi_users_db_sqlalchemy import so GUID() etc. resolve in generated scripts.
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
        import fastapi_users_db_sqlalchemy  # noqa: F401  (types used in models/migrations)

        # revision identifiers, used by Alembic.
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
        typer.echo(f"Wrote {script_path}")
    else:
        typer.echo(f"SKIP {script_path} (exists)")

    # 3) versions dir
    versions = project_root / AL_EMBIC_DIR / "versions"
    versions.mkdir(exist_ok=True)
    typer.echo(f"Ensured {versions}")


@app.command("revision")
def revision(
        message: str = typer.Option(..., "-m", "--message", help="Migration message"),
        autogenerate: bool = typer.Option(True, help="Autogenerate from model diffs"),
        project_root: Path = typer.Option(Path.cwd(), help="Root containing alembic.ini"),
        database_url: Optional[str] = typer.Option(None, help="Override DATABASE_URL"),
):
    cfg = _load_config(project_root.resolve(), database_url)
    command.revision(cfg, message=message, autogenerate=autogenerate)


@app.command("upgrade")
def upgrade(
        revision: str = typer.Argument("head"),
        project_root: Path = typer.Option(Path.cwd(), help="Root containing alembic.ini"),
        database_url: Optional[str] = typer.Option(None, help="Override DATABASE_URL"),
):
    cfg = _load_config(project_root.resolve(), database_url)
    command.upgrade(cfg, revision)


@app.command("downgrade")
def downgrade(
        revision: str = typer.Argument("-1"),
        project_root: Path = typer.Option(Path.cwd(), help="Root containing alembic.ini"),
        database_url: Optional[str] = typer.Option(None, help="Override DATABASE_URL"),
):
    cfg = _load_config(project_root.resolve(), database_url)
    command.downgrade(cfg, revision)


@app.command("current")
def current(
        verbose: bool = typer.Option(False, help="Verbose output"),
        project_root: Path = typer.Option(Path.cwd(), help="Root containing alembic.ini"),
        database_url: Optional[str] = typer.Option(None, help="Override DATABASE_URL"),
):
    cfg = _load_config(project_root.resolve(), database_url)
    command.current(cfg, verbose=verbose)


@app.command("history")
def history(
        verbose: bool = typer.Option(False, help="Verbose output"),
        project_root: Path = typer.Option(Path.cwd(), help="Root containing alembic.ini"),
        database_url: Optional[str] = typer.Option(None, help="Override DATABASE_URL"),
):
    cfg = _load_config(project_root.resolve(), database_url)
    command.history(cfg, verbose=verbose)


@app.command("stamp")
def stamp(
        revision: str = typer.Argument("head"),
        project_root: Path = typer.Option(Path.cwd(), help="Root containing alembic.ini"),
        database_url: Optional[str] = typer.Option(None, help="Override DATABASE_URL"),
):
    cfg = _load_config(project_root.resolve(), database_url)
    command.stamp(cfg, revision)


def _versions_dir(project_root: Path) -> Path:
    return project_root / AL_EMBIC_DIR / "versions"


def _latest_version_file(versions_dir: Path) -> Path | None:
    if not versions_dir.exists():
        return None
    candidates = [p for p in versions_dir.iterdir() if p.is_file() and p.suffix == ".py"]
    if not candidates:
        return None
    # newest by mtime
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _script_dir(cfg: Config) -> ScriptDirectory:
    return ScriptDirectory.from_config(cfg)


def _single_head_or_none(script: ScriptDirectory) -> str | None:
    heads = script.get_heads()
    if len(heads) == 0:
        return None
    if len(heads) == 1:
        return heads[0]
    # Multiple heads: let caller decide or raise
    raise RuntimeError(f"Multiple heads present: {', '.join(heads)}")


@app.command("drop-table")
def drop_table(
        table: str = typer.Argument(..., help="Table name (optionally schema.table)"),
        cascade: bool = typer.Option(False, help="Use CASCADE"),
        if_exists: bool = typer.Option(True, help="Use IF EXISTS"),
        message: Optional[str] = typer.Option(None, "-m", "--message", help="Migration message"),
        base: Optional[str] = typer.Option(None, help="Force down_revision to this revision id (use when multiple heads)"),
        apply: bool = typer.Option(False, help="Run upgrade head after creating the revision"),
        project_root: Path = typer.Option(Path.cwd(), help="Root with alembic.ini"),
        database_url: Optional[str] = typer.Option(None, help="Override DATABASE_URL"),
):
    cfg = _load_config(project_root.resolve(), database_url)
    script = _script_dir(cfg)

    msg = message or f"drop table {table}"
    command.revision(cfg, message=msg, autogenerate=False)

    versions_dir = project_root.resolve() / AL_EMBIC_DIR / "versions"
    rev_file = _latest_version_file(versions_dir)
    if rev_file is None:
        raise typer.Exit(code=1)

    # Decide down_revision
    try:
        down_rev = base or _single_head_or_none(script)
    except RuntimeError as e:
        typer.echo(str(e))
        typer.echo("Tip: re-run with --base <rev> or merge heads first.")
        raise typer.Exit(code=2)

    fq_table = table.strip()
    sql = f'DROP TABLE {"IF EXISTS " if if_exists else ""}{fq_table}{" CASCADE" if cascade else ""};'
    rev_id = rev_file.stem.split("_", 1)[0]

    content = f'''""" {msg} """\n\nfrom __future__ import annotations\n\nfrom alembic import op\nimport sqlalchemy as sa\n\n# revision identifiers, used by Alembic.\nrevision = "{rev_id}"\ndown_revision = {repr(down_rev) if down_rev else "None"}\nbranch_labels = None\ndepends_on = None\n\n\n
def upgrade() -> None:\n    op.execute({sql!r})\n\n\n
def downgrade() -> None:\n    # Irreversible without full table definition\n    pass\n'''
    rev_file.write_text(content, encoding="utf-8")
    typer.echo(f"Wrote drop migration: {rev_file}")

    if apply:
        command.upgrade(cfg, "head")
        typer.echo("Applied migration (upgrade head).")


@app.command("merge-heads")
def merge_heads(
        message: str = typer.Option("merge heads", "-m", "--message"),
        project_root: Path = typer.Option(Path.cwd()),
        database_url: Optional[str] = typer.Option(None),
):
    cfg = _load_config(project_root.resolve(), database_url)
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    if len(heads) <= 1:
        typer.echo("Nothing to merge (0 or 1 head).")
        return
    # Create a merge revision that depends on all current heads
    from alembic import command
    command.merge(cfg, revisions=heads, message=message)
    typer.echo(f"Created merge for heads: {', '.join(heads)}")