from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from svc_infra.db.nosql.scaffold import (
    scaffold_core,
    scaffold_documents_core,
    scaffold_resources_core,
    scaffold_schemas_core,
)


def cmd_scaffold(
    entity_name: str = typer.Option(
        "Item", help="Entity class name (e.g., User, Member, Product)."
    ),
    documents_dir: Path = typer.Option(..., help="Directory for Mongo document models."),
    schemas_dir: Path = typer.Option(..., help="Directory for Pydantic CRUD schemas."),
    overwrite: bool = typer.Option(False, help="Overwrite existing files."),
    same_dir: bool = typer.Option(
        False,
        "--same-dir/--no-same-dir",
        help="Put documents & schemas into the same directory.",
    ),
    documents_filename: Optional[str] = typer.Option(
        None, help="Custom filename for documents (separate-dir mode)."
    ),
    schemas_filename: Optional[str] = typer.Option(
        None, help="Custom filename for schemas (separate-dir mode)."
    ),
):
    """
    Scaffold starter Mongo document + CRUD schemas:
      • documents/<file>.py
      • schemas/<file>.py
    """
    res = scaffold_core(
        documents_dir=documents_dir,
        schemas_dir=schemas_dir,
        entity_name=entity_name,
        overwrite=overwrite,
        same_dir=same_dir,
        documents_filename=documents_filename,
        schemas_filename=schemas_filename,
    )
    typer.echo(res)


def cmd_scaffold_documents(
    dest_dir: Path = typer.Option(..., "--dest-dir", resolve_path=True),
    entity_name: str = typer.Option("Item", "--entity-name"),
    overwrite: bool = typer.Option(False, "--overwrite/--no-overwrite"),
    documents_filename: Optional[str] = typer.Option(
        None,
        "--documents-filename",
        help="Filename to write (e.g. product_doc.py). Defaults to <snake(entity)>.py",
    ),
):
    """Scaffold only the Mongo document model (Pydantic)."""
    res = scaffold_documents_core(
        dest_dir=dest_dir,
        entity_name=entity_name,
        overwrite=overwrite,
        documents_filename=documents_filename,
    )
    typer.echo(res)


def cmd_scaffold_schemas(
    dest_dir: Path = typer.Option(..., "--dest-dir", resolve_path=True),
    entity_name: str = typer.Option("Item", "--entity-name"),
    overwrite: bool = typer.Option(False, "--overwrite/--no-overwrite"),
    schemas_filename: Optional[str] = typer.Option(
        None,
        "--schemas-filename",
        help="Filename to write (e.g. product_schemas.py). Defaults to <snake(entity)>.py",
    ),
):
    """Scaffold only the CRUD schemas (Pydantic)."""
    res = scaffold_schemas_core(
        dest_dir=dest_dir,
        entity_name=entity_name,
        overwrite=overwrite,
        schemas_filename=schemas_filename,
    )
    typer.echo(res)


def cmd_scaffold_resources(
    dest_dir: Path = typer.Option(..., "--dest-dir", resolve_path=True),
    entity_name: str = typer.Option(
        "Item",
        "--entity-name",
        help="Used only to prefill example placeholders.",
    ),
    filename: Optional[str] = typer.Option(
        None,
        "--filename",
        help='Output filename (default: "resources.py")',
    ),
    overwrite: bool = typer.Option(False, "--overwrite/--no-overwrite"),
):
    """
    Scaffold a starter resources.py with an empty RESOURCES list.

    NOTE: Indexes are now declared directly on each NoSqlResource via its `indexes`
    attribute (e.g., `[IndexModel([...]), ...]`). There is no separate index-builders hook.
    """
    res = scaffold_resources_core(
        dest_dir=dest_dir,
        entity_name=entity_name,
        filename=filename,
        overwrite=overwrite,
    )
    typer.echo(res)


def register(app: typer.Typer) -> None:
    """
    Register Mongo scaffold commands on the given Typer app.
    Commands:
      • mongo-scaffold
      • mongo-scaffold-documents
      • mongo-scaffold-schemas
      • mongo-scaffold-resources
    """
    app.command("scaffold")(cmd_scaffold)
    app.command("scaffold-documents")(cmd_scaffold_documents)
    app.command("scaffold-schemas")(cmd_scaffold_schemas)
    app.command("scaffold-resources")(cmd_scaffold_resources)
