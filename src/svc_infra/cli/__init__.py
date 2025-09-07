from __future__ import annotations

import typer

from svc_infra.cli.alembic_cmds import register as register_alembic
from svc_infra.cli.scaffold_cmds import register as register_scaffold

app = typer.Typer(no_args_is_help=True, add_completion=False)

# Attach all commands to the ONE app
register_alembic(app)
register_scaffold(app)

if __name__ == "__main__":
    app()