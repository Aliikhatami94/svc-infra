from __future__ import annotations
import typer

from svc_infra.db.core import app as _db_app
from svc_infra.auth.cli import app as _auth_app
from svc_infra.cli.ai.graph.run import run_cli as _agent
from svc_infra.cli.utils import _async_cmd

app = typer.Typer(
    name="svc-infra",
    help="Unified CLI for service infrastructure commands (auth, db, agent, etc).",
    no_args_is_help=True,
    add_completion=False
)
app.add_typer(_db_app, name="db", help="Database related commands")
app.add_typer(_auth_app, name="auth", help="Auth db setup related commands")
app.command("agent", hidden=True)(_async_cmd(_agent))


if __name__ == "__main__":
    app()