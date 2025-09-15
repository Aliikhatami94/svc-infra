from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

import typer

from svc_infra.obs.providers.uptrace import default_service_name, make_uptrace_env
from svc_infra.utils import render_template, write


def _exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _compose_path(root: Path) -> Path:
    return root / "observability" / "uptrace" / "compose.yml"


def cmd_init(
    project: Optional[str] = typer.Option(
        None, "--project", help="Logical service name (defaults to folder name)."
    ),
    mode: str = typer.Option("uptrace", help="OBS_MODE for your app (uptrace|both|grafana|off)"),
    endpoint: Optional[str] = typer.Option(
        None,
        "--endpoint",
        help="OTLP endpoint your app should send to (default: http://uptrace:4317)",
    ),
    protocol: str = typer.Option("grpc", help='OTLP protocol: "grpc" or "http/protobuf"'),
    dsn: Optional[str] = typer.Option(None, "--dsn", help="Uptrace DSN (optional)"),
    overwrite: bool = typer.Option(False, "--overwrite/--no-overwrite"),
):
    """
    Scaffold a minimal Uptrace stack + app envs (provider-agnostic).
    """
    env = make_uptrace_env(
        service_name=project or default_service_name(),
        dsn=dsn,
        endpoint=endpoint,
        protocol=protocol,
        mode=mode,
    )

    subs = {
        "service_name": env.service_name,
        "mode": env.mode,
        "otlp_endpoint": env.otlp_endpoint,
        "protocol": env.protocol,
        "dsn_line": (
            f"UPTRACE_DSN={env.dsn}" if env.dsn else "# UPTRACE_DSN=<copy-from-Uptrace-project>"
        ),
    }

    root = Path.cwd()
    comp = _compose_path(root)

    compose_txt = render_template(
        "svc_infra.obs.providers.uptrace.templates", "compose.yml.tmpl", subs
    )
    readme_txt = render_template(
        "svc_infra.obs.providers.uptrace.templates", "README.md.tmpl", subs
    )
    env_txt = render_template("svc_infra.obs.providers.uptrace.templates", "env.uptrace.tmpl", subs)

    write(comp, compose_txt, overwrite=overwrite)
    write(root / "observability" / "uptrace" / "README.md", readme_txt, overwrite=overwrite)
    write(root / ".env.uptrace", env_txt, overwrite=overwrite)

    typer.secho(f"✓ Wrote {comp}", fg=typer.colors.GREEN)
    typer.secho("✓ Wrote observability/uptrace/README.md", fg=typer.colors.GREEN)
    typer.secho("✓ Wrote .env.uptrace (app envs)", fg=typer.colors.GREEN)

    typer.echo("\nApp envs to set on your platform:")
    for line in env_txt.strip().splitlines():
        typer.echo(line)


def cmd_deploy(
    compose_file: Optional[Path] = typer.Option(
        None,
        "--compose-file",
        help="Custom compose file path (default: observability/uptrace/compose.yml)",
    ),
    detach: bool = typer.Option(True, "--detach/--no-detach", help="Compose with -d"),
):
    """
    Best-effort deploy locally with docker compose.
    Prints exact command if docker is unavailable.
    """
    comp = compose_file or _compose_path(Path.cwd())
    if not comp.exists():
        typer.secho(f"Compose file not found: {comp}", fg=typer.colors.RED)
        raise typer.Exit(code=2)

    if _exists("docker"):
        cmd = ["docker", "compose", "-f", str(comp), "up"]
        if detach:
            cmd.append("-d")
        typer.echo("Running: " + " ".join(cmd))
        try:
            subprocess.run(cmd, check=True)
            typer.secho(
                "✓ Uptrace is up (local). UI: http://localhost:14318", fg=typer.colors.GREEN
            )
        except subprocess.CalledProcessError as e:
            typer.secho(f"Compose failed: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=e.returncode)
    else:
        typer.echo(
            "\nDocker not available. To deploy on a server/VM, run this on the host:\n"
            f"  docker compose -f {comp} up -d\n\n"
            "Then set the app envs from .env.uptrace on your platform."
        )


def register(app: typer.Typer) -> None:
    app.command("uptrace-init")(cmd_init)
    app.command("uptrace-deploy")(cmd_deploy)
