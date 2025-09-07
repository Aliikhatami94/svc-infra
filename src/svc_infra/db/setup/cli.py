from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, List, cast

import typer, click

from .core import (
    init_alembic as core_init_alembic,
    revision as core_revision,
    upgrade as core_upgrade,
    downgrade as core_downgrade,
    current as core_current,
    history as core_history,
    stamp as core_stamp,
    merge_heads as core_merge_heads,
    setup_and_migrate as core_setup_and_migrate,
)
from .scaffold import (
    scaffold_core,
    scaffold_models_core,
    scaffold_schemas_core,
    Kind,
)

app = typer.Typer(no_args_is_help=True, add_completion=False)


def _apply_database_url(database_url: Optional[str]) -> None:
    if database_url:
        os.environ["DATABASE_URL"] = database_url


@app.command("init")
def init(
        project_root: Path = typer.Option(
            Path(".."),
            exists=False,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
            help="Project root where alembic.ini and migrations/ will be created.",
        ),
        database_url: Optional[str] = typer.Option(
            None,
            help="Database URL; overrides env DATABASE_URL for this command. "
                 "Async vs sync is auto-detected from the URL."
        ),
        discover_packages: Optional[List[str]] = typer.Option(
            None,
            help="Packages to search for SQLAlchemy metadata; may pass multiple. "
                 "If omitted, automatic discovery is used."
        ),
        overwrite: bool = typer.Option(
            False,
            help="Overwrite existing files if present."
        ),
):
    """
    Initialize Alembic scaffold. The env.py variant (async vs. sync) is
    auto-detected from DATABASE_URL (if available at init time).
    """
    _apply_database_url(database_url)
    core_init_alembic(
        project_root=project_root,
        discover_packages=discover_packages,
        overwrite=overwrite,
    )


@app.command()
def revision(
        message: str = typer.Option(..., "-m", "--message", help="Revision message."),
        project_root: Path = typer.Option(Path(".."), help="Project root with alembic.ini.", resolve_path=True),
        database_url: Optional[str] = typer.Option(None, help="Database URL; overrides env for this command."),
        autogenerate: bool = typer.Option(False, help="Autogenerate migrations by comparing metadata."),
        head: Optional[str] = typer.Option("head", help="Set the head to base this revision on."),
        branch_label: Optional[str] = typer.Option(None, help="Branch label."),
        version_path: Optional[str] = typer.Option(None, help="Alternative versions/ path."),
        sql: bool = typer.Option(False, help="Don't generate Python; dump SQL to stdout."),
):
    _apply_database_url(database_url)
    core_revision(
        project_root=project_root,
        message=message,
        autogenerate=autogenerate,
        head=head,
        branch_label=branch_label,
        version_path=version_path,
        sql=sql,
    )


@app.command()
def upgrade(
        revision_target: str = typer.Argument("head", help="Target revision (default head)."),
        project_root: Path = typer.Option(Path(".."), resolve_path=True),
        database_url: Optional[str] = typer.Option(None, help="Database URL; overrides env for this command."),
):
    _apply_database_url(database_url)
    core_upgrade(project_root=project_root, revision_target=revision_target)


@app.command()
def downgrade(
        revision_target: str = typer.Argument("-1", help="Target revision (default -1)."),
        project_root: Path = typer.Option(Path(".."), resolve_path=True),
        database_url: Optional[str] = typer.Option(None, help="Database URL; overrides env for this command."),
):
    _apply_database_url(database_url)
    core_downgrade(project_root=project_root, revision_target=revision_target)


@app.command()
def current(
        project_root: Path = typer.Option(Path(".."), resolve_path=True),
        database_url: Optional[str] = typer.Option(None, help="Database URL; overrides env for this command."),
        verbose: bool = typer.Option(False, help="Verbose output."),
):
    _apply_database_url(database_url)
    core_current(project_root=project_root, verbose=verbose)


@app.command()
def history(
        project_root: Path = typer.Option(Path(".."), resolve_path=True),
        database_url: Optional[str] = typer.Option(None, help="Database URL; overrides env for this command."),
        verbose: bool = typer.Option(False, help="Verbose output."),
):
    _apply_database_url(database_url)
    core_history(project_root=project_root, verbose=verbose)


@app.command()
def stamp(
        revision_target: str = typer.Argument("head"),
        project_root: Path = typer.Option(Path(".."), resolve_path=True),
        database_url: Optional[str] = typer.Option(None, help="Database URL; overrides env for this command."),
):
    _apply_database_url(database_url)
    core_stamp(project_root=project_root, revision_target=revision_target)


@app.command("merge-heads")
def merge_heads(
        project_root: Path = typer.Option(Path(".."), resolve_path=True),
        database_url: Optional[str] = typer.Option(None, help="Database URL; overrides env for this command."),
        message: Optional[str] = typer.Option(None, "-m", "--message", help="Merge revision message."),
):
    _apply_database_url(database_url)
    core_merge_heads(project_root=project_root, message=message)


