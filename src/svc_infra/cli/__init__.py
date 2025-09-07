from __future__ import annotations

import typer

from svc_infra.cli.alembic_cmds import register as register_alembic
from svc_infra.cli.scaffold_cmds import register as register_scaffold
from svc_infra.cli.app_cmds import register as register_app

HELP = """\
svc-infra — service infrastructure CLI

How to run (pick what fits your workflow):

  1) Installed console script (recommended)
     $ svc-infra <command> [options]
     e.g.:
     $ svc-infra setup-and-migrate

  2) Python module form (from a checkout / local dev)
     $ python -m svc_infra <command> [options]
     e.g.:
     $ python -m svc_infra setup-and-migrate

  3) Poetry shim (inside a Poetry project)
     $ poetry run svc-infra <command> [options]
     e.g.:
     $ poetry run svc-infra setup-and-migrate

Notes:
* Make sure you’re in the right virtual environment (or use `pipx`).
* You can set DATABASE_URL in your environment, or pass --database-url to commands.
* You can point `--project-root` at your Alembic root; if omitted we auto-detect.
"""

app = typer.Typer(no_args_is_help=True, add_completion=False, help=HELP)

# Attach all commands to the ONE app
register_app(app)
register_alembic(app)
register_scaffold(app)

if __name__ == "__main__":
    app()