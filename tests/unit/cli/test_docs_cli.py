from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from svc_infra.cli import app as cli_app

runner = CliRunner()


def test_docs_topic_command_prints_file_contents():
    result = runner.invoke(cli_app, ["docs", "cache"])
    assert result.exit_code == 0
    out = result.stdout
    # basic content smoke check
    assert "Cache guide" in out
    assert "cashews" in out


def test_docs_dynamic_and_unknown_topic_error():
    # dynamic command works
    result = runner.invoke(cli_app, ["docs", "security"])
    assert result.exit_code == 0
    assert "Security" in result.stdout or "security" in result.stdout

    # unknown topic as dynamic subcommand
    bad = runner.invoke(cli_app, ["docs", "does-not-exist"])
    assert bad.exit_code != 0
    combined = (
        (bad.stdout or "") + (getattr(bad, "output", "") or "") + (bad.stderr or "")
    )
    assert "No such command" in combined


def test_docs_env_override(monkeypatch, tmp_path):
    # Create a custom docs dir with a unique topic
    custom_docs = tmp_path / "docs"
    custom_docs.mkdir()
    f = custom_docs / "custom-topic.md"
    f.write_text("# Custom Topic\nThis is custom docs.")

    # Point CLI at this docs dir via env var and ensure content is shown
    monkeypatch.setenv("SVC_INFRA_DOCS_DIR", str(custom_docs))

    res_topic = runner.invoke(cli_app, ["docs", "custom-topic"])
    assert res_topic.exit_code == 0
    assert "Custom Topic" in res_topic.stdout


def test_docs_dir_option_removed_shows_error(tmp_path: Path):
    # --docs-dir is no longer supported; ensure Typer rejects it
    result = runner.invoke(cli_app, ["docs", "--docs-dir", str(tmp_path), "show", "x"])
    assert result.exit_code != 0


def test_docs_topic_name_normalization_with_env(tmp_path: Path, monkeypatch):
    # Create docs with mixed case and underscores/spaces
    custom_docs = tmp_path / "docs"
    custom_docs.mkdir()
    f = custom_docs / "Mixed_Name Topic.md"
    f.write_text("# Normalized Topic\nThis should be found via normalized key.")

    monkeypatch.setenv("SVC_INFRA_DOCS_DIR", str(custom_docs))

    # Dynamic subcommand with normalized name should work
    res_topic = runner.invoke(cli_app, ["docs", "mixed-name-topic"])
    assert res_topic.exit_code == 0
    assert "Normalized Topic" in res_topic.stdout

    # Un-normalized input is not a valid dynamic command name; only normalized works
