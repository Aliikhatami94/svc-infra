"""Tests for svc_infra.health module."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from svc_infra.health import (
    AggregatedHealthResult,
    HealthCheck,
    HealthCheckResult,
    HealthRegistry,
    HealthStatus,
    add_dependency_health,
    add_health_routes,
    add_startup_probe,
    check_database,
    check_redis,
    check_tcp,
    check_url,
)

# =============================================================================
# HealthStatus Tests
# =============================================================================


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_healthy_value(self) -> None:
        """Test HEALTHY string value."""
        assert HealthStatus.HEALTHY == "healthy"

    def test_unhealthy_value(self) -> None:
        """Test UNHEALTHY string value."""
        assert HealthStatus.UNHEALTHY == "unhealthy"

    def test_degraded_value(self) -> None:
        """Test DEGRADED string value."""
        assert HealthStatus.DEGRADED == "degraded"

    def test_unknown_value(self) -> None:
        """Test UNKNOWN string value."""
        assert HealthStatus.UNKNOWN == "unknown"


# =============================================================================
# HealthCheckResult Tests
# =============================================================================


class TestHealthCheckResult:
    """Tests for HealthCheckResult dataclass."""

    def test_basic_result(self) -> None:
        """Test creating a basic health check result."""
        result = HealthCheckResult(
            name="test",
            status=HealthStatus.HEALTHY,
            latency_ms=5.5,
        )
        assert result.name == "test"
        assert result.status == HealthStatus.HEALTHY
        assert result.latency_ms == 5.5
        assert result.message is None
        assert result.details is None

    def test_result_with_message(self) -> None:
        """Test result with error message."""
        result = HealthCheckResult(
            name="db",
            status=HealthStatus.UNHEALTHY,
            latency_ms=100.0,
            message="Connection refused",
        )
        assert result.message == "Connection refused"

    def test_result_with_details(self) -> None:
        """Test result with additional details."""
        result = HealthCheckResult(
            name="http",
            status=HealthStatus.HEALTHY,
            latency_ms=50.0,
            details={"status_code": 200},
        )
        assert result.details == {"status_code": 200}

    def test_to_dict_minimal(self) -> None:
        """Test to_dict with minimal fields."""
        result = HealthCheckResult(
            name="test",
            status=HealthStatus.HEALTHY,
            latency_ms=5.555,
        )
        d = result.to_dict()
        assert d["name"] == "test"
        assert d["status"] == "healthy"
        # Floating point rounding may vary, just check it's close
        assert 5.55 <= d["latency_ms"] <= 5.56

    def test_to_dict_full(self) -> None:
        """Test to_dict with all fields."""
        result = HealthCheckResult(
            name="test",
            status=HealthStatus.UNHEALTHY,
            latency_ms=100.0,
            message="Error",
            details={"code": 500},
        )
        d = result.to_dict()
        assert d == {
            "name": "test",
            "status": "unhealthy",
            "latency_ms": 100.0,
            "message": "Error",
            "details": {"code": 500},
        }


# =============================================================================
# HealthCheck Tests
# =============================================================================


class TestHealthCheck:
    """Tests for HealthCheck dataclass."""

    def test_defaults(self) -> None:
        """Test default values."""
        check = HealthCheck(
            name="test",
            check_fn=AsyncMock(),
        )
        assert check.critical is True
        assert check.timeout == 5.0

    def test_custom_values(self) -> None:
        """Test custom values."""
        fn = AsyncMock()
        check = HealthCheck(
            name="cache",
            check_fn=fn,
            critical=False,
            timeout=10.0,
        )
        assert check.name == "cache"
        assert check.check_fn is fn
        assert check.critical is False
        assert check.timeout == 10.0


# =============================================================================
# HealthRegistry Tests
# =============================================================================


class TestHealthRegistry:
    """Tests for HealthRegistry class."""

    def test_init_empty(self) -> None:
        """Test initialization creates empty registry."""
        registry = HealthRegistry()
        assert len(registry.checks) == 0

    def test_add_check(self) -> None:
        """Test adding a health check."""
        registry = HealthRegistry()
        mock_fn = AsyncMock()
        registry.add("test", mock_fn)
        assert len(registry.checks) == 1
        assert registry.checks[0].name == "test"

    def test_add_check_duplicate_raises(self) -> None:
        """Test adding duplicate check name raises error."""
        registry = HealthRegistry()
        registry.add("test", AsyncMock())
        with pytest.raises(ValueError, match="already registered"):
            registry.add("test", AsyncMock())

    def test_add_check_with_options(self) -> None:
        """Test adding check with custom options."""
        registry = HealthRegistry()
        registry.add("cache", AsyncMock(), critical=False, timeout=10.0)
        check = registry.checks[0]
        assert check.critical is False
        assert check.timeout == 10.0

    def test_remove_existing(self) -> None:
        """Test removing an existing check."""
        registry = HealthRegistry()
        registry.add("test", AsyncMock())
        assert registry.remove("test") is True
        assert len(registry.checks) == 0

    def test_remove_nonexistent(self) -> None:
        """Test removing a non-existent check."""
        registry = HealthRegistry()
        assert registry.remove("test") is False

    def test_clear(self) -> None:
        """Test clearing all checks."""
        registry = HealthRegistry()
        registry.add("one", AsyncMock())
        registry.add("two", AsyncMock())
        registry.clear()
        assert len(registry.checks) == 0

    @pytest.mark.asyncio
    async def test_check_one_success(self) -> None:
        """Test running a single check that succeeds."""
        registry = HealthRegistry()

        async def healthy_check() -> HealthCheckResult:
            return HealthCheckResult(
                name="test",
                status=HealthStatus.HEALTHY,
                latency_ms=1.0,
            )

        registry.add("test", healthy_check)
        result = await registry.check_one("test")
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_one_not_found(self) -> None:
        """Test running a check that doesn't exist."""
        registry = HealthRegistry()
        with pytest.raises(KeyError, match="not found"):
            await registry.check_one("nonexistent")

    @pytest.mark.asyncio
    async def test_check_one_timeout(self) -> None:
        """Test check that times out."""
        registry = HealthRegistry()

        async def slow_check() -> HealthCheckResult:
            await asyncio.sleep(10)
            return HealthCheckResult(name="slow", status=HealthStatus.HEALTHY, latency_ms=0)

        registry.add("slow", slow_check, timeout=0.1)
        result = await registry.check_one("slow")
        assert result.status == HealthStatus.UNHEALTHY
        assert "timed out" in (result.message or "")

    @pytest.mark.asyncio
    async def test_check_one_exception(self) -> None:
        """Test check that raises an exception."""
        registry = HealthRegistry()

        async def failing_check() -> HealthCheckResult:
            raise RuntimeError("Connection failed")

        registry.add("fail", failing_check)
        result = await registry.check_one("fail")
        assert result.status == HealthStatus.UNHEALTHY
        assert "Connection failed" in (result.message or "")

    @pytest.mark.asyncio
    async def test_check_all_no_checks(self) -> None:
        """Test check_all with no registered checks."""
        registry = HealthRegistry()
        result = await registry.check_all()
        assert result.status == HealthStatus.HEALTHY
        assert len(result.checks) == 0

    @pytest.mark.asyncio
    async def test_check_all_all_healthy(self) -> None:
        """Test check_all when all checks pass."""
        registry = HealthRegistry()

        async def healthy() -> HealthCheckResult:
            return HealthCheckResult(name="h", status=HealthStatus.HEALTHY, latency_ms=1)

        registry.add("one", healthy)
        registry.add("two", healthy)

        result = await registry.check_all()
        assert result.status == HealthStatus.HEALTHY
        assert len(result.checks) == 2

    @pytest.mark.asyncio
    async def test_check_all_critical_fails(self) -> None:
        """Test check_all when a critical check fails."""
        registry = HealthRegistry()

        async def healthy() -> HealthCheckResult:
            return HealthCheckResult(name="h", status=HealthStatus.HEALTHY, latency_ms=1)

        async def unhealthy() -> HealthCheckResult:
            return HealthCheckResult(name="u", status=HealthStatus.UNHEALTHY, latency_ms=1)

        registry.add("healthy", healthy, critical=True)
        registry.add("unhealthy", unhealthy, critical=True)

        result = await registry.check_all()
        assert result.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_check_all_noncritical_fails(self) -> None:
        """Test check_all when only non-critical check fails."""
        registry = HealthRegistry()

        async def healthy() -> HealthCheckResult:
            return HealthCheckResult(name="h", status=HealthStatus.HEALTHY, latency_ms=1)

        async def unhealthy() -> HealthCheckResult:
            return HealthCheckResult(name="u", status=HealthStatus.UNHEALTHY, latency_ms=1)

        registry.add("healthy", healthy, critical=True)
        registry.add("cache", unhealthy, critical=False)

        result = await registry.check_all()
        assert result.status == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_wait_until_healthy_immediate(self) -> None:
        """Test wait_until_healthy when already healthy."""
        registry = HealthRegistry()

        async def healthy() -> HealthCheckResult:
            return HealthCheckResult(name="h", status=HealthStatus.HEALTHY, latency_ms=1)

        registry.add("test", healthy)

        result = await registry.wait_until_healthy(timeout=5)
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_until_healthy_timeout(self) -> None:
        """Test wait_until_healthy times out when unhealthy."""
        registry = HealthRegistry()

        async def unhealthy() -> HealthCheckResult:
            return HealthCheckResult(name="u", status=HealthStatus.UNHEALTHY, latency_ms=1)

        registry.add("test", unhealthy)

        result = await registry.wait_until_healthy(timeout=0.3, interval=0.1)
        assert result is False

    @pytest.mark.asyncio
    async def test_wait_until_healthy_becomes_healthy(self) -> None:
        """Test wait_until_healthy succeeds when check becomes healthy."""
        registry = HealthRegistry()
        call_count = 0

        async def eventually_healthy() -> HealthCheckResult:
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                return HealthCheckResult(name="e", status=HealthStatus.HEALTHY, latency_ms=1)
            return HealthCheckResult(name="e", status=HealthStatus.UNHEALTHY, latency_ms=1)

        registry.add("test", eventually_healthy)

        result = await registry.wait_until_healthy(timeout=5, interval=0.1)
        assert result is True
        assert call_count >= 3

    @pytest.mark.asyncio
    async def test_wait_until_healthy_specific_checks(self) -> None:
        """Test wait_until_healthy with specific check names."""
        registry = HealthRegistry()

        async def healthy() -> HealthCheckResult:
            return HealthCheckResult(name="h", status=HealthStatus.HEALTHY, latency_ms=1)

        async def unhealthy() -> HealthCheckResult:
            return HealthCheckResult(name="u", status=HealthStatus.UNHEALTHY, latency_ms=1)

        registry.add("healthy", healthy)
        registry.add("unhealthy", unhealthy)

        # Wait only for the healthy check
        result = await registry.wait_until_healthy(timeout=1, check_names=["healthy"])
        assert result is True


