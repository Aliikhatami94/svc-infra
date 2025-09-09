from __future__ import annotations

import typer

from svc_infra.cli.foundation.typer_bootstrap import pre_cli
from svc_infra.cli.cmds import (
    _HELP, register_alembic, register_scaffold, register_obs
)

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help=_HELP
)
pre_cli(app)
register_alembic(app)
register_scaffold(app)
register_obs(app)

def main():
    app()

if __name__ == "__main__":
    main()