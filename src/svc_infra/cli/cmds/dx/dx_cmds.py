from __future__ import annotations

import sys
from pathlib import Path

import typer

from svc_infra.dx.changelog import Commit, generate_release_section
from svc_infra.dx.checks import check_migrations_up_to_date, check_openapi_problem_schema

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command("openapi")
def cmd_openapi(path: str = typer.Argument(..., help="Path to OpenAPI JSON")):
    try:
        check_openapi_problem_schema(path=path)
    except Exception as e:  # noqa: BLE001
        typer.secho(f"OpenAPI check failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)
    typer.secho("OpenAPI checks passed", fg=typer.colors.GREEN)


@app.command("migrations")
def cmd_migrations(project_root: str = typer.Option(".", help="Project root")):
    try:
        check_migrations_up_to_date(project_root=project_root)
    except Exception as e:  # noqa: BLE001
        typer.secho(f"Migrations check failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)
    typer.secho("Migrations checks passed", fg=typer.colors.GREEN)


@app.command("changelog")
def cmd_changelog(
    version: str = typer.Argument(..., help="Version (e.g., 0.1.604)"),
    commits_file: str = typer.Option(None, help="Path to JSON lines of commits (sha,subject)"),
):
    """Generate a changelog section from commit messages.

    Expects Conventional Commits style for best grouping; falls back to Other.
    If commits_file is omitted, prints an example format.
    """
    import json
    import sys

    if not commits_file:
        typer.echo(
            '# Provide --commits-file with JSONL: {"sha": "<sha>", "subject": "feat: ..."}',
            err=True,
        )
        raise typer.Exit(2)
    rows = [
        json.loads(line) for line in Path(commits_file).read_text().splitlines() if line.strip()
    ]
    commits = [Commit(sha=r["sha"], subject=r["subject"]) for r in rows]
    out = generate_release_section(version=version, commits=commits)
    sys.stdout.write(out)


@app.command("ci")
def cmd_ci(
    run: bool = typer.Option(False, help="Execute the steps; default just prints a plan"),
    openapi: str | None = typer.Option(None, help="Path to OpenAPI JSON to lint"),
    project_root: str = typer.Option(".", help="Project root for migrations check"),
):
    """Print (or run) the CI steps locally to mirror the workflow."""
    steps: list[list[str]] = []
    # Lint, typecheck, tests
    steps.append(["flake8", "--select=E,F"])  # mirrors CI
    steps.append(["mypy", "src"])  # mirrors CI
    if openapi:
        steps.append([sys.executable, "-m", "svc_infra.cli", "dx", "openapi", openapi])
    steps.append(
        [sys.executable, "-m", "svc_infra.cli", "dx", "migrations", "--project-root", project_root]
    )
    steps.append(["pytest", "-q", "-W", "error"])  # mirrors CI

    if not run:
        typer.echo("CI dry-run plan:")
        for cmd in steps:
            typer.echo("  $ " + " ".join(cmd))
        return

    import subprocess

    for cmd in steps:
        typer.echo("Running: " + " ".join(cmd))
        res = subprocess.run(cmd)
        if res.returncode != 0:
            raise typer.Exit(res.returncode)
    typer.echo("All CI steps passed")


def main():  # pragma: no cover - CLI entrypoint
    app()


__all__ = ["main", "app"]