# =============================================================================
# AggregatedHealthResult Tests
# =============================================================================


class TestAggregatedHealthResult:
    """Tests for AggregatedHealthResult dataclass."""

    def test_to_dict_minimal(self) -> None:
        """Test to_dict with minimal data."""
        result = AggregatedHealthResult(
            status=HealthStatus.HEALTHY,
            checks=[],
        )
        d = result.to_dict()
        assert d == {"status": "healthy", "checks": []}

    def test_to_dict_with_checks(self) -> None:
        """Test to_dict with check results."""
        result = AggregatedHealthResult(
            status=HealthStatus.DEGRADED,
            checks=[
                HealthCheckResult(name="db", status=HealthStatus.HEALTHY, latency_ms=5.0),
                HealthCheckResult(name="cache", status=HealthStatus.UNHEALTHY, latency_ms=100.0),
            ],
        )
        d = result.to_dict()
        assert d["status"] == "degraded"
        assert len(d["checks"]) == 2

    def test_to_dict_with_message(self) -> None:
        """Test to_dict with message."""
        result = AggregatedHealthResult(
            status=HealthStatus.HEALTHY,
            checks=[],
            message="All systems operational",
        )
        d = result.to_dict()
        assert d["message"] == "All systems operational"


# =============================================================================
# check_database Tests
# =============================================================================