@app.command("setup-and-migrate")
def setup_and_migrate_cmd(
        project_root: Path = typer.Option(Path(".."), resolve_path=True),
        database_url: Optional[str] = typer.Option(
            None,
            help="Overrides env for this command. Async vs sync is auto-detected from the URL."
        ),
        overwrite_scaffold: bool = typer.Option(False, help="Overwrite alembic scaffold if present."),
        create_db_if_missing: bool = typer.Option(True, help="Create the database/schema if missing."),
        create_followup_revision: bool = typer.Option(True, help="Create an autogen follow-up revision if revisions already exist."),
        initial_message: str = typer.Option("initial schema"),
        followup_message: str = typer.Option("autogen"),
):
    """
    End-to-end: ensure DB exists, scaffold Alembic, create/upgrade revisions.
    Async vs. sync is inferred from DATABASE_URL.
    """
    _apply_database_url(database_url)
    core_setup_and_migrate(
        project_root=project_root,
        overwrite_scaffold=overwrite_scaffold,
        create_db_if_missing=create_db_if_missing,
        create_followup_revision=create_followup_revision,
        initial_message=initial_message,
        followup_message=followup_message,
    )


@app.command("scaffold")
def scaffold(
        kind: str = typer.Option(
            "entity",
            "--kind",
            help="Kind of scaffold to generate (entity or auth).",
            click_type=click.Choice(["entity", "auth"], case_sensitive=False),
        ),
        entity_name: str = typer.Option("Item", help="Entity name (for kind=entity)."),
        models_dir: Path = typer.Option(..., help="Directory for models."),
        schemas_dir: Path = typer.Option(..., help="Directory for schemas."),
        overwrite: bool = typer.Option(False, help="Overwrite existing files."),
        same_dir: bool = typer.Option(False, "--same-dir/--no-same-dir", help="Put models & schemas into the same dir."),
        models_filename: Optional[str] = typer.Option(None, help="Custom filename for models (separate-dir mode)."),
        schemas_filename: Optional[str] = typer.Option(None, help="Custom filename for schemas (separate-dir mode)."),
):
    """
    Scaffold starter models/schemas for either:
    - kind=auth   → app/auth/models.py + schemas.py
    - kind=entity → app/models/<file>.py + app/schemas/<file>.py
    """
    res = scaffold_core(
        models_dir=models_dir,
        schemas_dir=schemas_dir,
        kind=cast(Kind, kind.lower()),
        entity_name=entity_name,
        overwrite=overwrite,
        same_dir=same_dir,
        models_filename=models_filename,
        schemas_filename=schemas_filename,
    )
    typer.echo(res)


@app.command("scaffold-models")
def scaffold_models(
        dest_dir: Path = typer.Option(..., "--dest-dir", resolve_path=True),
        kind: str = typer.Option(
            "entity",
            "--kind",
            help="Scaffold type",
            click_type=click.Choice(["entity", "auth"], case_sensitive=False),
        ),
        entity_name: str = typer.Option("Item", "--entity-name"),
        table_name: Optional[str] = typer.Option(None, "--table-name"),
        include_tenant: bool = typer.Option(True, "--include-tenant/--no-include-tenant"),
        include_soft_delete: bool = typer.Option(False, "--include-soft-delete/--no-include-soft-delete"),
        overwrite: bool = typer.Option(False, "--overwrite/--no-overwrite"),
        models_filename: Optional[str] = typer.Option(
            None, "--models-filename",
            help="Filename to write (e.g. project_models.py). Defaults to <snake(entity)>.py",
        ),
):
    res = scaffold_models_core(
        dest_dir=dest_dir,
        kind=cast(Kind, kind.lower()),
        entity_name=entity_name,
        table_name=table_name,
        include_tenant=include_tenant,
        include_soft_delete=include_soft_delete,
        overwrite=overwrite,
        models_filename=models_filename,
    )
    typer.echo(res)


@app.command("scaffold-schemas")
def scaffold_schemas(
        dest_dir: Path = typer.Option(..., "--dest-dir", resolve_path=True),
        kind: str = typer.Option(
            "entity",
            "--kind",
            help="Scaffold type",
            click_type=click.Choice(["entity", "auth"], case_sensitive=False),
        ),
        entity_name: str = typer.Option("Item", "--entity-name"),
        include_tenant: bool = typer.Option(True, "--include-tenant/--no-include-tenant"),
        overwrite: bool = typer.Option(False, "--overwrite/--no-overwrite"),
        schemas_filename: Optional[str] = typer.Option(
            None, "--schemas-filename",
            help="Filename to write (e.g. project_schemas.py). Defaults to <snake(entity)>.py",
        ),
):
    res = scaffold_schemas_core(
        dest_dir=dest_dir,
        kind=cast(Kind, kind.lower()),
        entity_name=entity_name,
        include_tenant=include_tenant,
        overwrite=overwrite,
        schemas_filename=schemas_filename,
    )
    typer.echo(res)


if __name__ == "__main__":
    app()