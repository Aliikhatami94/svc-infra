from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import tarfile
import time
import webbrowser
import zipfile
from pathlib import Path
from string import Template
from urllib.parse import urlparse
from urllib.request import urlretrieve

import typer

PKG_TPL_ROOT = "svc_infra.observability.grafana"

# ------------------------- small utils -------------------------


def _pkg_file(*parts: str) -> str:
    import importlib.resources as pkg

    return pkg.files(PKG_TPL_ROOT).joinpath(*parts).read_text(encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _patch_dashboard_datasource(dash_path: Path, prom_uid: str = "prom") -> None:
    """
    Ensure the dashboard uses the Prometheus datasource with a stable UID ('prom')
    and that template variables have allValue='.*' so 'All' matches all series.
    """
    try:
        data = json.loads(dash_path.read_text(encoding="utf-8"))
    except Exception:
        return

    ds_obj = {"type": "prometheus", "uid": prom_uid}

    for p in data.get("panels", []):
        if p.get("type") == "row" and "panels" in p:
            for sp in p["panels"]:
                sp["datasource"] = ds_obj
        p["datasource"] = ds_obj
        for t in p.get("targets", []):
            t["datasource"] = ds_obj

    templ = data.get("templating", {}).get("list", [])
    for v in templ:
        v["datasource"] = ds_obj
        if v.get("includeAll"):
            v["allValue"] = ".*"
        v.setdefault("refresh", 2)

    data["datasource"] = ds_obj
    dash_path.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":"), indent=2),
        encoding="utf-8",
    )


def _exists(cmd: list[str]) -> bool:
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return True
    except Exception:
        return False


def _docker_running() -> bool:
    try:
        out = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return out.returncode == 0
    except Exception:
        return False


def _try_autostart_docker() -> None:
    if _docker_running():
        return
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.Popen(["open", "-g", "-a", "Docker"])
            for _ in range(30):
                if _docker_running():
                    return
                time.sleep(1)
        elif system == "Windows":
            exe = r"C:\Program Files\Docker\Docker\Docker Desktop.exe"
            if Path(exe).exists():
                subprocess.Popen([exe], shell=False)
                for _ in range(30):
                    if _docker_running():
                        return
                    time.sleep(1)
        else:
            # Linux: don't sudo; just bail if not running
            pass
    except Exception:
        pass


# --------------------- native fallback bits --------------------

NATIVE_GRAFANA_URLS = {
    (
        "Darwin",
        "arm64",
    ): "https://dl.grafana.com/oss/release/grafana-11.1.4.darwin-arm64.tar.gz",
    (
        "Darwin",
        "x86_64",
    ): "https://dl.grafana.com/oss/release/grafana-11.1.4.darwin-amd64.tar.gz",
    (
        "Linux",
        "x86_64",
    ): "https://dl.grafana.com/oss/release/grafana-11.1.4.linux-amd64.tar.gz",
}
NATIVE_PROM_URLS = {
    (
        "Darwin",
        "arm64",
    ): "https://github.com/prometheus/prometheus/releases/download/v2.54.1/prometheus-2.54.1.darwin-arm64.tar.gz",
    (
        "Darwin",
        "x86_64",
    ): "https://github.com/prometheus/prometheus/releases/download/v2.54.1/prometheus-2.54.1.darwin-amd64.tar.gz",
    (
        "Linux",
        "x86_64",
    ): "https://github.com/prometheus/prometheus/releases/download/v2.54.1/prometheus-2.54.1.linux-amd64.tar.gz",
}


def _detect_arch() -> tuple[str, str]:
    return platform.system(), platform.machine()


