import os
from pathlib import Path
from unittest.mock import patch
import pytest
from typer.testing import CliRunner

from svc_infra.cli import app, _apply_database_url


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_env():
    original_db_url = os.environ.get("DATABASE_URL")
    yield
    if original_db_url:
        os.environ["DATABASE_URL"] = original_db_url
    elif "DATABASE_URL" in os.environ:
        del os.environ["DATABASE_URL"]


class TestApplyDatabaseUrl:
    def test_apply_database_url_sets_env(self, mock_env):
        test_url = "postgresql://test:test@localhost/testdb"
        _apply_database_url(test_url)
        assert os.environ["DATABASE_URL"] == test_url

    def test_apply_database_url_none_does_nothing(self, mock_env):
        original = os.environ.get("DATABASE_URL")
        _apply_database_url(None)
        assert os.environ.get("DATABASE_URL") == original


class TestInitCommand:
    @patch("svc_infra.db.cli.core_init_alembic")
    def test_init_with_defaults(self, mock_init, runner):
        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        mock_init.assert_called_once()
        args, kwargs = mock_init.call_args
        # async/sync is auto-detected now; no async_db kwarg anymore
        assert "async_db" not in kwargs
        assert kwargs["discover_packages"] is None
        assert kwargs["overwrite"] is False

    @patch("svc_infra.db.cli.core_init_alembic")
    def test_init_with_all_options(self, mock_init, runner, mock_env):
        result = runner.invoke(app, [
            "init",
            "--project-root", "/tmp/test",
            "--database-url", "postgresql://test:test@localhost/testdb",
            "--discover-packages", "pkg1",
            "--discover-packages", "pkg2",
            "--overwrite",
        ])

        assert result.exit_code == 0
        assert os.environ["DATABASE_URL"] == "postgresql://test:test@localhost/testdb"
        mock_init.assert_called_once()
        args, kwargs = mock_init.call_args
        assert kwargs["project_root"] == Path("/tmp/test").resolve()
        assert "async_db" not in kwargs
        assert kwargs["discover_packages"] == ["pkg1", "pkg2"]
        assert kwargs["overwrite"] is True


class TestRevisionCommand:
    @patch("svc_infra.db.cli.core_revision")
    def test_revision_with_required_message(self, mock_revision, runner):
        result = runner.invoke(app, ["revision", "--message", "Test migration"])

        assert result.exit_code == 0
        mock_revision.assert_called_once()
        args, kwargs = mock_revision.call_args
        assert kwargs["message"] == "Test migration"
        assert kwargs["autogenerate"] is False
        assert kwargs["head"] == "head"
        assert kwargs["branch_label"] is None
        assert kwargs["version_path"] is None
        assert kwargs["sql"] is False

    @patch("svc_infra.db.cli.core_revision")
    def test_revision_with_all_options(self, mock_revision, runner, mock_env):
        result = runner.invoke(app, [
            "revision",
            "--message", "Test migration",
            "--project-root", "/tmp/test",
            "--database-url", "sqlite:///test.db",
            "--autogenerate",
            "--head", "abc123",
            "--branch-label", "feature",
            "--version-path", "/tmp/versions",
            "--sql",
        ])

        assert result.exit_code == 0
        assert os.environ["DATABASE_URL"] == "sqlite:///test.db"
        mock_revision.assert_called_once()
        args, kwargs = mock_revision.call_args
        assert kwargs["project_root"] == Path("/tmp/test").resolve()
        assert kwargs["message"] == "Test migration"
        assert kwargs["autogenerate"] is True
        assert kwargs["head"] == "abc123"
        assert kwargs["branch_label"] == "feature"
        assert kwargs["version_path"] == "/tmp/versions"
        assert kwargs["sql"] is True

    def test_revision_without_message_fails(self, runner):
        result = runner.invoke(app, ["revision"])
        assert result.exit_code != 0


