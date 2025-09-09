from __future__ import annotations

import os, subprocess
from pathlib import Path
from urllib.parse import urlparse
from string import Template
import typer

def _pkg_file(*parts: str) -> str:
    import importlib.resources as pkg
    # returns text; use .read_bytes() for binary if needed
    return pkg.files("svc_infra.observability.grafana").joinpath(*parts).read_text(encoding="utf-8")

def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def up(
        metrics_url: str = typer.Option("http://host.docker.internal:8000/metrics"),
        grafana_port: int = 3000,
        prom_port: int = 9090,
):
    """Start Prometheus + Grafana in Docker to observe your app's metrics.
    Your app should expose Prometheus metrics at /metrics (or customize with --metrics-url)."""
    root = Path(".obs")
    (root / "provisioning" / "datasources").mkdir(parents=True, exist_ok=True)
    (root / "provisioning" / "dashboards").mkdir(parents=True, exist_ok=True)
    (root / "dashboards").mkdir(parents=True, exist_ok=True)

    # --- docker-compose.yml from template
    compose_tmpl = _pkg_file("templates", "docker-compose.yml.tmpl")
    _write_text(root / "docker-compose.yml", compose_tmpl)

    # --- provisioning (static)
    _write_text(root / "provisioning" / "datasources" / "datasource.yml",
                _pkg_file("templates", "provisioning", "datasource.yml"))
    _write_text(root / "provisioning" / "dashboards" / "dashboards.yml",
                _pkg_file("templates", "provisioning", "dashboards.yml"))

    # --- prometheus.yml from template (render metrics target/path)
    parsed = urlparse(metrics_url)
    target = parsed.netloc or "host.docker.internal:8000"
    mpath = parsed.path or "/metrics"
    prom_tmpl = Template(_pkg_file("templates", "prometheus.yml.tmpl")).substitute(
        metrics_path=mpath,
        target=target,
    )
    _write_text(root / "prometheus.yml", prom_tmpl)

    # --- dashboard json (copy packaged file)
    _write_text(root / "dashboards" / "fastapi_overview.json",
                _pkg_file("dashboards", "fastapi_overview.json"))

    # --- docker compose up
    env = os.environ.copy()
    env["PROM_PORT"] = str(prom_port)
    env["GRAFANA_PORT"] = str(grafana_port)
    subprocess.run(
        ["docker", "compose", "-f", str(root / "docker-compose.yml"), "up", "-d"],
        check=True,
        env=env,
    )
    typer.echo(f"Grafana:     http://localhost:{grafana_port}  (admin/admin)")
    typer.echo(f"Prometheus:  http://localhost:{prom_port}")
    typer.echo(f"Scraping:    {metrics_url}")

def down():
    """Stop Prometheus + Grafana."""
    root = Path(".obs")
    if not (root / "docker-compose.yml").exists():
        typer.echo("No .obs/docker-compose.yml found.")
        raise typer.Exit(code=1)
    subprocess.run(["docker", "compose", "-f", str(root / "docker-compose.yml"), "down"], check=False)
    typer.echo("Stopped Prometheus + Grafana.")

def register(app: typer.Typer) -> None:
    app.command("obs-up")(up)
    app.command("obs-down")(down)