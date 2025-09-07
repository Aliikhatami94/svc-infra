from __future__ import annotations

import typer

from svc_infra.cli.alembic_cmds import register as register_alembic
from svc_infra.cli.scaffold_cmds import register as register_scaffold
from svc_infra.cli.app_cmds import register as register_app, HELP
from svc_infra.cli._bootstrap import pre as _pre

app = typer.Typer(no_args_is_help=True, add_completion=False, help=HELP)

# Attach all commands to the ONE app
_pre(app)
register_app(app)
register_alembic(app)
register_scaffold(app)

if __name__ == "__main__":
    app()