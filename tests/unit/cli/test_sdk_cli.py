from __future__ import annotations

import pytest
from typer.testing import CliRunner

from svc_infra.cli import app

runner = CliRunner()


@pytest.mark.sdk
def test_sdk_ts_dry_run_prints_command(tmp_path):
    result = runner.invoke(app, ["sdk", "ts", str(tmp_path / "openapi.json")])
    assert result.exit_code == 0
    assert "openapi-typescript-codegen" in result.stdout


@pytest.mark.sdk
def test_sdk_py_dry_run_prints_command(tmp_path):
    result = runner.invoke(app, ["sdk", "py", str(tmp_path / "openapi.json")])
    assert result.exit_code == 0
    assert (
        "openapi-generator" in result.stdout
        or "@openapitools/openapi-generator-cli" in result.stdout
    )


@pytest.mark.sdk
def test_sdk_postman_dry_run_prints_command(tmp_path):
    result = runner.invoke(app, ["sdk", "postman", str(tmp_path / "openapi.json")])
    assert result.exit_code == 0
    assert "openapi-to-postmanv2" in result.stdout
