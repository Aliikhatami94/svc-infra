"""Tests for database operations CLI commands.

Tests for:
- svc-infra db wait
- svc-infra db kill-queries
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from svc_infra.cli import app as cli_app
from svc_infra.health import HealthCheckResult, HealthStatus

runner = CliRunner()


# =============================================================================
# db wait tests
# =============================================================================


class TestDbWait:
    """Tests for the 'svc-infra db wait' command."""

    def test_wait_no_url_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Fails with error if no database URL provided."""
        monkeypatch.delenv("SQL_URL", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)

        result = runner.invoke(cli_app, ["db", "wait"])
        assert result.exit_code == 1
        assert "No database URL" in result.stdout

    def test_wait_url_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Uses SQL_URL from environment."""
        monkeypatch.setenv("SQL_URL", "postgresql://localhost/test")

        # Mock the health check to return healthy immediately
        mock_result = HealthCheckResult(
            name="database",
            status=HealthStatus.HEALTHY,
            latency_ms=5.0,
        )

        with patch("svc_infra.health.check_database") as mock_check:
            mock_check.return_value = AsyncMock(return_value=mock_result)
            result = runner.invoke(cli_app, ["db", "wait", "--timeout", "1"])

        assert result.exit_code == 0
        assert "Database ready" in result.stdout

    def test_wait_url_from_option(self) -> None:
        """Uses --url option if provided."""
        mock_result = HealthCheckResult(
            name="database",
            status=HealthStatus.HEALTHY,
            latency_ms=3.0,
        )

        with patch("svc_infra.health.check_database") as mock_check:
            mock_check.return_value = AsyncMock(return_value=mock_result)
            result = runner.invoke(
                cli_app,
                [
                    "db",
                    "wait",
                    "--url",
                    "postgresql://localhost/test",
                    "--timeout",
                    "1",
                ],
            )

        assert result.exit_code == 0
        mock_check.assert_called_once_with("postgresql://localhost/test")

    def test_wait_database_url_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Falls back to DATABASE_URL if SQL_URL not set."""
        monkeypatch.delenv("SQL_URL", raising=False)
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/fallback")

        mock_result = HealthCheckResult(
            name="database",
            status=HealthStatus.HEALTHY,
            latency_ms=2.0,
        )

        with patch("svc_infra.health.check_database") as mock_check:
            mock_check.return_value = AsyncMock(return_value=mock_result)
            result = runner.invoke(cli_app, ["db", "wait", "--timeout", "1"])

        assert result.exit_code == 0
        mock_check.assert_called_once_with("postgresql://localhost/fallback")

    def test_wait_timeout_error(self) -> None:
        """Exits with error after timeout if database not ready."""
        mock_result = HealthCheckResult(
            name="database",
            status=HealthStatus.UNHEALTHY,
            latency_ms=0,
            message="Connection refused",
        )

        with patch("svc_infra.health.check_database") as mock_check:
            mock_check.return_value = AsyncMock(return_value=mock_result)
            result = runner.invoke(
                cli_app,
                [
                    "db",
                    "wait",
                    "--url",
                    "postgresql://localhost/test",
                    "--timeout",
                    "1",
                    "--interval",
                    "0.2",
                ],
            )

        assert result.exit_code == 1
        assert "not ready after" in result.stdout

    def test_wait_quiet_mode(self) -> None:
        """Quiet mode suppresses progress messages."""
        mock_result = HealthCheckResult(
            name="database",
            status=HealthStatus.HEALTHY,
            latency_ms=5.0,
        )

        with patch("svc_infra.health.check_database") as mock_check:
            mock_check.return_value = AsyncMock(return_value=mock_result)
            result = runner.invoke(
                cli_app,
                ["db", "wait", "--url", "postgresql://localhost/test", "--quiet"],
            )

        assert result.exit_code == 0
        # Quiet mode should not show "Attempt 1" messages
        assert "Attempt" not in result.stdout

    def test_wait_help(self) -> None:
        """Help message shows expected content."""
        result = runner.invoke(cli_app, ["db", "wait", "--help"])
        assert result.exit_code == 0
        assert "Wait for database to be ready" in result.stdout
        assert "--timeout" in result.stdout
        assert "--interval" in result.stdout


# =============================================================================
# db kill-queries tests
# =============================================================================


class TestDbKillQueries:
    """Tests for the 'svc-infra db kill-queries' command."""

    def test_kill_queries_no_url_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Fails with error if no database URL provided."""
        monkeypatch.delenv("SQL_URL", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)

        result = runner.invoke(cli_app, ["db", "kill-queries", "users"])
        assert result.exit_code == 1
        assert "No database URL" in result.stdout

    def test_kill_queries_help(self) -> None:
        """Help message shows expected content."""
        result = runner.invoke(cli_app, ["db", "kill-queries", "--help"])
        assert result.exit_code == 0
        assert "Kill queries blocking operations on a table" in result.stdout
        assert "--dry-run" in result.stdout
        assert "--force" in result.stdout
        assert "--quiet" in result.stdout
        assert "--url" in result.stdout

    def test_kill_queries_missing_argument_shows_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing table argument results in error."""
        # Without URL, we get URL error first
        monkeypatch.delenv("SQL_URL", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)
        result = runner.invoke(cli_app, ["db", "kill-queries"])
        # Should exit with error (URL check or argument check)
        assert result.exit_code != 0
