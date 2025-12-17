from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.acceptance


def _py(
    cmd: list[str], env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        [sys.executable, "-m", "svc_infra.cli", *cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=merged,
        check=True,
        text=True,
    )


def test_a1001_cli_migrations_and_seed(tmp_path: Path):
    # Use an ephemeral SQLite db under tmp_path
    db_url = f"sqlite+aiosqlite:///{tmp_path}/a10.db"
    env = {"SQL_URL": db_url, "PROJECT_ROOT": str(tmp_path)}

    # Copy User model to tmp_path so it's available for alembic
    import shutil

    models_source = Path(__file__).parent / "models.py"
    shutil.copy(models_source, tmp_path / "models.py")

    # End-to-end setup and migrate should succeed
    out1 = _py(
        [
            "sql",
            "setup-and-migrate",
            "--overwrite-scaffold",
            "--create-followup-revision",
        ],
        env=env,
    )
    assert "setup_and_migrate" in out1.stdout

    # Patch env.py to import User model before security models
    env_py_path = tmp_path / "migrations" / "env.py"
    env_py_content = env_py_path.read_text()
    lines = env_py_content.splitlines()
    # Insert import after line 2 (after "from __future__ import annotations")
    lines.insert(
        2,
        f'import sys; sys.path.insert(0, "{tmp_path}"); import models  # Import User model',
    )
    env_py_path.write_text("\n".join(lines))

    # Regenerate migrations with User model
    versions_dir = tmp_path / "migrations" / "versions"
    for ver_file in versions_dir.glob("*.py"):
        ver_file.unlink()

    # Generate new migration with User model
    _py(["sql", "revision", "--autogenerate", "-m", "initial_with_user"], env=env)
    _py(["sql", "upgrade", "head"], env=env)

    # Current should exit 0
    out2 = _py(["sql", "current"], env=env)
    assert "project_root" in out2.stdout or out2.stdout.strip() == ""

    # Downgrade one and upgrade back to head
    _py(["sql", "downgrade", "-1"], env=env)
    _py(["sql", "upgrade", "head"], env=env)

    # Seed callable should resolve and exit 0
    _py(["sql", "seed", "tests.acceptance._seed:acceptance_seed"], env=env)


def test_a1002_jobs_runner_consumes_task(tmp_path: Path):
    # Configure the jobs schedule via env JSON to run our sentinel writer
    sentinel = tmp_path / "jobs.ok"
    schedule = [
        {
            "name": "sentinel",
            "interval_seconds": 0,  # immediate
            "target": "tests.acceptance._seed:write_sentinel",
        }
    ]
    env = {
        "JOBS_SCHEDULE_JSON": json.dumps(schedule),
        "JOBS_SENTINEL": str(sentinel),
        # keep in-memory driver
        "JOBS_DRIVER": "memory",
        "PROJECT_ROOT": str(tmp_path),
    }
    # Run a tiny loop so at least one tick happens
    _py(["jobs", "run", "--poll-interval", "0.1", "--max-loops", "3"], env=env)
    assert sentinel.exists() and sentinel.read_text().strip() == "ok"


def test_a1003_sdk_cli_dry_run(tmp_path: Path, client: httpx.Client):
    # Fetch OpenAPI and write to disk
    schema_path = tmp_path / "openapi.json"
    r = client.get("/openapi.json")
    assert r.status_code == 200
    schema_path.write_text(json.dumps(r.json()), encoding="utf-8")

    env = {"PROJECT_ROOT": str(tmp_path)}

    # TS SDK dry-run prints command
    out_ts = _py(
        [
            "sdk",
            "ts",
            str(schema_path),
            "--outdir",
            str(tmp_path / "sdk-ts"),
            "--dry-run",
            "true",
        ],
        env=env,
    )
    assert "openapi-typescript-codegen" in out_ts.stdout

    # PY SDK dry-run prints command
    out_py = _py(
        [
            "sdk",
            "py",
            str(schema_path),
            "--outdir",
            str(tmp_path / "sdk-py"),
            "--package-name",
            "client_sdk",
            "--dry-run",
            "true",
        ],
        env=env,
    )
    assert "openapi-generator-cli" in out_py.stdout

    # Postman dry-run prints command
    out_pm = _py(
        [
            "sdk",
            "postman",
            str(schema_path),
            "--out",
            str(tmp_path / "postman.json"),
            "--dry-run",
            "true",
        ],
        env=env,
    )
    assert "openapi-to-postmanv2" in out_pm.stdout
