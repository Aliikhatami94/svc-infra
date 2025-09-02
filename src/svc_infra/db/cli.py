import typer
from pathlib import Path
from typing import Optional

from .core import (
    db_init_core, db_revision_core, db_upgrade_core, db_downgrade_core,
    db_current_core, db_history_core, db_stamp_core, db_drop_table_core,
    db_merge_heads_core
)

app = typer.Typer(no_args_is_help=True, add_completion=False)

@app.command("init", help="Initialize alembic environment")
def init(
        project_root: Path = typer.Option(Path.cwd(), help="Root of your app (where alembic.ini should live)"),
        database_url: Optional[str] = typer.Option(None, help="Override DATABASE_URL; defaults to env"),
        async_db: bool = typer.Option(True, help="Use async engine (postgresql+asyncpg)"),
        discover_packages: Optional[str] = typer.Option(None, help="Comma-separated packages to crawl for models"),
):
    res = db_init_core(
        project_root=project_root, database_url=database_url,
        async_db=async_db, discover_packages=discover_packages
    )
    for n in res.get("notes", []):
        typer.echo(n)

@app.command("revision", help="Create new migration revision")
def revision(
        message: str = typer.Option(..., "-m", "--message", help="Migration message"),
        autogenerate: bool = typer.Option(True, help="Autogenerate from model diffs"),
        project_root: Path = typer.Option(Path.cwd(), help="Root containing alembic.ini"),
        database_url: Optional[str] = typer.Option(None, help="Override DATABASE_URL"),
):
    db_revision_core(message=message, autogenerate=autogenerate, project_root=project_root, database_url=database_url)
    typer.echo("Created revision.")

@app.command("upgrade", help="Upgrade to a later version")
def upgrade(
        revision: str = typer.Argument("head"),
        project_root: Path = typer.Option(Path.cwd(), help="Root containing alembic.ini"),
        database_url: Optional[str] = typer.Option(None, help="Override DATABASE_URL"),
):
    db_upgrade_core(revision=revision, project_root=project_root, database_url=database_url)
    typer.echo(f"Upgraded to {revision}.")

@app.command("downgrade", help="Downgrade to an earlier version")
def downgrade(
        revision: str = typer.Argument("-1"),
        project_root: Path = typer.Option(Path.cwd(), help="Root containing alembic.ini"),
        database_url: Optional[str] = typer.Option(None, help="Override DATABASE_URL"),
):
    db_downgrade_core(revision=revision, project_root=project_root, database_url=database_url)
    typer.echo(f"Downgraded to {revision}.")

@app.command("current", help="Display current revision")
def current(
        verbose: bool = typer.Option(False, help="Verbose output"),
        project_root: Path = typer.Option(Path.cwd(), help="Root containing alembic.ini"),
        database_url: Optional[str] = typer.Option(None, help="Override DATABASE_URL"),
):
    db_current_core(verbose=verbose, project_root=project_root, database_url=database_url)

@app.command("history", help="Display revision history")
def history(
        verbose: bool = typer.Option(False, help="Verbose output"),
        project_root: Path = typer.Option(Path.cwd(), help="Root containing alembic.ini"),
        database_url: Optional[str] = typer.Option(None, help="Override DATABASE_URL"),
):
    db_history_core(verbose=verbose, project_root=project_root, database_url=database_url)

@app.command("stamp", help="Stamp database with a revision (no upgrade/downgrade)")
def stamp(
        revision: str = typer.Argument("head"),
        project_root: Path = typer.Option(Path.cwd(), help="Root containing alembic.ini"),
        database_url: Optional[str] = typer.Option(None, help="Override DATABASE_URL"),
):
    db_stamp_core(revision=revision, project_root=project_root, database_url=database_url)
    typer.echo(f"Stamped {revision}.")

@app.command("drop-table", help="Create a migration to drop a table")
def drop_table(
        table: str = typer.Argument(..., help="Table name (optionally schema.table)"),
        cascade: bool = typer.Option(False, help="Use CASCADE"),
        if_exists: bool = typer.Option(True, help="Use IF EXISTS"),
        message: Optional[str] = typer.Option(None, "-m", "--message", help="Migration message"),
        base: Optional[str] = typer.Option(None, help="Force down_revision to this revision id"),
        apply: bool = typer.Option(False, help="Run upgrade head after creating the revision"),
        project_root: Path = typer.Option(Path.cwd(), help="Root with alembic.ini"),
        database_url: Optional[str] = typer.Option(None, help="Override DATABASE_URL"),
):
    res = db_drop_table_core(
        table=table, cascade=cascade, if_exists=if_exists, message=message,
        base=base, apply=apply, project_root=project_root, database_url=database_url
    )
    typer.echo(f"Wrote {res['wrote']}")
    if res.get("applied"):
        typer.echo("Applied migration (upgrade head).")

@app.command("merge-heads", help="Merge multiple heads into one")
def merge_heads(
        message: str = typer.Option("merge heads", "-m", "--message"),
        project_root: Path = typer.Option(Path.cwd()),
        database_url: Optional[str] = typer.Option(None),
):
    res = db_merge_heads_core(message=message, project_root=project_root, database_url=database_url)
    if res["status"] == "noop":
        typer.echo("Nothing to merge (0 or 1 head).")
    else:
        typer.echo(f"Created merge for heads: {', '.join(res['merged'])}")