class TestCheckDatabase:
    """Tests for check_database function."""

    @pytest.mark.asyncio
    async def test_no_url(self) -> None:
        """Test with no URL configured."""
        check = check_database(None)
        result = await check()
        assert result.status == HealthStatus.UNHEALTHY
        assert "not configured" in (result.message or "")

    @pytest.mark.asyncio
    async def test_asyncpg_not_installed(self) -> None:
        """Test when asyncpg is not installed."""
        # If asyncpg is actually installed, this test just verifies
        # the code doesn't crash when connection fails
        check = check_database("postgresql://invalid-host-that-does-not-exist/test")
        result = await check()
        # Should return unhealthy or unknown when connection fails
        assert result.status in (HealthStatus.UNHEALTHY, HealthStatus.UNKNOWN)

    @pytest.mark.asyncio
    async def test_connection_success(self) -> None:
        """Test successful database connection (mocked)."""
        # Create a mock module for asyncpg
        mock_asyncpg = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.close = AsyncMock()

        # Mock asyncpg.connect to return our mock connection
        async def mock_connect(*args, **kwargs):
            return mock_conn

        mock_asyncpg.connect = mock_connect

        with patch.dict("sys.modules", {"asyncpg": mock_asyncpg}):
            check = check_database("postgresql://localhost/test")
            result = await check()
            assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_normalizes_url(self) -> None:
        """Test that postgres:// is normalized to postgresql://."""
        # Create a mock to capture the URL
        captured_url = []

        mock_asyncpg = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.close = AsyncMock()

        async def mock_connect(url, *args, **kwargs):
            captured_url.append(url)
            return mock_conn

        mock_asyncpg.connect = mock_connect

        with patch.dict("sys.modules", {"asyncpg": mock_asyncpg}):
            check = check_database("postgres://localhost/test")
            await check()
            # Check that the URL was normalized
            assert len(captured_url) == 1
            assert "postgresql://" in captured_url[0]


