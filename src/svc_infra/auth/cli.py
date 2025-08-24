from __future__ import annotations
from pathlib import Path
from string import Template
import importlib.resources as pkg
import typer

app = typer.Typer(no_args_is_help=True, add_completion=False)


def _render(name: str, ctx: dict[str, str]) -> str:
    txt = pkg.files("svc_infra.auth.templates").joinpath(name).read_text(encoding="utf-8")
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
    routers_dir: Path = typer.Option(..., help="Where to place routers (users + oauth + include)"),
    table_name: str = typer.Option("users", help="SQL table name"),
    auth_prefix: str = typer.Option("/auth", help="Auth API prefix"),
    oauth_prefix: str = typer.Option("/oauth", help="OAuth API prefix"),
    post_login_redirect: str = typer.Option("/", help="Where to redirect with ?token=..."),
    overwrite: bool = typer.Option(False, help="Overwrite files if they exist"),
):
    ctx_common = dict(
        table_name=table_name,
        auth_prefix=auth_prefix,
        oauth_prefix=oauth_prefix,
        post_login_redirect=post_login_redirect,
    )

    _write(Path(models_dir) / "models.py", _render("models.py.tmpl", ctx_common), overwrite)
    _write(Path(schemas_dir) / "schemas.py", _render("schemas.py.tmpl", ctx_common), overwrite)
    _write(Path(routers_dir) / "users.py", _render("users.py.tmpl", ctx_common), overwrite)
    _write(Path(routers_dir) / "oauth_router.py", _render("oauth_router.py.tmpl", ctx_common), overwrite)
    _write(Path(routers_dir) / "settings.py", _render("settings.py.tmpl", ctx_common), overwrite)
    _write(Path(routers_dir) / "include_routers.py", _render("include_routers.py.tmpl", ctx_common), overwrite)


# One-by-one scaffolders for simplicity
@app.command("scaffold-auth-models")
def scaffold_auth_models(
    dest_dir: Path = typer.Option(..., help="Directory to place models.py"),
    table_name: str = typer.Option("users", help="SQL table name"),
    overwrite: bool = typer.Option(False, help="Overwrite if exists"),
):
    _write(Path(dest_dir) / "models.py", _render("models.py.tmpl", {"table_name": table_name}), overwrite)


@app.command("scaffold-auth-schemas")
def scaffold_auth_schemas(
    dest_dir: Path = typer.Option(..., help="Directory to place schemas.py"),
    overwrite: bool = typer.Option(False, help="Overwrite if exists"),
):
    _write(Path(dest_dir) / "schemas.py", _render("schemas.py.tmpl", {}), overwrite)


@app.command("scaffold-auth-settings")
def scaffold_auth_settings(
    dest_dir: Path = typer.Option(..., help="Directory to place auth settings.py"),
    overwrite: bool = typer.Option(False, help="Overwrite if exists"),
):
    _write(Path(dest_dir) / "settings.py", _render("settings.py.tmpl", {}), overwrite)


@app.command("scaffold-auth-users-router")
def scaffold_auth_users_router(
    dest_dir: Path = typer.Option(..., help="Directory to place users.py router"),
    auth_prefix: str = typer.Option("/auth", help="Auth API prefix"),
    overwrite: bool = typer.Option(False, help="Overwrite if exists"),
):
    ctx = dict(auth_prefix=auth_prefix)
    _write(Path(dest_dir) / "users.py", _render("users.py.tmpl", ctx), overwrite)


@app.command("scaffold-auth-oauth-router")
def scaffold_auth_oauth_router(
    dest_dir: Path = typer.Option(..., help="Directory to place oauth_router.py"),
    oauth_prefix: str = typer.Option("/oauth", help="OAuth API prefix"),
    post_login_redirect: str = typer.Option("/", help="Where to redirect with ?token=..."),
    overwrite: bool = typer.Option(False, help="Overwrite if exists"),
):
    ctx = dict(oauth_prefix=oauth_prefix, post_login_redirect=post_login_redirect)
    _write(Path(dest_dir) / "oauth_router.py", _render("oauth_router.py.tmpl", ctx), overwrite)


@app.command("scaffold-auth-include")
def scaffold_auth_include(
    dest_dir: Path = typer.Option(..., help="Directory to place include_routers.py"),
    auth_prefix: str = typer.Option("/auth", help="Auth API prefix"),
    overwrite: bool = typer.Option(False, help="Overwrite if exists"),
):
    ctx = dict(auth_prefix=auth_prefix)
    _write(Path(dest_dir) / "include_routers.py", _render("include_routers.py.tmpl", ctx), overwrite)


if __name__ == "__main__":
    app()