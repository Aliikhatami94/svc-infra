from __future__ import annotations
from pathlib import Path
from string import Template
import importlib.resources as pkg
import typer

app = typer.Typer(no_args_is_help=True, add_completion=False)

TEMPLATES_PKG = "svc_infra.auth.templates"  # must be a package with the .tmpl files

def _render(name: str, ctx: dict[str, str]) -> str:
    txt = pkg.files(TEMPLATES_PKG).joinpath(name).read_text(encoding="utf-8")
    return Template(txt).substitute(**ctx)

def _write(dest: Path, content: str, overwrite: bool):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not overwrite:
        typer.echo(f"SKIP {dest} (exists). Use --overwrite to replace.")
        return
    dest.write_text(content, encoding="utf-8")
    typer.echo(f"Wrote {dest}")

@app.command("scaffold-auth")
def scaffold_auth(
        models_dir: Path = typer.Option(..., help="Where to place models.py"),
        schemas_dir: Path = typer.Option(..., help="Where to place schemas.py"),
        overwrite: bool = typer.Option(False, help="Overwrite files if they exist"),
):
    # no table_name anymore; template should hardcode __tablename__ = "users"
    _write(Path(models_dir) / "models.py", _render("models.py.tmpl", {}), overwrite)
    _write(Path(schemas_dir) / "schemas.py", _render("schemas.py.tmpl", {}), overwrite)

@app.command("scaffold-auth-models")
def scaffold_auth_models(
        dest_dir: Path = typer.Option(..., help="Directory to place models.py"),
        overwrite: bool = typer.Option(False, help="Overwrite if exists"),
):
    _write(Path(dest_dir) / "models.py", _render("models.py.tmpl", {}), overwrite)

@app.command("scaffold-auth-schemas")
def scaffold_auth_schemas(
        dest_dir: Path = typer.Option(..., help="Directory to place schemas.py"),
        overwrite: bool = typer.Option(False, help="Overwrite if exists"),
):
    _write(Path(dest_dir) / "schemas.py", _render("schemas.py.tmpl", {}), overwrite)