class TestUpgradeCommand:
    @patch("svc_infra.db.cli.core_upgrade")
    def test_upgrade_with_defaults(self, mock_upgrade, runner):
        result = runner.invoke(app, ["upgrade"])

        assert result.exit_code == 0
        mock_upgrade.assert_called_once()
        args, kwargs = mock_upgrade.call_args
        assert kwargs["revision_target"] == "head"

    @patch("svc_infra.db.cli.core_upgrade")
    def test_upgrade_with_target(self, mock_upgrade, runner, mock_env):
        result = runner.invoke(app, [
            "upgrade",
            "abc123",
            "--project-root", "/tmp/test",
            "--database-url", "postgresql://test@localhost/db",
        ])

        assert result.exit_code == 0
        assert os.environ["DATABASE_URL"] == "postgresql://test@localhost/db"
        mock_upgrade.assert_called_once()
        args, kwargs = mock_upgrade.call_args
        assert kwargs["project_root"] == Path("/tmp/test").resolve()
        assert kwargs["revision_target"] == "abc123"


class TestDowngradeCommand:
    @patch("svc_infra.db.cli.core_downgrade")
    def test_downgrade_with_defaults(self, mock_downgrade, runner):
        result = runner.invoke(app, ["downgrade"])

        assert result.exit_code == 0
        mock_downgrade.assert_called_once()
        args, kwargs = mock_downgrade.call_args
        assert kwargs["revision_target"] == "-1"

    @patch("svc_infra.db.cli.core_downgrade")
    def test_downgrade_with_target(self, mock_downgrade, runner, mock_env):
        result = runner.invoke(app, [
            "downgrade",
            "base",
            "--project-root", "/tmp/test",
            "--database-url", "sqlite:///test.db",
        ])

        assert result.exit_code == 0
        assert os.environ["DATABASE_URL"] == "sqlite:///test.db"
        mock_downgrade.assert_called_once()
        args, kwargs = mock_downgrade.call_args
        assert kwargs["project_root"] == Path("/tmp/test").resolve()
        assert kwargs["revision_target"] == "base"


class TestCurrentCommand:
    @patch("svc_infra.db.cli.core_current")
    def test_current_with_defaults(self, mock_current, runner):
        result = runner.invoke(app, ["current"])

        assert result.exit_code == 0
        mock_current.assert_called_once()
        args, kwargs = mock_current.call_args
        assert kwargs["verbose"] is False

    @patch("svc_infra.db.cli.core_current")
    def test_current_with_verbose(self, mock_current, runner, mock_env):
        result = runner.invoke(app, [
            "current",
            "--project-root", "/tmp/test",
            "--database-url", "postgresql://localhost/db",
            "--verbose",
        ])

        assert result.exit_code == 0
        assert os.environ["DATABASE_URL"] == "postgresql://localhost/db"
        mock_current.assert_called_once()
        args, kwargs = mock_current.call_args
        assert kwargs["project_root"] == Path("/tmp/test").resolve()
        assert kwargs["verbose"] is True


class TestHistoryCommand:
    @patch("svc_infra.db.cli.core_history")
    def test_history_with_defaults(self, mock_history, runner):
        result = runner.invoke(app, ["history"])

        assert result.exit_code == 0
        mock_history.assert_called_once()
        args, kwargs = mock_history.call_args
        assert kwargs["verbose"] is False

    @patch("svc_infra.db.cli.core_history")
    def test_history_with_verbose(self, mock_history, runner, mock_env):
        result = runner.invoke(app, [
            "history",
            "--project-root", "/tmp/test",
            "--database-url", "mysql://user@localhost/db",
            "--verbose",
        ])

        assert result.exit_code == 0
        assert os.environ["DATABASE_URL"] == "mysql://user@localhost/db"
        mock_history.assert_called_once()
        args, kwargs = mock_history.call_args
        assert kwargs["project_root"] == Path("/tmp/test").resolve()
        assert kwargs["verbose"] is True


