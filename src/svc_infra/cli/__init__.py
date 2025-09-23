from __future__ import annotations

import typer

from svc_infra.cli.cmds import (
    _HELP,
    register_alembic,
    register_mongo,
    register_mongo_scaffold,
    register_obs,
    register_sql_scaffold,
)
from svc_infra.cli.foundation.typer_bootstrap import pre_cli

app = typer.Typer(no_args_is_help=True, add_completion=False, help=_HELP)
pre_cli(app)

# --- sql commands ---
register_alembic(app)
register_sql_scaffold(app)

# --- nosql commands ---
register_mongo(app)
register_mongo_scaffold(app)

# -- observability commands ---
register_obs(app)


def main():
    app()


if __name__ == "__main__":
    main()
