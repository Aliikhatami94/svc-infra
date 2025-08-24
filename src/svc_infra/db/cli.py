from __future__ import annotations
import os
from pathlib import Path
from typing import Optional

import typer
from alembic import command
from alembic.config import Config

app = typer.Typer(no_args_is_help=True, add_completion=False)

AL_EMBIC_DIR = "migrations"  # folder name for alembic scripts
ALEMBIC_INI = "alembic.ini"


def _load_config(project_root: Path, database_url: Optional[str]) -> Config:
    cfg = Config(str(project_root / ALEMBIC_INI))
    db_url = database_url or os.getenv("DATABASE_URL")
    if db_url:
        cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("script_location", str(project_root / AL_EMBIC_DIR))
    # IMPORTANT: let env.py decide logging (app logger vs fileConfig)
    cfg.attributes["configure_logger"] = False
    return cfg

# NEW: helper to normalize the models module
def _normalize_models_module(raw: str) -> str:
    # strip any leading "src." and redundant dots/spaces
    m = raw.strip().lstrip(".")
    if m.startswith("src."):
        m = m[4:]
    return m

@app.command("init")
def init(
        project_root: Path = typer.Option(Path.cwd(), help="Root of your app (where alembic.ini should live)"),
        models_module: str = typer.Option(..., help="Import path to your models module exposing Base (e.g. 'app.models')"),
        database_url: Optional[str] = typer.Option(None, help="Override DATABASE_URL; defaults to env"),
        async_db: bool = typer.Option(True, help="Use async engine (postgresql+asyncpg)")
):
    """Scaffold alembic (alembic.ini, migrations/, env.py) wired to your Base."""
    project_root = project_root.resolve()
    (project_root / AL_EMBIC_DIR).mkdir(parents=True, exist_ok=True)
    normalized_models_module = _normalize_models_module(models_module)

    # 1) alembic.ini
    ini_path = project_root / ALEMBIC_INI
    if not ini_path.exists():
        ini_path.write_text(f"""\
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
""", encoding="utf-8")
        typer.echo(f"Wrote {ini_path}")
    else:
        typer.echo(f"SKIP {ini_path} (exists)")

    # 2) env.py (async-aware)
    env_py = (project_root / AL_EMBIC_DIR / "env.py")
    if not env_py.exists():
        run_cmd = "asyncio.run(run_migrations_online_async())" if async_db else "run_migrations_online_sync()"
        content = f"""\
from __future__ import annotations
import os
import sys
import asyncio
import logging
from pathlib import Path
from importlib import import_module
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy import engine_from_config
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.engine.url import make_url

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

# --- Models/Base wiring ---
models_module = "{normalized_models_module}"
module = __import__(models_module, fromlist=["Base"])
target_metadata = getattr(module, "Base").metadata

# --- Choose async/sync path from URL automatically ---
url_str = config.get_main_option("sqlalchemy.url") or ""
driver = ""
try:
    driver = make_url(url_str).drivername.split("+", 1)[1]
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
    if is_async:
        asyncio.run(run_migrations_online_async())
    else:
        run_migrations_online_sync()
"""
        env_py.write_text(content, encoding="utf-8")
        typer.echo(f"Wrote {env_py}")
    else:
        typer.echo(f"SKIP {env_py} (exists)")

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


if __name__ == "__main__":
    app()