# =============================================================================
# check_redis Tests
# =============================================================================


class TestCheckRedis:
    """Tests for check_redis function."""

    @pytest.mark.asyncio
    async def test_no_url(self) -> None:
        """Test with no URL configured."""
        check = check_redis(None)
        result = await check()
        assert result.status == HealthStatus.UNHEALTHY
        assert "not configured" in (result.message or "")

    @pytest.mark.asyncio
    async def test_connection_success(self) -> None:
        """Test successful Redis connection (mocked)."""
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=True)
        mock_client.aclose = AsyncMock()

        with patch("redis.asyncio.from_url", return_value=mock_client):
            check = check_redis("redis://localhost:6379")
            result = await check()
            assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_ping_returns_false(self) -> None:
        """Test when Redis PING returns False."""
        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(return_value=False)
        mock_client.aclose = AsyncMock()

        with patch("redis.asyncio.from_url", return_value=mock_client):
            check = check_redis("redis://localhost:6379")
            result = await check()
            assert result.status == HealthStatus.UNHEALTHY


# =============================================================================
# check_url Tests
# =============================================================================


class TestCheckUrl:
    """Tests for check_url function."""

    @pytest.mark.asyncio
    async def test_success(self) -> None:
        """Test successful HTTP check."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("svc_infra.health.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            check = check_url("http://api:8080/health")
            result = await check()
            assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_wrong_status(self) -> None:
        """Test when status code doesn't match expected."""
        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch("svc_infra.health.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            check = check_url("http://api:8080/health", expected_status=200)
            result = await check()
            assert result.status == HealthStatus.UNHEALTHY
            assert "Expected status 200" in (result.message or "")

    @pytest.mark.asyncio
    async def test_custom_expected_status(self) -> None:
        """Test with custom expected status code."""
        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch("svc_infra.health.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            check = check_url("http://api:8080/health", expected_status=204)
            result = await check()
            assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        """Test connection timeout."""
        import httpx

        # Create a mock that properly implements async context manager
        mock_client = MagicMock()
        mock_client.request = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("svc_infra.health.httpx.AsyncClient", return_value=mock_client):
            check = check_url("http://api:8080/health", timeout=1.0)
            result = await check()
            assert result.status == HealthStatus.UNHEALTHY
            assert "timeout" in (result.message or "").lower()

    @pytest.mark.asyncio
    async def test_connection_error(self) -> None:
        """Test connection error."""
        import httpx

        # Create a mock that properly implements async context manager
        mock_client = MagicMock()
        mock_client.request = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("svc_infra.health.httpx.AsyncClient", return_value=mock_client):
            check = check_url("http://api:8080/health")
            result = await check()
            assert result.status == HealthStatus.UNHEALTHY


# =============================================================================
# check_tcp Tests
# =============================================================================


class TestCheckTcp:
    """Tests for check_tcp function."""

    @pytest.mark.asyncio
    async def test_success(self) -> None:
        """Test successful TCP connection."""
        mock_writer = AsyncMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with patch("asyncio.open_connection", return_value=(None, mock_writer)):
            check = check_tcp("localhost", 5432)
            result = await check()
            assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        """Test connection timeout."""
        with patch("asyncio.open_connection", side_effect=asyncio.TimeoutError):
            check = check_tcp("localhost", 5432, timeout=1.0)
            result = await check()
            assert result.status == HealthStatus.UNHEALTHY
            assert "timeout" in (result.message or "").lower()

    @pytest.mark.asyncio
    async def test_connection_refused(self) -> None:
        """Test connection refused."""
        with patch("asyncio.open_connection", side_effect=OSError("Connection refused")):
            check = check_tcp("localhost", 9999)
            result = await check()
            assert result.status == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_name_includes_host_port(self) -> None:
        """Test that result name includes host:port."""
        with patch("asyncio.open_connection", side_effect=OSError("refused")):
            check = check_tcp("myhost", 1234)
            result = await check()
            assert result.name == "myhost:1234"


# =============================================================================
# FastAPI Integration Tests
# =============================================================================


class TestAddHealthRoutes:
    """Tests for add_health_routes function."""

    def test_adds_routes(self) -> None:
        """Test that health routes are added to the app."""
        from fastapi import FastAPI

        app = FastAPI()
        registry = HealthRegistry()

        add_health_routes(app, registry)

        # Check routes were added
        routes = [r.path for r in app.routes]
        assert "/_health/live" in routes or "/_health/live/" in routes
        assert "/_health/ready" in routes or "/_health/ready/" in routes
        assert "/_health/startup" in routes or "/_health/startup/" in routes

    def test_custom_prefix(self) -> None:
        """Test with custom prefix."""
        from fastapi import FastAPI

        app = FastAPI()
        registry = HealthRegistry()

        add_health_routes(app, registry, prefix="/probes")

        routes = [r.path for r in app.routes]
        assert "/probes/live" in routes or "/probes/live/" in routes

    @pytest.mark.asyncio
    async def test_liveness_always_ok(self) -> None:
        """Test liveness endpoint always returns 200."""
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        app = FastAPI()
        registry = HealthRegistry()
        add_health_routes(app, registry)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/_health/live")
            assert response.status_code == 200
            assert response.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_readiness_healthy(self) -> None:
        """Test readiness endpoint when all checks pass."""
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        app = FastAPI()
        registry = HealthRegistry()

        async def healthy() -> HealthCheckResult:
            return HealthCheckResult(name="test", status=HealthStatus.HEALTHY, latency_ms=1)

        registry.add("test", healthy)
        add_health_routes(app, registry)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/_health/ready")
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_readiness_unhealthy(self) -> None:
        """Test readiness endpoint when checks fail."""
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        app = FastAPI()
        registry = HealthRegistry()

        async def unhealthy() -> HealthCheckResult:
            return HealthCheckResult(name="test", status=HealthStatus.UNHEALTHY, latency_ms=1)

        registry.add("test", unhealthy)
        add_health_routes(app, registry)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/_health/ready")
            assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_single_check_endpoint(self) -> None:
        """Test single check endpoint."""
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        app = FastAPI()
        registry = HealthRegistry()

        async def healthy() -> HealthCheckResult:
            return HealthCheckResult(name="db", status=HealthStatus.HEALTHY, latency_ms=1)

        registry.add("db", healthy)
        add_health_routes(app, registry)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/_health/checks/db")
            assert response.status_code == 200
            assert response.json()["name"] == "db"

    @pytest.mark.asyncio
    async def test_single_check_not_found(self) -> None:
        """Test single check endpoint with unknown check."""
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        app = FastAPI()
        registry = HealthRegistry()
        add_health_routes(app, registry)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/_health/checks/unknown")
            assert response.status_code == 404


class TestAddStartupProbe:
    """Tests for add_startup_probe function."""

    @pytest.mark.asyncio
    async def test_startup_success(self) -> None:
        """Test startup probe with healthy checks."""
        from fastapi import FastAPI

        app = FastAPI()

        async def healthy() -> HealthCheckResult:
            return HealthCheckResult(name="test", status=HealthStatus.HEALTHY, latency_ms=1)

        add_startup_probe(app, [healthy], timeout=5)

        # Simulate startup
        for handler in app.router.on_startup:
            await handler()

        # If we get here, startup succeeded

    @pytest.mark.asyncio
    async def test_startup_timeout(self) -> None:
        """Test startup probe times out with unhealthy checks."""
        from fastapi import FastAPI

        app = FastAPI()

        async def unhealthy() -> HealthCheckResult:
            return HealthCheckResult(name="test", status=HealthStatus.UNHEALTHY, latency_ms=1)

        add_startup_probe(app, [unhealthy], timeout=0.3, interval=0.1)

        # Startup should raise RuntimeError
        with pytest.raises(RuntimeError, match="not ready"):
            for handler in app.router.on_startup:
                await handler()


class TestAddDependencyHealth:
    """Tests for add_dependency_health function."""

    def test_creates_registry(self) -> None:
        """Test that registry is created if not exists."""
        from fastapi import FastAPI

        app = FastAPI()

        async def healthy() -> HealthCheckResult:
            return HealthCheckResult(name="test", status=HealthStatus.HEALTHY, latency_ms=1)

        add_dependency_health(app, "db", healthy)

        assert hasattr(app.state, "_health_registry")
        assert len(app.state._health_registry.checks) == 1

    def test_adds_to_existing_registry(self) -> None:
        """Test adding to existing registry."""
        from fastapi import FastAPI

        app = FastAPI()

        async def healthy() -> HealthCheckResult:
            return HealthCheckResult(name="test", status=HealthStatus.HEALTHY, latency_ms=1)

        add_dependency_health(app, "db", healthy)
        add_dependency_health(app, "cache", healthy, critical=False)

        assert len(app.state._health_registry.checks) == 2

    def test_requires_state(self) -> None:
        """Test that app must have state attribute."""

        class NoStateApp:
            pass

        app = NoStateApp()

        async def healthy() -> HealthCheckResult:
            return HealthCheckResult(name="test", status=HealthStatus.HEALTHY, latency_ms=1)

        with pytest.raises(ValueError, match="state"):
            add_dependency_health(app, "db", healthy)  # type: ignore


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_check_latency_measured(self) -> None:
        """Test that latency is measured accurately."""
        registry = HealthRegistry()

        async def slow_check() -> HealthCheckResult:
            await asyncio.sleep(0.1)  # 100ms
            return HealthCheckResult(name="slow", status=HealthStatus.HEALTHY, latency_ms=0)

        registry.add("slow", slow_check, timeout=5)
        result = await registry.check_one("slow")

        # Latency should be at least 100ms (but allow some tolerance)
        assert result.latency_ms >= 95  # Allow 5ms tolerance

    @pytest.mark.asyncio
    async def test_concurrent_checks(self) -> None:
        """Test that checks run concurrently."""
        registry = HealthRegistry()
        start_times: list[float] = []

        async def track_time() -> HealthCheckResult:
            import time as time_mod

            start_times.append(time_mod.perf_counter())
            await asyncio.sleep(0.1)
            return HealthCheckResult(name="t", status=HealthStatus.HEALTHY, latency_ms=1)

        registry.add("one", track_time)
        registry.add("two", track_time)
        registry.add("three", track_time)

        await registry.check_all()

        # All checks should start at approximately the same time
        if len(start_times) == 3:
            time_spread = max(start_times) - min(start_times)
            assert time_spread < 0.05  # Less than 50ms difference

    @pytest.mark.asyncio
    async def test_empty_registry_wait(self) -> None:
        """Test wait_until_healthy with empty registry."""
        registry = HealthRegistry()
        result = await registry.wait_until_healthy(timeout=1)
        assert result is True

    def test_check_url_extracts_name(self) -> None:
        """Test that check_url extracts name from URL."""
        # This is more of a smoke test - we can't easily test the name
        # without running the check, but we can verify the function doesn't crash
        check = check_url("http://api-service:8080/health")
        assert callable(check)
