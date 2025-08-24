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
        sqlalchemy_base_import: str = typer.Option(..., help='Import path to your SQLAlchemy Base (e.g. "app.db.base import Base")'),
        session_dep_import: str = typer.Option(..., help='Module path to your SessionDep (e.g. "my_app.db.integration_fastapi")'),
        table_name: str = typer.Option("users", help="SQL table name"),
        auth_prefix: str = typer.Option("/auth", help="Auth API prefix"),
        oauth_prefix: str = typer.Option("/oauth", help="OAuth API prefix"),
        post_login_redirect: str = typer.Option("/", help="Where to redirect with ?token=..."),
        overwrite: bool = typer.Option(False, help="Overwrite files if they exist"),
):
    ctx = dict(
        sqlalchemy_base_import=sqlalchemy_base_import,
        session_dep_import=session_dep_import,
        table_name=table_name,
        auth_prefix=auth_prefix,
        oauth_prefix=oauth_prefix,
        post_login_redirect=post_login_redirect,
    )

    _write(Path(models_dir) / "models.py", _render("models.py.tmpl", ctx), overwrite)
    _write(Path(schemas_dir) / "schemas.py", _render("schemas.py.tmpl", ctx), overwrite)
    _write(Path(routers_dir) / "users.py", _render("users.py.tmpl", ctx), overwrite)
    _write(Path(routers_dir) / "oauth_router.py", _render("oauth_router.py.tmpl", ctx), overwrite)
    _write(Path(routers_dir) / "settings.py", _render("settings.py.tmpl", ctx), overwrite)
    _write(Path(routers_dir) / "include_routers.py", _render("include_routers.py.tmpl", ctx), overwrite)

# One-by-one scaffolders for simplicity
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

@app.command("scaffold-auth-settings")
def scaffold_auth_settings(
        dest_dir: Path = typer.Option(..., help="Directory to place auth settings.py"),
        overwrite: bool = typer.Option(False, help="Overwrite if exists"),
):
    _write(Path(dest_dir) / "settings.py", _render("settings.py.tmpl", {}), overwrite)

@app.command("scaffold-auth-users-router")
def scaffold_auth_users_router(
        dest_dir: Path = typer.Option(..., help="Directory to place users.py router"),
        session_dep_import: str = typer.Option(..., help='Module path to your SessionDep (e.g. "my_app.db.integration_fastapi")'),
        auth_prefix: str = typer.Option("/auth", help="Auth API prefix"),
        overwrite: bool = typer.Option(False, help="Overwrite if exists"),
):
    ctx = dict(session_dep_import=session_dep_import, auth_prefix=auth_prefix)
    _write(Path(dest_dir) / "users.py", _render("users.py.tmpl", ctx), overwrite)

@app.command("scaffold-auth-oauth-router")
def scaffold_auth_oauth_router(
        dest_dir: Path = typer.Option(..., help="Directory to place oauth_router.py"),
        session_dep_import: str = typer.Option(..., help='Module path to your SessionDep (e.g. "my_app.db.integration_fastapi")'),
        oauth_prefix: str = typer.Option("/oauth", help="OAuth API prefix"),
        post_login_redirect: str = typer.Option("/", help="Where to redirect with ?token=..."),
        overwrite: bool = typer.Option(False, help="Overwrite if exists"),
):
    ctx = dict(session_dep_import=session_dep_import, oauth_prefix=oauth_prefix, post_login_redirect=post_login_redirect)
    _write(Path(dest_dir) / "oauth_router.py", _render("oauth_router.py.tmpl", ctx), overwrite)

@app.command("scaffold-auth-include")
def scaffold_auth_include(
        dest_dir: Path = typer.Option(..., help="Directory to place include_routers.py"),
        auth_prefix: str = typer.Option("/auth", help="Auth API prefix"),
        overwrite: bool = typer.Option(False, help="Overwrite if exists"),
):
    ctx = dict(auth_prefix=auth_prefix)
    _write(Path(dest_dir) / "include_routers.py", _render("include_routers.py.tmpl", ctx), overwrite)

# Existing: scaffold a DB health router that performs SELECT 1 using your SessionDep
@app.command("scaffold-health")
def scaffold_health(
        routers_dir: Path = typer.Option(..., help="Where to place health router (health.py)"),
        session_dep_import: str = typer.Option(..., help='Module path to your SessionDep (e.g. "my_app.db.integration_fastapi")'),
        health_prefix: str = typer.Option("/health", help="Prefix for health router (module-level ROUTER_PREFIX)"),
        overwrite: bool = typer.Option(False, help="Overwrite file if it exists"),
):
    ctx = dict(
        session_dep_import=session_dep_import,
        health_prefix=health_prefix,
    )
    _write(Path(routers_dir) / "health.py", _render("health_router.py.tmpl", ctx), overwrite)

# Existing: scaffold a FastAPI DB integration helper that wires engine + session dependency
@app.command("scaffold-db-fastapi")
def scaffold_db_fastapi_integration(
        dest_dir: Path = typer.Option(..., help="Where to place the DB FastAPI integration module"),
        filename: str = typer.Option("integration_fastapi.py", help="Filename for the integration module"),
        dsn_env: str = typer.Option("DATABASE_URL", help="Env var name holding the DB URL (async driver)"),
        overwrite: bool = typer.Option(False, help="Overwrite file if it exists"),
):
    ctx = dict(
        dsn_env=dsn_env,
    )
    _write(Path(dest_dir) / filename, _render("db_fastapi_integration.py.tmpl", ctx), overwrite)

if __name__ == "__main__":
    app()