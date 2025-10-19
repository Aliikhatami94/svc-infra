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


def test_docs_env_override(monkeypatch, tmp_path):
    # Create a custom docs dir with a unique topic
    custom_docs = tmp_path / "docs"
    custom_docs.mkdir()
    f = custom_docs / "custom-topic.md"
    f.write_text("# Custom Topic\nThis is custom docs.")

    # Point CLI at this docs dir via env var
    monkeypatch.setenv("SVC_INFRA_DOCS_DIR", str(custom_docs))

    # list should include custom-topic
    res_list = runner.invoke(cli_app, ["docs", "list"])
    assert res_list.exit_code == 0
    assert "custom-topic\t" in res_list.stdout

    # topic should render content
    res_topic = runner.invoke(cli_app, ["docs", "custom-topic"])
    assert res_topic.exit_code == 0
    assert "Custom Topic" in res_topic.stdout


def test_docs_dir_option_propagates_to_subcommands(tmp_path: Path):
    custom_docs = tmp_path / "docs"
    custom_docs.mkdir()
    f = custom_docs / "option-topic.md"
    f.write_text("# Option Topic\nDocs from option.")

    docs_dir_arg = str(custom_docs)

    result_list = runner.invoke(cli_app, ["docs", "--docs-dir", docs_dir_arg, "list"])
    assert result_list.exit_code == 0
    assert "option-topic\t" in result_list.stdout

    result_topic = runner.invoke(cli_app, ["docs", "--docs-dir", docs_dir_arg, "option-topic"])
    assert result_topic.exit_code == 0
    assert "Option Topic" in result_topic.stdout


def test_docs_topic_name_normalization_with_option(tmp_path: Path):
    # Create docs with mixed case and underscores/spaces
    custom_docs = tmp_path / "docs"
    custom_docs.mkdir()
    f = custom_docs / "Mixed_Name Topic.md"
    f.write_text("# Normalized Topic\nThis should be found via normalized key.")

    docs_dir_arg = str(custom_docs)

    # Dynamic subcommand with normalized name should work
    res_topic = runner.invoke(cli_app, ["docs", "--docs-dir", docs_dir_arg, "mixed-name-topic"])
    assert res_topic.exit_code == 0
    assert "Normalized Topic" in res_topic.stdout

    # --topic should also work with un-normalized input
    res_topic_flag = runner.invoke(
        cli_app, ["docs", "--docs-dir", docs_dir_arg, "--topic", "Mixed_Name Topic"]
    )
    assert res_topic_flag.exit_code == 0
    assert "Normalized Topic" in res_topic_flag.stdout


def test_docs_dir_option_precedes_env(monkeypatch, tmp_path: Path):
    # Prepare two docs directories; CLI should pick --docs-dir over env
    env_docs = tmp_path / "env_docs"
    env_docs.mkdir()
    (env_docs / "from-env.md").write_text("# From Env\n")

    opt_docs = tmp_path / "opt_docs"
    opt_docs.mkdir()
    (opt_docs / "from-opt.md").write_text("# From Option\n")

    monkeypatch.setenv("SVC_INFRA_DOCS_DIR", str(env_docs))

    # list should include only from-opt when --docs-dir is provided (first hit wins)
    res_list = runner.invoke(cli_app, ["docs", "--docs-dir", str(opt_docs), "list"])
    assert res_list.exit_code == 0
    out = res_list.stdout
    assert "from-opt\t" in out
    assert "from-env\t" not in out
