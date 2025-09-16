# svc_infra/obs/cli.py
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import typer

from svc_infra.obs.cloud_dash import push_dashboards_from_pkg  # Step 2
from svc_infra.utils import render_template, write

app = typer.Typer(help="Observability bootstrap (local or cloud)")


def _run(cmd: list[str]):
    subprocess.run(cmd, check=True)


def _emit_local_stack(root: Path, metrics_url: str):
    # Templates you already ship under providers/grafana/templates
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
    p = urlparse(metrics_url)
    write(
        root / "agent.yaml",
        f"""metrics:
  wal_directory: /tmp/agent/wal
  global: {{ scrape_interval: 5s }}
  configs:
    - name: svc-infra
      scrape_configs:
        - job_name: svc-infra
          scheme: {p.scheme or "http"}
          metrics_path: {p.path or "/metrics"}
          static_configs: [{{ targets: ["{p.netloc or "host.docker.internal:8000"}"] }}]
      remote_write:
        - url: ${{GRAFANA_CLOUD_PROM_URL}}
          basic_auth:
            username: ${{GRAFANA_CLOUD_USERNAME}}
            password: ${{GRAFANA_CLOUD_TOKEN}}
""",
    )
    write(
        root / "docker-compose.cloud.yml",
        """version: "3.9"
services:
  agent:
    image: grafana/agent:latest
    command: ["/bin/grafana-agent","--config.file=/etc/agent/agent.yaml","--config.expand-env"]
    environment:
      - GRAFANA_CLOUD_PROM_URL
      - GRAFANA_CLOUD_USERNAME
      - GRAFANA_CLOUD_TOKEN
    volumes:
      - ./agent.yaml:/etc/agent/agent.yaml:ro
""",
    )


def up():
    """
    Auto-detect mode:
      - If GRAFANA_CLOUD_URL & GRAFANA_CLOUD_TOKEN → Cloud mode (push dashboards).
        If remote_write creds present → also run local Agent to push metrics.
      - Else → Local mode (Grafana + Prometheus).
    """
    root = Path(".obs")
    root.mkdir(exist_ok=True)
    metrics_url = os.getenv("SVC_INFRA_METRICS_URL", "http://host.docker.internal:8000/metrics")

    cloud_url = os.getenv("GRAFANA_CLOUD_URL", "").strip()
    cloud_token = os.getenv("GRAFANA_CLOUD_TOKEN", "").strip()

    if cloud_url and cloud_token:
        folder = os.getenv("SVC_INFRA_CLOUD_FOLDER", "Service Infrastructure")
        push_dashboards_from_pkg(cloud_url, cloud_token, folder)
        typer.echo(f"[cloud] dashboards synced to '{folder}'")

        if all(
            os.getenv(k)
            for k in ("GRAFANA_CLOUD_PROM_URL", "GRAFANA_CLOUD_USERNAME", "GRAFANA_CLOUD_TOKEN")
        ):
            _emit_local_agent(root, metrics_url)
            _run(["docker", "compose", "-f", str(root / "docker-compose.cloud.yml"), "up", "-d"])
            typer.echo("[cloud] local Grafana Agent started (pushing metrics to Cloud)")
        else:
            typer.echo("[cloud] expecting Agent sidecar in deployment to push metrics")
        return

    # Local mode
    _emit_local_stack(root, metrics_url)
    _run(["docker", "compose", "-f", str(root / "docker-compose.yml"), "up", "-d"])
    typer.echo("Local Grafana → http://localhost:3000  (admin/admin)")
    typer.echo("Local Prometheus → http://localhost:9090")


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
    """
    Write a ready-to-deploy Grafana Agent sidecar template to ./obs-sidecar/<target>/
    """
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
    app.command("obs-up")(up)
    app.command("obs-down")(down)
    app.command("obs-scaffold")(scaffold)