def _download_and_unpack(url: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = dest_dir / url.split("/")[-1]
    if not filename.exists():
        typer.echo(f"Downloading {url} …")
        urlretrieve(url, filename)  # nosec
    if str(filename).endswith((".tar.gz", ".tgz")):
        with tarfile.open(filename, "r:gz") as tf:
            tf.extractall(dest_dir)  # nosec
            top = sorted(set(p.parts[0] for p in map(Path, tf.getnames()) if "/" in p))[0]
            return dest_dir / top
    if str(filename).endswith(".zip"):
        with zipfile.ZipFile(filename) as z:
            z.extractall(dest_dir)
            top = sorted(set(Path(n).parts[0] for n in z.namelist() if "/" in n))[0]
            return dest_dir / top
    raise RuntimeError(f"Unsupported archive: {filename.name}")


def _native_up(root: Path, grafana_port: int, prom_port: int) -> None:
    sys_os, sys_arch = _detect_arch()
    g_url = NATIVE_GRAFANA_URLS.get((sys_os, sys_arch))
    p_url = NATIVE_PROM_URLS.get((sys_os, sys_arch))
    if not g_url or not p_url:
        raise typer.BadParameter(
            f"Native backend not supported on {sys_os}/{sys_arch}. "
            "Install & run Docker or contribute URLs for your platform."
        )

    bin_dir = root / "bin"
    g_dir = _download_and_unpack(g_url, bin_dir)
    p_dir = _download_and_unpack(p_url, bin_dir)

    prom_cmd = [
        str(p_dir / "prometheus"),
        f"--config.file={root / 'prometheus.yml'}",
        f"--web.listen-address=:{prom_port}",
        f"--storage.tsdb.path={root / 'prom-data'}",
    ]
    graf_cmd = [
        str(g_dir / "bin" / "grafana-server"),
        f"--homepath={g_dir}",
        f"--config={root / 'grafana.ini'}",
    ]

    _write_text(
        root / "grafana.ini",
        f"""
[security]
admin_user = admin
admin_password = admin

[paths]
provisioning = {root / 'provisioning'}
data = {root / 'graf-data'}

[server]
http_port = {grafana_port}
http_addr =
""".strip(),
    )

    (root / "graf-data").mkdir(parents=True, exist_ok=True)
    (root / "prom-data").mkdir(parents=True, exist_ok=True)

    promp = subprocess.Popen(prom_cmd, cwd=p_dir)  # nosec
    grafp = subprocess.Popen(graf_cmd, cwd=g_dir)  # nosec

    _write_text(root / "prometheus.pid", str(promp.pid))
    _write_text(root / "grafana.pid", str(grafp.pid))


def _native_down(root: Path) -> None:
    for name in ("prometheus.pid", "grafana.pid"):
        pid_file = root / name
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, 15)  # SIGTERM
            except Exception:
                pass
            try:
                pid_file.unlink()
            except Exception:
                pass


# -------------------- shared file emission --------------------

_DASH_FILES = [
    ("00_overview.json", "dashboards", "00_overview.json"),
    ("10_http.json", "dashboards", "10_http.json"),
    ("20_db.json", "dashboards", "20_db.json"),
    ("30_runtime.json", "dashboards", "30_runtime.json"),
    ("40_clients.json", "dashboards", "40_clients.json"),
]


def _emit_common_files(
    root: Path, metrics_url: str, remote_write: dict[str, str] | None = None
) -> None:
    (root / "provisioning" / "datasources").mkdir(parents=True, exist_ok=True)
    (root / "provisioning" / "dashboards").mkdir(parents=True, exist_ok=True)
    (root / "dashboards").mkdir(parents=True, exist_ok=True)

    # docker-compose.yml (for docker backend)
    compose_tmpl = _pkg_file("templates", "docker-compose.yml.tmpl")
    _write_text(root / "docker-compose.yml", compose_tmpl)

    # provisioning (static): single folder "Service Infrastructure"
    _write_text(
        root / "provisioning" / "datasources" / "datasource.yml",
        _pkg_file("templates", "provisioning", "datasource.yml"),
    )
    # dashboards provider — points to /var/lib/grafana/dashboards
    _write_text(
        root / "provisioning" / "dashboards" / "dashboards.yml",
        _pkg_file("templates", "provisioning", "dashboards.yml"),
    )

    # prometheus.yml (render)
    parsed = urlparse(metrics_url)
    target = parsed.netloc or "host.docker.internal:8000"
    mpath = parsed.path or "/metrics"
    prom_tmpl = Template(_pkg_file("templates", "prometheus.yml.tmpl")).substitute(
        metrics_path=mpath,
        target=target,
    )

    # optional remote_write for Grafana Cloud / Thanos
    if remote_write and remote_write.get("url"):
        # Append a simple remote_write block
        prom_tmpl += '\nremote_write:\n  - url: "{url}"\n'.format(url=remote_write["url"])
        if remote_write.get("user") or remote_write.get("password"):
            prom_tmpl += "    basic_auth:\n"
            if remote_write.get("user"):
                prom_tmpl += f"      username: \"{remote_write['user']}\"\n"
            if remote_write.get("password"):
                prom_tmpl += f"      password: \"{remote_write['password']}\"\n"

    _write_text(root / "prometheus.yml", prom_tmpl)

    # dashboards (packaged JSONs)
    for dst_name, pkg_dir, pkg_name in _DASH_FILES:
        out_path = root / "dashboards" / dst_name
        _write_text(out_path, _pkg_file(pkg_dir, pkg_name))
        # NEW: bind datasource & fix variable All handling
        _patch_dashboard_datasource(out_path, prom_uid="prom")


def _port_free(port: int) -> bool:
    import socket as _s

    with _s.socket(_s.AF_INET, _s.SOCK_STREAM) as s:
        s.setsockopt(_s.SOL_SOCKET, _s.SO_REUSEADDR, 1)
        return s.connect_ex(("127.0.0.1", port)) != 0


def _choose_port(preferred: int, limit: int = 10) -> int:
    p = preferred
    for _ in range(limit):
        if _port_free(p):
            return p
        p += 1
    return preferred


