from __future__ import annotations

from pathlib import Path
import typer

from .core import (
    scaffold_auth_core,
    scaffold_auth_models_core,
    scaffold_auth_schemas_core,
)

app = typer.Typer(no_args_is_help=True, add_completion=False)

def _echo_result(r: dict) -> None:
    action = r.get("action")
    path = r.get("path")
    if action == "wrote":
        typer.echo(f"Wrote {path}")
    elif action == "skipped":
        reason = r.get("reason", "skipped")
        typer.echo(f"SKIP {path} ({reason}). Use --overwrite to replace.")
    else:
        typer.echo(f"{action or 'done'} {path}")

@app.command("scaffold-auth", help="Scaffold auth models.py and schemas.py from templates")
def scaffold_auth(
        models_dir: Path = typer.Option(..., help="Where to place models.py"),
        schemas_dir: Path = typer.Option(..., help="Where to place schemas.py"),
        overwrite: bool = typer.Option(False, help="Overwrite files if they exist"),
):
    res = scaffold_auth_core(models_dir=models_dir, schemas_dir=schemas_dir, overwrite=overwrite)
    _echo_result(res["results"]["models"])
    _echo_result(res["results"]["schemas"])

@app.command("scaffold-auth-models", help="Scaffold auth models.py from template")
def scaffold_auth_models(
        dest_dir: Path = typer.Option(..., help="Directory to place models.py"),
        overwrite: bool = typer.Option(False, help="Overwrite if exists"),
):
    res = scaffold_auth_models_core(dest_dir=dest_dir, overwrite=overwrite)
    _echo_result(res["result"])

@app.command("scaffold-auth-schemas", help="Scaffold auth schemas.py from template")
def scaffold_auth_schemas(
        dest_dir: Path = typer.Option(..., help="Directory to place schemas.py"),
        overwrite: bool = typer.Option(False, help="Overwrite if exists"),
):
    res = scaffold_auth_schemas_core(dest_dir=dest_dir, overwrite=overwrite)
    _echo_result(res["result"])