class TestStampCommand:
    @patch("svc_infra.db.cli.core_stamp")
    def test_stamp_with_defaults(self, mock_stamp, runner):
        result = runner.invoke(app, ["stamp"])

        assert result.exit_code == 0
        mock_stamp.assert_called_once()
        args, kwargs = mock_stamp.call_args
        assert kwargs["revision_target"] == "head"

    @patch("svc_infra.db.cli.core_stamp")
    def test_stamp_with_target(self, mock_stamp, runner, mock_env):
        result = runner.invoke(app, [
            "stamp",
            "abc123",
            "--project-root", "/tmp/test",
            "--database-url", "sqlite:///test.db",
        ])

        assert result.exit_code == 0
        assert os.environ["DATABASE_URL"] == "sqlite:///test.db"
        mock_stamp.assert_called_once()
        args, kwargs = mock_stamp.call_args
        assert kwargs["project_root"] == Path("/tmp/test").resolve()
        assert kwargs["revision_target"] == "abc123"


class TestMergeHeadsCommand:
    @patch("svc_infra.db.cli.core_merge_heads")
    def test_merge_heads_with_defaults(self, mock_merge, runner):
        result = runner.invoke(app, ["merge-heads"])

        assert result.exit_code == 0
        mock_merge.assert_called_once()
        args, kwargs = mock_merge.call_args
        assert kwargs["message"] is None

    @patch("svc_infra.db.cli.core_merge_heads")
    def test_merge_heads_with_message(self, mock_merge, runner, mock_env):
        result = runner.invoke(app, [
            "merge-heads",
            "--project-root", "/tmp/test",
            "--database-url", "postgresql://localhost/db",
            "--message", "Merge conflicting heads",
        ])

        assert result.exit_code == 0
        assert os.environ["DATABASE_URL"] == "postgresql://localhost/db"
        mock_merge.assert_called_once()
        args, kwargs = mock_merge.call_args
        assert kwargs["project_root"] == Path("/tmp/test").resolve()
        assert kwargs["message"] == "Merge conflicting heads"


class TestScaffoldCommand:
    @patch("svc_infra.db.cli.scaffold_core")
    def test_scaffold_entity_with_defaults(self, mock_scaffold, runner):
        mock_scaffold.return_value = "Generated entity scaffolding"

        result = runner.invoke(app, [
            "scaffold",
            "--models-dir", "/tmp/models",
            "--schemas-dir", "/tmp/schemas",
        ])

        assert result.exit_code == 0
        assert "Generated entity scaffolding" in result.output
        mock_scaffold.assert_called_once()
        args, kwargs = mock_scaffold.call_args
        assert kwargs["kind"] == "entity"
        assert kwargs["entity_name"] == "Item"
        assert kwargs["overwrite"] is False
        assert kwargs["same_dir"] is False

    @patch("svc_infra.db.cli.scaffold_core")
    def test_scaffold_auth_with_options(self, mock_scaffold, runner):
        mock_scaffold.return_value = "Generated auth scaffolding"

        result = runner.invoke(app, [
            "scaffold",
            "--kind", "auth",
            "--entity-name", "User",
            "--models-dir", "/tmp/app/auth",
            "--schemas-dir", "/tmp/app/auth",
            "--overwrite",
            "--same-dir",
            "--models-filename", "auth_models.py",
            "--schemas-filename", "auth_schemas.py",
        ])

        assert result.exit_code == 0
        assert "Generated auth scaffolding" in result.output
        mock_scaffold.assert_called_once()
        args, kwargs = mock_scaffold.call_args
        assert kwargs["kind"] == "auth"
        assert kwargs["entity_name"] == "User"
        assert kwargs["overwrite"] is True
        assert kwargs["same_dir"] is True
        assert kwargs["models_filename"] == "auth_models.py"
        assert kwargs["schemas_filename"] == "auth_schemas.py"

    def test_scaffold_invalid_kind(self, runner):
        result = runner.invoke(app, [
            "scaffold",
            "--kind", "invalid",
            "--models-dir", "/tmp/models",
            "--schemas-dir", "/tmp/schemas",
        ])

        assert result.exit_code != 0