def _docker_compose_up(
    compose_file: Path, env: dict, grafana_port: int, prom_port: int
) -> tuple[bool, int, int]:
    """
    Try to bring up compose. If ports are busy, try next ports a few times.
    Returns (ok, grafana_port, prom_port).
    """
    attempts = 5
    gp, pp = grafana_port, prom_port
    for _ in range(attempts):
        env["PROM_PORT"] = str(pp)
        env["GRAFANA_PORT"] = str(gp)
        try:
            subprocess.run(
                ["docker", "compose", "-f", str(compose_file), "up", "-d"],
                check=True,
                env=env,
            )
            return True, gp, pp
        except subprocess.CalledProcessError:
            # bump ports and retry
            gp += 1
            pp += 1
    return False, grafana_port, prom_port


# ---------------------- main commands ------------------------


def up(
    metrics_url: str = typer.Option(
        "http://host.docker.internal:8000/metrics",
        help="Prometheus scrape URL (your app).",
    ),
    grafana_port: int = typer.Option(3000, help="Grafana port to expose."),
    prom_port: int = typer.Option(9090, help="Prometheus port to expose."),
    backend: str = typer.Option("auto", help="auto|docker|native"),
    emit_only: bool = typer.Option(
        False, help="Just write files under .obs/ (for dev/uat/prod deployment)."
    ),
    open_browser: bool = typer.Option(True, help="Open Grafana in your browser after start."),
    remote_write_url: str = typer.Option(
        "", help="Prom remote_write URL (Grafana Cloud/Thanos/etc)"
    ),
    remote_write_user: str = typer.Option(
        "", help="Basic auth username (Grafana Cloud Metrics instance ID)"
    ),
    remote_write_password: str = typer.Option("", help="API key/password"),
):
    """
    Start Prometheus + Grafana to observe your app's metrics.
    Works with Docker (preferred) or a native fallback (no Docker).
    """
    root = Path(".obs")
    remote_write = (
        {
            "url": remote_write_url.strip(),
            "user": remote_write_user.strip(),
            "password": remote_write_password.strip(),
        }
        if remote_write_url.strip()
        else None
    )

    _emit_common_files(root, metrics_url, remote_write=remote_write)

    grafana_port = _choose_port(grafana_port)
    prom_port = _choose_port(prom_port)

    if emit_only:
        typer.echo("Wrote .obs/ files (emit-only). Hand off to your deployment tooling.")
        return

    chosen = backend
    if backend == "auto":
        _try_autostart_docker()
        chosen = "docker" if shutil.which("docker") and _docker_running() else "native"

    if chosen == "docker":
        if not shutil.which("docker"):
            typer.echo("Docker CLI not found. Falling back to native backend…")
            chosen = "native"
        elif not _docker_running():
            typer.echo("Docker daemon not running. Falling back to native backend…")
            chosen = "native"

    if chosen == "docker":
        env = os.environ.copy()
        ok, g_used, p_used = _docker_compose_up(
            root / "docker-compose.yml", env, grafana_port, prom_port
        )
        if not ok:
            raise typer.Exit(code=1)
        grafana_port, prom_port = g_used, p_used
        typer.echo(f"[docker] Grafana:    http://localhost:{grafana_port}  (admin/admin)")
        typer.echo(f"[docker] Prometheus: http://localhost:{prom_port}")
    elif chosen == "native":
        _native_up(root, grafana_port, prom_port)
        typer.echo(f"[native] Grafana:    http://localhost:{grafana_port}  (admin/admin)")
        typer.echo(f"[native] Prometheus: http://localhost:{prom_port}")
    else:
        raise typer.BadParameter("backend must be auto|docker|native")

    typer.echo(f"Scraping:   {metrics_url}")
    if open_browser:
        try:
            webbrowser.open_new_tab(f"http://localhost:{grafana_port}")
        except Exception:
            pass


def down():
    """Stop Prometheus + Grafana (docker or native)."""
    root = Path(".obs")
    if (root / "docker-compose.yml").exists() and shutil.which("docker"):
        subprocess.run(
            ["docker", "compose", "-f", str(root / "docker-compose.yml"), "down"],
            check=False,
        )
    _native_down(root)
    typer.echo("Stopped Prometheus + Grafana.")


def status():
    """Basic status health hints."""
    root = Path(".obs")
    dkr = "up" if _docker_running() else "down"
    typer.echo(f"Docker: {dkr}")
    if (root / "prometheus.pid").exists() or (root / "grafana.pid").exists():
        typer.echo("Native: processes appear to be running (pid files present).")
    if (root / "docker-compose.yml").exists():
        typer.echo("Compose: .obs/docker-compose.yml present.")
    else:
        typer.echo("Compose: not initialized (run obs-up).")


def open_ui(grafana_port: int = 3000):
    """Open Grafana UI."""
    webbrowser.open_new_tab(f"http://localhost:{grafana_port}")


def register(app_: typer.Typer) -> None:
    app_.command("obs-up")(up)
    app_.command("obs-down")(down)
    app_.command("obs-status")(status)
    app_.command("obs-open")(open_ui)
