from __future__ import annotations

import typer, sys

from svc_infra.cli.alembic_cmds import resolve_project_root


def cmd_doctor() -> None:
    """Provides environment info of current project for debugging."""
    import os, pathlib
    root= resolve_project_root()
    typer.echo(f"Root:         {root}")
    typer.echo(f"Python:       {sys.executable}")
    typer.echo(f"Package:      {__package__ or 'svc_infra'}")
    typer.echo(f"Working dir:  {pathlib.Path.cwd()}")
    typer.echo(f"DATABASE_URL: {os.getenv('DATABASE_URL') or '<unset>'}")

def register(app: typer.Typer) -> None:
    app.command("doctor")(cmd_doctor)