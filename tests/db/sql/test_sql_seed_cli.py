from __future__ import annotations

from typer.testing import CliRunner

from svc_infra.cli.__init__ import app

called = {"seed": 0}


def my_seed():  # noqa: D401, ANN201
    called["seed"] += 1


def test_sql_seed_cli():
    runner = CliRunner()
    # tests.* is the correct import path for test modules in this repo
    result = runner.invoke(app, ["sql-seed", "tests.db.sql.test_sql_seed_cli:my_seed"])  # type: ignore[arg-type]
    assert result.exit_code == 0, result.output
    assert called["seed"] == 1
