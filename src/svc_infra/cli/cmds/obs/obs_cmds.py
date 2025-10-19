from __future__ import annotations

import os
import socket
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import typer

# --- NEW: load .env automatically (best-effort) ---
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    load_dotenv = None

from svc_infra.obs.cloud_dash import push_dashboards_from_pkg
from svc_infra.utils import render_template, write


def _run(cmd: list[str], *, env: dict | None = None):
    subprocess.run(cmd, check=True, env=env)


def _emit_local_stack(root: Path, metrics_url: str):
    write(
        root / "docker-compose.yml",
        render_template("svc_infra.obs.providers.grafana.templates", "docker-compose.yml.tmpl", {}),
    )
    p = urlparse(metrics_url)
    prom_yml = render_template(
        "svc_infra.obs.providers.grafana.templates",
        "prometheus.yml.tmpl",
        {
            "metrics_path": (p.path or "/metrics"),
            "target": (p.netloc or "host.docker.internal:8000"),
        },
    )
    write(root / "prometheus.yml", prom_yml)

    # provisioning + dashboards
    root.joinpath("provisioning/datasources").mkdir(parents=True, exist_ok=True)
    root.joinpath("provisioning/dashboards").mkdir(parents=True, exist_ok=True)
    root.joinpath("dashboards").mkdir(parents=True, exist_ok=True)

    from importlib.resources import files

    tpl = files("svc_infra.obs.providers.grafana")
    write(
        root / "provisioning/datasources/datasource.yml",
        tpl.joinpath("templates/provisioning/datasource.yml").read_text(),
    )
    write(
        root / "provisioning/dashboards/dashboards.yml",
        tpl.joinpath("templates/provisioning/dashboards.yml").read_text(),
    )
    for d in tpl.joinpath("dashboards").iterdir():
        if d.name.endswith(".json"):
            write(root / "dashboards" / d.name, d.read_text())


def _emit_local_agent(root: Path, metrics_url: str):
    """
    Render the agent + compose from the dedicated compose_cloud templates.
    """
    # Write agent.yaml from template (no hardcoded strings)
    agent_text = render_template(
        tmpl_dir="svc_infra.obs.providers.compose_cloud.templates",
        name="agent.yaml.tmpl",
        subs={},  # values come from env at runtime via ${...}
    )
    write(root / "agent.yaml", agent_text, overwrite=True)

    compose_text = render_template(
        tmpl_dir="svc_infra.obs.providers.compose_cloud.templates",
        name="docker-compose.cloud.yml.tmpl",
        subs={},  # all env-driven
    )
    write(root / "docker-compose.cloud.yml", compose_text, overwrite=True)


def _port_free(p: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.connect_ex(("127.0.0.1", p)) != 0


def _choose_port(preferred: int, limit: int = 15) -> int:
    p = preferred
    for _ in range(limit):
        if _port_free(p):
            return p
        p += 1
    return preferred


def up():
    """
    Auto-detect mode:
      - If GRAFANA_CLOUD_URL & GRAFANA_CLOUD_TOKEN → Cloud mode (push dashboards).
        If remote_write creds present → also run local Agent to push metrics.
      - Else → Local mode (Grafana + Prometheus).
    """
    # NEW: load .env once, best-effort, without crashing if package missing
    if load_dotenv:
        try:
            load_dotenv(dotenv_path=Path(".env"), override=False)
        except Exception:
            pass

    root = Path(".obs")
    root.mkdir(exist_ok=True)
    metrics_url = os.getenv("SVC_INFRA_METRICS_URL", "http://host.docker.internal:8000/metrics")

    cloud_url = os.getenv("GRAFANA_CLOUD_URL", "").strip()
    cloud_token = os.getenv("GRAFANA_CLOUD_TOKEN", "").strip()

    if cloud_url and cloud_token:
        folder = os.getenv("SVC_INFRA_CLOUD_FOLDER", "Service Infrastructure")
        push_dashboards_from_pkg(cloud_url, cloud_token, folder)
        typer.echo(f"[cloud] dashboards synced to '{folder}'")

        # NOTE: look for RW token (not the Grafana API token)
        if all(
            os.getenv(k)
            for k in (
                "GRAFANA_CLOUD_PROM_URL",
                "GRAFANA_CLOUD_PROM_USERNAME",
                "GRAFANA_CLOUD_RW_TOKEN",
            )
        ):
            _emit_local_agent(root, metrics_url)
            _run(
                ["docker", "compose", "-f", str(root / "docker-compose.cloud.yml"), "up", "-d"],
                env=os.environ.copy(),
            )
            typer.echo("[cloud] local Grafana Agent started (pushing metrics to Cloud)")
        else:
            typer.echo("[cloud] expecting Agent sidecar in deployment to push metrics")
        return

    # Local mode
    local_graf = _choose_port(int(os.getenv("GRAFANA_PORT", "3000")))
    local_prom = _choose_port(int(os.getenv("PROM_PORT", "9090")))
    env = os.environ.copy()
    env["GRAFANA_PORT"] = str(local_graf)
    env["PROM_PORT"] = str(local_prom)
    _emit_local_stack(root, metrics_url)
    _run(["docker", "compose", "-f", str(root / "docker-compose.yml"), "up", "-d"], env=env)
    typer.echo(f"Local Grafana → http://localhost:{local_graf}  (admin/admin)")
    typer.echo(f"Local Prometheus → http://localhost:{local_prom}")


def down():
    root = Path(".obs")
    if (root / "docker-compose.yml").exists():
        subprocess.run(
            ["docker", "compose", "-f", str(root / "docker-compose.yml"), "down"], check=False
        )
    if (root / "docker-compose.cloud.yml").exists():
        subprocess.run(
            ["docker", "compose", "-f", str(root / "docker-compose.cloud.yml"), "down"], check=False
        )
    typer.echo("Stopped local obs services.")


def scaffold(target: str = typer.Option(..., help="compose|railway|k8s|fly")):
    from importlib.resources import files

    out = Path("obs-sidecar") / target
    out.mkdir(parents=True, exist_ok=True)

    base = files("svc_infra.obs.templates.sidecars").joinpath(target)
    for p in base.rglob("*"):
        if p.is_file():
            rel = p.relative_to(base)
            dst = out / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

    typer.echo(f"Wrote sidecar template to {out}. Fill envs and deploy.")


def register(app: typer.Typer) -> None:
    # Attach to 'obs' group app
    app.command("up")(up)
    app.command("down")(down)
    app.command("scaffold")(scaffold)
