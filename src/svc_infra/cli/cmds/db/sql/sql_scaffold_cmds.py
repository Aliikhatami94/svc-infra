from __future__ import annotations

from pathlib import Path
from typing import Optional, cast

import click
import typer

from svc_infra.db.sql.scaffold import (
    Kind,
    scaffold_core,
    scaffold_models_core,
    scaffold_schemas_core,
)


def cmd_scaffold(
    kind: str = typer.Option(
        "entity",
        "--kind",
        click_type=click.Choice(["entity", "auth"], case_sensitive=False),
    ),
    entity_name: str = typer.Option(
        "Item", help="Class name for entity/auth (e.g., User, Member, Product)."
    ),
    table_name: Optional[str] = typer.Option(
        None,
        help="Optional table name. For kind=auth, can also be set via AUTH_TABLE_NAME; defaults to plural snake of entity.",
    ),
    models_dir: Path = typer.Option(..., help="Directory for models."),
    schemas_dir: Path = typer.Option(..., help="Directory for schemas."),
    overwrite: bool = typer.Option(False, help="Overwrite existing files."),
    same_dir: bool = typer.Option(
        False,
        "--same-dir/--no-same-dir",
        help="Put models & schemas into the same dir.",
    ),
    models_filename: Optional[str] = typer.Option(
        None, help="Custom filename for models (separate-dir mode)."
    ),
    schemas_filename: Optional[str] = typer.Option(
        None, help="Custom filename for schemas (separate-dir mode)."
    ),
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
        table_name=table_name,
        overwrite=overwrite,
        same_dir=same_dir,
        models_filename=models_filename,
        schemas_filename=schemas_filename,
    )
    typer.echo(res)


def cmd_scaffold_models(
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
    include_soft_delete: bool = typer.Option(
        False, "--include-soft-delete/--no-include-soft-delete"
    ),
    overwrite: bool = typer.Option(False, "--overwrite/--no-overwrite"),
    models_filename: Optional[str] = typer.Option(
        None,
        "--models-filename",
        help="Filename to write (e.g. project_models.py). Defaults to <snake(entity)>.py",
    ),
):
    """
    Scaffold starter SQLAlchemy models for either:
    - kind=auth   → app/auth/models.py
    - kind=entity → app/models/<file>.py
    """
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


def cmd_scaffold_schemas(
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
        None,
        "--schemas-filename",
        help="Filename to write (e.g. project_schemas.py). Defaults to <snake(entity)>.py",
    ),
):
    """
    Scaffold starter Pydantic schemas for either:
    - kind=auth   → app/auth/schemas.py
    - kind=entity → app/schemas/<file>.py
    """
    res = scaffold_schemas_core(
        dest_dir=dest_dir,
        kind=cast(Kind, kind.lower()),
        entity_name=entity_name,
        include_tenant=include_tenant,
        overwrite=overwrite,
        schemas_filename=schemas_filename,
    )
    typer.echo(res)


def register(app: typer.Typer) -> None:
    app.command("scaffold")(cmd_scaffold)
    app.command("scaffold-models")(cmd_scaffold_models)
    app.command("scaffold-schemas")(cmd_scaffold_schemas)
