from __future__ import annotations

import typer
from typer.testing import CliRunner

from svc_infra.cli import app as cli_app

runner = CliRunner()


def test_root_help_shows_commands():
    result = runner.invoke(cli_app, ["--help"])
    assert result.exit_code == 0
    # A few representative commands we register
    assert "sql-init" in result.stdout
    assert "sql-setup-and-migrate" in result.stdout
    assert "sql-seed" in result.stdout


def test_sql_init_help():
    result = runner.invoke(cli_app, ["sql-init", "--help"])
    assert result.exit_code == 0
    assert "Initialize Alembic scaffold" in result.stdout
    assert "--discover-packages" in result.stdout


def test_seed_bad_format_errors():
    # Missing ':' separator
    result = runner.invoke(cli_app, ["sql-seed", "badformat"])
    assert result.exit_code != 0
    out = (result.stdout or "") + (getattr(result, "output", "") or "") + (result.stderr or "")
    assert "Expected format" in out or "Invalid value for 'TARGET'" in out


def test_seed_missing_callable_errors():
    # Point to this test module but a missing callable name
    dotted = "tests.unit.cli.test_cli_help_and_errors:does_not_exist"
    result = runner.invoke(cli_app, ["sql-seed", dotted])
    assert result.exit_code != 0
    out = (result.stdout or "") + (getattr(result, "output", "") or "") + (result.stderr or "")
    assert "Callable 'does_not_exist' not found" in out or "Invalid value for 'TARGET'" in out


def test_sql_current_missing_db_path(monkeypatch):
    # Simulate a DB connection failure path by making the implementation raise.
    import svc_infra.cli.cmds.db.sql.alembic_cmds as alembic_cmds

    def fake_current(*args, **kwargs):  # noqa: ANN001
        raise RuntimeError("DB missing or unreachable")

    monkeypatch.setattr(alembic_cmds, "core_current", fake_current)

    result = runner.invoke(cli_app, ["sql-current"])  # no SQL_URL set
    # Typer propagates unhandled exceptions; ensure we see it
    assert result.exit_code != 0
    assert result.exception is not None
    assert "DB missing or unreachable" in str(result.exception)
