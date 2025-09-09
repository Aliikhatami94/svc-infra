import os, subprocess
from pathlib import Path
import typer
from urllib.parse import urlparse

def up(
        metrics_url: str = typer.Option("http://host.docker.internal:8000/metrics"),
        grafana_port: int = 3000,
        prom_port: int = 9090,
):
    root = Path(".obs")
    (root / "provisioning" / "datasources").mkdir(parents=True, exist_ok=True)
    (root / "provisioning" / "dashboards").mkdir(parents=True, exist_ok=True)
    (root / "dashboards").mkdir(parents=True, exist_ok=True)

    # write compose, datasources, dashboards.yml (from embedded strings above)

    # write prometheus.yml from metrics_url
    parsed = urlparse(metrics_url)
    hostport = parsed.netloc
    mpath = parsed.path or "/metrics"
    prom = f"""global:
  scrape_interval: 5s
  evaluation_interval: 5s
scrape_configs:
  - job_name: "fastapi"
    metrics_path: "{mpath}"
    static_configs:
      - targets: ["{hostport}"]
"""
    (root / "prometheus.yml").write_text(prom)

    # copy packaged dashboard file
    import importlib.resources as pkg
    dash = pkg.files("svc_infra.observability.grafana.dashboards").joinpath("fastapi_overview.json").read_text()
    (root / "dashboards" / "fastapi_overview.json").write_text(dash)

    # write docker-compose.yml from template
    compose = """<… content from above …>"""
    (root / "docker-compose.yml").write_text(compose)

    env = os.environ.copy()
    env["PROM_PORT"] = str(prom_port)
    env["GRAFANA_PORT"] = str(grafana_port)
    subprocess.run(["docker", "compose", "-f", str(root / "docker-compose.yml"), "up", "-d"], check=True, env=env)
    typer.echo(f"Grafana: http://localhost:{grafana_port}  (admin/admin)")
    typer.echo(f"Prometheus: http://localhost:{prom_port}")
    typer.echo(f"Scraping: {metrics_url}")

def down():
    root = Path(".obs")
    if not (root / "docker-compose.yml").exists():
        typer.echo("No .obs/docker-compose.yml found.")
        raise typer.Exit(code=1)
    subprocess.run(["docker", "compose", "-f", str(root / "docker-compose.yml"), "down"], check=False)
    typer.echo("Stopped Prometheus + Grafana.")

def register(app: typer.Typer) -> None:
    app.command("obs-up")(up)
    app.command("obs-down")(down)