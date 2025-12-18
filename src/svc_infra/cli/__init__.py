from __future__ import annotations

import typer

from svc_infra.cli.cmds import (
    _HELP,
    jobs_app,
    register_alembic,
    register_db_ops,
    register_docs,
    register_dx,
    register_health,
    register_mongo,
    register_mongo_scaffold,
    register_obs,
    register_sdk,
    register_sql_export,
    register_sql_scaffold,
)
from svc_infra.cli.foundation.typer_bootstrap import pre_cli

app = typer.Typer(no_args_is_help=True, add_completion=False, help=_HELP)
pre_cli(app)

# --- db ops group ---
db_app = typer.Typer(no_args_is_help=True, add_completion=False, help="Database operations")
register_db_ops(db_app)
app.add_typer(db_app, name="db")

# --- sql group ---
sql_app = typer.Typer(no_args_is_help=True, add_completion=False, help="SQL commands")
register_alembic(sql_app)
register_sql_scaffold(sql_app)
register_sql_export(sql_app)
app.add_typer(sql_app, name="sql")

# --- mongo group ---
mongo_app = typer.Typer(no_args_is_help=True, add_completion=False, help="MongoDB commands")
register_mongo(mongo_app)
register_mongo_scaffold(mongo_app)
app.add_typer(mongo_app, name="mongo")

# --- health group ---
health_app = typer.Typer(no_args_is_help=True, add_completion=False, help="Health checks")
register_health(health_app)
app.add_typer(health_app, name="health")

# -- obs group ---
obs_app = typer.Typer(no_args_is_help=True, add_completion=False, help="Observability commands")
register_obs(obs_app)
app.add_typer(obs_app, name="obs")

# -- dx commands ---
register_dx(app)

# -- jobs commands ---
app.add_typer(jobs_app, name="jobs")

# -- sdk commands ---
register_sdk(app)

# -- docs commands ---
register_docs(app)


def main():
    app()


if __name__ == "__main__":
    main()
