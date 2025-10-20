_HELP = """\
# svc-infra — service infrastructure CLI

## Allows for common infra tasks:
  - Alembic DB migrations (setup, create, migrate, stamp, etc)
  - Scaffold starter models/schemas for auth or entities
  - Setup OpenTelemetry observability (tracing/metrics/logs)

How to run (pick what fits your workflow):

  1) Installed console script (recommended)
     $ svc-infra <command> [options]
     e.g.:
     $ svc-infra setup-and-migrate

  2) Poetry shim (inside a Poetry project)
     $ poetry run svc-infra <command> [options]
     e.g.:
     $ poetry run svc-infra setup-and-migrate

Notes:
* Make sure you’re in the right virtual environment (or use `pipx`).
* You can point `--project-root` at your Alembic root; if omitted we auto-detect.

Learn more:
* Explore available topics: `svc-infra docs --help`
* Show a topic directly: `svc-infra docs <topic>` or `svc-infra docs show <topic>`
"""