class TestScaffoldModelsCommand:
    @patch("svc_infra.db.cli.scaffold_models_core")
    def test_scaffold_models_with_defaults(self, mock_scaffold, runner):
        mock_scaffold.return_value = "Generated models"

        result = runner.invoke(app, [
            "scaffold-models",
            "--dest-dir", "/tmp/models",
        ])

        assert result.exit_code == 0
        assert "Generated models" in result.output
        mock_scaffold.assert_called_once()
        args, kwargs = mock_scaffold.call_args
        assert kwargs["kind"] == "entity"
        assert kwargs["entity_name"] == "Item"
        assert kwargs["include_tenant"] is True
        assert kwargs["include_soft_delete"] is False
        assert kwargs["overwrite"] is False

    @patch("svc_infra.db.cli.scaffold_models_core")
    def test_scaffold_models_with_all_options(self, mock_scaffold, runner):
        mock_scaffold.return_value = "Generated auth models"

        result = runner.invoke(app, [
            "scaffold-models",
            "--dest-dir", "/tmp/auth",
            "--kind", "auth",
            "--entity-name", "User",
            "--table-name", "users",
            "--no-include-tenant",
            "--include-soft-delete",
            "--overwrite",
            "--models-filename", "user_models.py",
        ])

        assert result.exit_code == 0
        assert "Generated auth models" in result.output
        mock_scaffold.assert_called_once()
        args, kwargs = mock_scaffold.call_args
        assert kwargs["kind"] == "auth"
        assert kwargs["entity_name"] == "User"
        assert kwargs["table_name"] == "users"
        assert kwargs["include_tenant"] is False
        assert kwargs["include_soft_delete"] is True
        assert kwargs["overwrite"] is True
        assert kwargs["models_filename"] == "user_models.py"


class TestScaffoldSchemasCommand:
    @patch("svc_infra.db.cli.scaffold_schemas_core")
    def test_scaffold_schemas_with_defaults(self, mock_scaffold, runner):
        mock_scaffold.return_value = "Generated schemas"

        result = runner.invoke(app, [
            "scaffold-schemas",
            "--dest-dir", "/tmp/schemas",
        ])

        assert result.exit_code == 0
        assert "Generated schemas" in result.output
        mock_scaffold.assert_called_once()
        args, kwargs = mock_scaffold.call_args
        assert kwargs["kind"] == "entity"
        assert kwargs["entity_name"] == "Item"
        assert kwargs["include_tenant"] is True
        assert kwargs["overwrite"] is False

    @patch("svc_infra.db.cli.scaffold_schemas_core")
    def test_scaffold_schemas_with_options(self, mock_scaffold, runner):
        mock_scaffold.return_value = "Generated auth schemas"

        result = runner.invoke(app, [
            "scaffold-schemas",
            "--dest-dir", "/tmp/auth",
            "--kind", "auth",
            "--entity-name", "User",
            "--no-include-tenant",
            "--overwrite",
            "--schemas-filename", "user_schemas.py",
        ])

        assert result.exit_code == 0
        assert "Generated auth schemas" in result.output
        mock_scaffold.assert_called_once()
        args, kwargs = mock_scaffold.call_args
        assert kwargs["kind"] == "auth"
        assert kwargs["entity_name"] == "User"
        assert kwargs["include_tenant"] is False
        assert kwargs["overwrite"] is True
        assert kwargs["schemas_filename"] == "user_schemas.py"


class TestIntegration:
    def test_app_no_args_shows_help(self, runner):
        result = runner.invoke(app, [])
        assert result.exit_code != 0
        assert "Usage:" in result.output

    def test_command_help_works(self, runner):
        result = runner.invoke(app, ["init", "--help"])
        assert result.exit_code == 0
        assert "alembic.ini" in result.output

    @patch.dict(os.environ, {}, clear=True)
    def test_database_url_environment_isolation(self, runner):
        with patch("svc_infra.db.cli.core_upgrade") as mock_upgrade:
            result1 = runner.invoke(app, [
                "upgrade",
                "--database-url", "postgresql://test1@localhost/db1",
            ])
            assert result1.exit_code == 0

            result2 = runner.invoke(app, ["upgrade"])
            assert result2.exit_code == 0

            assert mock_upgrade.call_count == 2

    def test_error_handling_invalid_command(self, runner):
        result = runner.invoke(app, ["nonexistent-command"])
        assert result.exit_code != 0

    @patch("svc_infra.db.cli.core_init_alembic")
    def test_command_exception_handling(self, mock_init, runner):
        mock_init.side_effect = Exception("Test error")

        result = runner.invoke(app, ["init"])
        assert result.exit_code != 0