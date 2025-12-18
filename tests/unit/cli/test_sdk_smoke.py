from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from svc_infra.cli import app

runner = CliRunner()


@pytest.mark.sdk
def test_sdk_smoke_py_import(monkeypatch, tmp_path: Path):
    openapi = tmp_path / "openapi.json"
    openapi.write_text(
        json.dumps({"openapi": "3.0.3", "info": {"title": "x", "version": "1"}, "paths": {}})
    )

    def fake_check_call(cmd):
        # emulate generation by creating a minimal package that can be imported
        # find output directory after '-o'
        if "-o" in cmd:
            outdir = Path(cmd[cmd.index("-o") + 1])
        elif "--output" in cmd:
            outdir = Path(cmd[cmd.index("--output") + 1])
        else:  # pragma: no cover - safety
            outdir = tmp_path / "sdk-py"
        pkg = outdir / "client_sdk"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "__init__.py").write_text("def ping():\n    return 'ok'\n")

    monkeypatch.setattr("subprocess.check_call", fake_check_call)

    outdir = tmp_path / "sdk-py"
    result = runner.invoke(
        app,
        [
            "sdk",
            "py",
            str(openapi),
            "--outdir",
            str(outdir),
            "--package-name",
            "client_sdk",
            "--dry-run",
            "false",
        ],
    )
    assert result.exit_code == 0, result.stdout
    sys.path.insert(0, str(outdir))
    import client_sdk  # type: ignore

    assert client_sdk.ping() == "ok"  # type: ignore[attr-defined]


@pytest.mark.sdk
def test_sdk_smoke_ts_directory(monkeypatch, tmp_path: Path):
    openapi = tmp_path / "openapi.json"
    openapi.write_text(
        json.dumps({"openapi": "3.0.3", "info": {"title": "x", "version": "1"}, "paths": {}})
    )

    def fake_check_call(cmd):
        if "--output" in cmd:
            outdir = Path(cmd[cmd.index("--output") + 1])
        else:
            outdir = tmp_path / "sdk-ts"
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "index.ts").write_text("export const ping = () => 'ok'\n")
        (outdir / "package.json").write_text(json.dumps({"name": "client-ts"}))

    monkeypatch.setattr("subprocess.check_call", fake_check_call)

    outdir = tmp_path / "sdk-ts"
    result = runner.invoke(
        app,
        ["sdk", "ts", str(openapi), "--outdir", str(outdir), "--dry-run", "false"],
    )
    assert result.exit_code == 0, result.stdout
    assert (outdir / "index.ts").exists()
    assert (outdir / "package.json").exists()


@pytest.mark.sdk
def test_sdk_smoke_postman_collection(monkeypatch, tmp_path: Path):
    openapi = tmp_path / "openapi.json"
    out = tmp_path / "postman.json"
    openapi.write_text(
        json.dumps({"openapi": "3.0.3", "info": {"title": "x", "version": "1"}, "paths": {}})
    )

    def fake_check_call(cmd):
        # emulate conversion creating output file
        if "-o" in cmd:
            outfile = Path(cmd[cmd.index("-o") + 1])
        else:
            outfile = out
        outfile.write_text(json.dumps({"info": {"name": "demo"}}))

    monkeypatch.setattr("subprocess.check_call", fake_check_call)

    result = runner.invoke(
        app,
        ["sdk", "postman", str(openapi), "--out", str(out), "--dry-run", "false"],
    )
    assert result.exit_code == 0, result.stdout
    assert out.exists()
