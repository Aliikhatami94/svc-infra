from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from svc_infra.cli import app as cli_app

runner = CliRunner()


def test_docs_list_shows_known_topics(tmp_path: Path):
    # sanity: ensure some docs exist in repo
    result = runner.invoke(cli_app, ["docs", "list"])
    assert result.exit_code == 0
    out = result.stdout
    assert "cache\t" in out
    assert "security\t" in out


def test_docs_topic_command_prints_file_contents():
    result = runner.invoke(cli_app, ["docs", "cache"])
    assert result.exit_code == 0
    out = result.stdout
    # basic content smoke check
    assert "Cache guide" in out
    assert "cashews" in out


def test_docs_topic_option_and_unknown_topic_error():
    # --topic fallback
    result = runner.invoke(cli_app, ["docs", "--topic", "security"])
    assert result.exit_code == 0
    assert "Security" in result.stdout or "security" in result.stdout

    # unknown topic
    bad = runner.invoke(cli_app, ["docs", "--topic", "does-not-exist"])
    assert bad.exit_code != 0
    # Typer shows error text in either stdout or exception depending on version
    combined = (bad.stdout or "") + (getattr(bad, "output", "") or "") + (bad.stderr or "")
    assert "Unknown topic" in combined or (bad.exception and "Unknown topic" in str(bad.exception))
