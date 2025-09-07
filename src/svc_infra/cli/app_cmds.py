from __future__ import annotations

import typer, sys, os
from pathlib import Path

from svc_infra.cli.alembic_cmds import resolve_project_root


HELP = """\
svc-infra — service infrastructure CLI

How to run (pick what fits your workflow):

  1) Installed console script (recommended)
     $ svc-infra <command> [options]
     e.g.:
     $ svc-infra setup-and-migrate

  2) Poetry shim (inside a Poetry project)
     $ poetry run svc-infra <command> [options]
     e.g.:
     $ poetry run svc-infra setup-and-migrate

Notes:
* Make sure you’re in the right virtual environment (or use `pipx`).
* You can set DATABASE_URL in your environment, or pass --database-url to commands.
* You can point `--project-root` at your Alembic root; if omitted we auto-detect.
"""

def load_env_file(env_path: str | Path = ".env") -> None:
    """
    Load all key=value pairs from a .env file and export them to os.environ.

    Args:
        env_path: Path to the .env file (default: ./.env).
    """
    env_file = Path(env_path)
    if not env_file.exists():
        raise FileNotFoundError(f".env file not found at {env_file.resolve()}")

    with env_file.open("r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue  # skip malformed lines

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ[key] = value

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