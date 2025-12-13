"""Tests for health check CLI commands.

Tests for:
- svc-infra health check
- svc-infra health wait
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from svc_infra.cli import app as cli_app
from svc_infra.health import HealthCheckResult, HealthStatus

runner = CliRunner()


# =============================================================================
# health check tests
# =============================================================================


class TestHealthCheck:
    """Tests for the 'svc-infra health check' command."""

    def test_check_healthy_endpoint(self) -> None:
        """Reports healthy for 200 response."""
        mock_result = HealthCheckResult(
            name="health",
            status=HealthStatus.HEALTHY,
            latency_ms=15.5,
        )

        with patch("svc_infra.health.check_url") as mock_check:
            mock_check.return_value = AsyncMock(return_value=mock_result)
            result = runner.invoke(cli_app, ["health", "check", "http://localhost:8000/health"])

        assert result.exit_code == 0
        assert "✓" in result.stdout
        assert "healthy" in result.stdout
        assert "15.5ms" in result.stdout

    def test_check_unhealthy_endpoint(self) -> None:
        """Reports unhealthy and exits with error code."""
        mock_result = HealthCheckResult(
            name="health",
            status=HealthStatus.UNHEALTHY,
            latency_ms=0,
            message="Connection refused",
        )

        with patch("svc_infra.health.check_url") as mock_check:
            mock_check.return_value = AsyncMock(return_value=mock_result)
            result = runner.invoke(cli_app, ["health", "check", "http://localhost:8000/health"])

        assert result.exit_code == 1
        assert "✗" in result.stdout
        assert "unhealthy" in result.stdout
        assert "Connection refused" in result.stdout

    def test_check_json_output(self) -> None:
        """JSON output includes all fields."""
        mock_result = HealthCheckResult(
            name="health",
            status=HealthStatus.HEALTHY,
            latency_ms=12.3,
            details={"version": "1.0.0"},
        )

        with patch("svc_infra.health.check_url") as mock_check:
            mock_check.return_value = AsyncMock(return_value=mock_result)
            result = runner.invoke(
                cli_app, ["health", "check", "http://localhost:8000/health", "--json"]
            )

        assert result.exit_code == 0
        import json

        data = json.loads(result.stdout)
        assert data["status"] == "healthy"
        assert data["latency_ms"] == 12.3
        assert data["details"]["version"] == "1.0.0"

    def test_check_verbose_output(self) -> None:
        """Verbose mode shows details."""
        mock_result = HealthCheckResult(
            name="health",
            status=HealthStatus.HEALTHY,
            latency_ms=10.0,
            details={"database": "connected", "cache": "ready"},
        )

        with patch("svc_infra.health.check_url") as mock_check:
            mock_check.return_value = AsyncMock(return_value=mock_result)
            result = runner.invoke(
                cli_app,
                ["health", "check", "http://localhost:8000/health", "--verbose"],
            )

        assert result.exit_code == 0
        assert "Details:" in result.stdout
        assert "database: connected" in result.stdout
        assert "cache: ready" in result.stdout

    def test_check_custom_timeout(self) -> None:
        """Timeout option is passed to check function."""
        mock_result = HealthCheckResult(
            name="health",
            status=HealthStatus.HEALTHY,
            latency_ms=5.0,
        )

        with patch("svc_infra.health.check_url") as mock_check:
            mock_check.return_value = AsyncMock(return_value=mock_result)
            result = runner.invoke(
                cli_app,
                ["health", "check", "http://localhost:8000/health", "--timeout", "30"],
            )

        assert result.exit_code == 0
        mock_check.assert_called_once_with("http://localhost:8000/health", timeout=30.0)

    def test_check_help(self) -> None:
        """Help message shows expected content."""
        result = runner.invoke(cli_app, ["health", "check", "--help"])
        assert result.exit_code == 0
        assert "Check health of a URL endpoint" in result.stdout
        assert "--timeout" in result.stdout
        assert "--json" in result.stdout
        assert "--verbose" in result.stdout


# =============================================================================
# health wait tests
# =============================================================================


class TestHealthWait:
    """Tests for the 'svc-infra health wait' command."""

    def test_wait_healthy_immediately(self) -> None:
        """Returns success if healthy on first check."""
        mock_result = HealthCheckResult(
            name="health",
            status=HealthStatus.HEALTHY,
            latency_ms=8.0,
        )

        with patch("svc_infra.health.check_url") as mock_check:
            mock_check.return_value = AsyncMock(return_value=mock_result)
            result = runner.invoke(
                cli_app,
                ["health", "wait", "http://localhost:8000/health", "--timeout", "5"],
            )

        assert result.exit_code == 0
        assert "Healthy" in result.stdout

    def test_wait_timeout(self) -> None:
        """Exits with error if endpoint never becomes healthy."""
        mock_result = HealthCheckResult(
            name="health",
            status=HealthStatus.UNHEALTHY,
            latency_ms=0,
            message="Service unavailable",
        )

        with patch("svc_infra.health.check_url") as mock_check:
            mock_check.return_value = AsyncMock(return_value=mock_result)
            result = runner.invoke(
                cli_app,
                [
                    "health",
                    "wait",
                    "http://localhost:8000/health",
                    "--timeout",
                    "1",
                    "--interval",
                    "0.2",
                ],
            )

        assert result.exit_code == 1
        assert "not healthy after" in result.stdout

    def test_wait_becomes_healthy(self) -> None:
        """Returns success when endpoint becomes healthy after retries."""
        unhealthy = HealthCheckResult(
            name="health",
            status=HealthStatus.UNHEALTHY,
            latency_ms=0,
            message="Starting up",
        )
        healthy = HealthCheckResult(
            name="health",
            status=HealthStatus.HEALTHY,
            latency_ms=5.0,
        )

        call_count = 0

        async def mock_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return unhealthy
            return healthy

        with patch("svc_infra.health.check_url") as mock_check:
            mock_check.return_value = mock_fn
            result = runner.invoke(
                cli_app,
                [
                    "health",
                    "wait",
                    "http://localhost:8000/health",
                    "--timeout",
                    "10",
                    "--interval",
                    "0.1",
                ],
            )

        assert result.exit_code == 0
        assert "Healthy" in result.stdout

    def test_wait_quiet_mode(self) -> None:
        """Quiet mode suppresses progress messages."""
        mock_result = HealthCheckResult(
            name="health",
            status=HealthStatus.HEALTHY,
            latency_ms=5.0,
        )

        with patch("svc_infra.health.check_url") as mock_check:
            mock_check.return_value = AsyncMock(return_value=mock_result)
            result = runner.invoke(
                cli_app,
                ["health", "wait", "http://localhost:8000/health", "--quiet"],
            )

        assert result.exit_code == 0
        # Quiet mode should not show "Attempt" or "Checking" messages
        assert "Attempt" not in result.stdout
        assert "Checking" not in result.stdout

    def test_wait_help(self) -> None:
        """Help message shows expected content."""
        result = runner.invoke(cli_app, ["health", "wait", "--help"])
        assert result.exit_code == 0
        assert "Wait for a health endpoint to become healthy" in result.stdout
        assert "--timeout" in result.stdout
        assert "--interval" in result.stdout
        assert "--quiet" in result.stdout


# =============================================================================
# Integration tests
# =============================================================================


class TestHealthCLIIntegration:
    """Integration tests for health CLI commands."""

    def test_health_group_help(self) -> None:
        """Health group shows available commands."""
        result = runner.invoke(cli_app, ["health", "--help"])
        assert result.exit_code == 0
        assert "check" in result.stdout
        assert "wait" in result.stdout

    def test_health_commands_registered(self) -> None:
        """Verify health commands are properly registered."""
        # Check that commands are accessible
        result = runner.invoke(cli_app, ["health", "check", "--help"])
        assert result.exit_code == 0

        result = runner.invoke(cli_app, ["health", "wait", "--help"])
        assert result.exit_code == 0
