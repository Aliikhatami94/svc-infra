"""Health check utilities for svc-infra applications.

This module provides comprehensive health check infrastructure for
containerized deployments, including:

- **Startup probes**: Wait for dependencies before accepting traffic
- **Readiness probes**: Check if the service can handle requests
- **Liveness probes**: Verify the service is still running
- **Dependency checks**: Built-in checks for common services

Designed for Kubernetes, Docker, and PaaS deployments where proper
health probes prevent routing traffic to unhealthy instances.

Example:
    >>> from svc_infra.health import (
    ...     HealthRegistry,
    ...     check_database,
    ...     check_redis,
    ...     check_url,
    ...     add_health_routes,
    ... )
    >>>
    >>> # Create registry with checks
    >>> registry = HealthRegistry()
    >>> registry.add("database", check_database(os.getenv("DATABASE_URL")))
    >>> registry.add("redis", check_redis(os.getenv("REDIS_URL")))
    >>> registry.add("api", check_url("http://api-service:8080/health"))
    >>>
    >>> # Add to FastAPI app
    >>> add_health_routes(app, registry)
    >>>
    >>> # Or wait for dependencies at startup
    >>> await registry.wait_until_healthy(timeout=60, interval=2)
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx


class HealthStatus(StrEnum):
    """Health check status values."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"  # Partially working
    UNKNOWN = "unknown"  # Check hasn't run yet


@dataclass
class HealthCheckResult:
    """Result of a single health check."""

    name: str
    status: HealthStatus
    latency_ms: float
    message: str | None = None
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "name": self.name,
            "status": self.status,
            "latency_ms": round(self.latency_ms, 2),
        }
        if self.message:
            result["message"] = self.message
        if self.details:
            result["details"] = self.details
        return result


# Type alias for health check functions
HealthCheckFn = Callable[[], Awaitable[HealthCheckResult]]


@dataclass
class HealthCheck:
    """Registered health check with metadata."""

    name: str
    check_fn: HealthCheckFn
    critical: bool = True  # If False, failure doesn't fail overall health
    timeout: float = 5.0  # Timeout in seconds


class HealthRegistry:
    """Registry of health checks for a service.

    The registry manages multiple health checks and provides methods to:
    - Run all checks and aggregate results
    - Wait for all critical checks to pass (startup probe)
    - Determine overall service health

    Example:
        >>> registry = HealthRegistry()
        >>> registry.add("database", check_database(db_url), critical=True)
        >>> registry.add("cache", check_redis(redis_url), critical=False)
        >>>
        >>> # Run all checks
        >>> result = await registry.check_all()
        >>> print(result.status)  # "healthy" or "unhealthy"
        >>>
        >>> # Wait for startup
        >>> await registry.wait_until_healthy(timeout=60)
    """

    def __init__(self) -> None:
        """Initialize empty health registry."""
        self._checks: dict[str, HealthCheck] = {}

    def add(
        self,
        name: str,
        check_fn: HealthCheckFn,
        *,
        critical: bool = True,
        timeout: float = 5.0,
    ) -> None:
        """
        Register a health check.

        Args:
            name: Unique name for this check (e.g., "database", "redis")
            check_fn: Async function that returns HealthCheckResult
            critical: If True, failure means service is unhealthy
            timeout: Maximum time to wait for this check (seconds)

        Raises:
            ValueError: If a check with this name already exists
        """
        if name in self._checks:
            raise ValueError(f"Health check '{name}' already registered")
        self._checks[name] = HealthCheck(
            name=name,
            check_fn=check_fn,
            critical=critical,
            timeout=timeout,
        )

    def remove(self, name: str) -> bool:
        """
        Remove a health check by name.

        Args:
            name: Name of the check to remove

        Returns:
            True if check was removed, False if not found
        """
        if name in self._checks:
            del self._checks[name]
            return True
        return False

    def clear(self) -> None:
        """Remove all registered health checks."""
        self._checks.clear()

    @property
    def checks(self) -> list[HealthCheck]:
        """Get list of all registered checks."""
        return list(self._checks.values())

    async def check_one(self, name: str) -> HealthCheckResult:
        """
        Run a single health check by name.

        Args:
            name: Name of the check to run

        Returns:
            HealthCheckResult for the check

        Raises:
            KeyError: If check not found
        """
        if name not in self._checks:
            raise KeyError(f"Health check '{name}' not found")

        check = self._checks[name]
        start = time.perf_counter()

        try:
            result = await asyncio.wait_for(check.check_fn(), timeout=check.timeout)
            # Update latency from our timing
            result.latency_ms = (time.perf_counter() - start) * 1000
            return result
        except TimeoutError:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                latency_ms=(time.perf_counter() - start) * 1000,
                message=f"Check timed out after {check.timeout}s",
            )
        except Exception as e:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                latency_ms=(time.perf_counter() - start) * 1000,
                message=str(e),
            )

    async def check_all(self) -> AggregatedHealthResult:
        """
        Run all registered health checks concurrently.

        Returns:
            AggregatedHealthResult with overall status and individual results
        """
        if not self._checks:
            return AggregatedHealthResult(
                status=HealthStatus.HEALTHY,
                checks=[],
                message="No health checks registered",
            )

        # Run all checks concurrently
        check_names = list(self._checks.keys())
        results = await asyncio.gather(
            *[self.check_one(name) for name in check_names],
            return_exceptions=False,
        )

        # Determine overall status
        # - All critical checks must pass for HEALTHY
        # - If any critical check fails, UNHEALTHY
        # - If only non-critical checks fail, DEGRADED
        critical_failed = False
        non_critical_failed = False

        for registered_name, result in zip(check_names, results):
            check = self._checks.get(registered_name)
            if result.status == HealthStatus.UNHEALTHY:
                if check and check.critical:
                    critical_failed = True
                else:
                    non_critical_failed = True

        if critical_failed:
            overall_status = HealthStatus.UNHEALTHY
        elif non_critical_failed:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY

        return AggregatedHealthResult(
            status=overall_status,
            checks=results,
        )

    async def wait_until_healthy(
        self,
        *,
        timeout: float = 60.0,
        interval: float = 2.0,
        check_names: list[str] | None = None,
    ) -> bool:
        """
        Wait until all (or specified) critical checks pass.

        Useful for startup scripts to wait for dependencies before
        the main application starts accepting traffic.

        Args:
            timeout: Maximum time to wait (seconds)
            interval: Time between check attempts (seconds)
            check_names: Specific checks to wait for (None = all critical)

        Returns:
            True if all checks passed, False if timeout reached

        Example:
            >>> # Wait up to 60 seconds for database
            >>> if not await registry.wait_until_healthy(timeout=60):
            ...     raise RuntimeError("Dependencies not ready")
        """
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if check_names:
                # Check specific checks
                all_healthy = True
                for name in check_names:
                    try:
                        check_result = await self.check_one(name)
                        if check_result.status == HealthStatus.UNHEALTHY:
                            all_healthy = False
                            break
                    except KeyError:
                        all_healthy = False
                        break
            else:
                # Check all critical checks
                agg_result = await self.check_all()
                all_healthy = agg_result.status in (
                    HealthStatus.HEALTHY,
                    HealthStatus.DEGRADED,
                )

            if all_healthy:
                return True

            # Wait before next attempt
            remaining = deadline - time.monotonic()
            await asyncio.sleep(min(interval, max(0, remaining)))

        return False


@dataclass
class AggregatedHealthResult:
    """Aggregated result from multiple health checks."""

    status: HealthStatus
    checks: list[HealthCheckResult] = field(default_factory=list)
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "status": self.status,
            "checks": [c.to_dict() for c in self.checks],
        }
        if self.message:
            result["message"] = self.message
        return result


# =============================================================================
# Built-in Health Check Functions
# =============================================================================


def check_database(url: str | None) -> HealthCheckFn:
    """
    Create a health check for a PostgreSQL database.

    Uses a simple "SELECT 1" query to verify connectivity.

    Args:
        url: Database URL (postgres:// or postgresql://)

    Returns:
        Async health check function

    Example:
        >>> check = check_database(os.getenv("DATABASE_URL"))
        >>> registry.add("database", check, critical=True)
    """

    async def _check() -> HealthCheckResult:
        if not url:
            return HealthCheckResult(
                name="database",
                status=HealthStatus.UNHEALTHY,
                latency_ms=0,
                message="DATABASE_URL not configured",
            )

        start = time.perf_counter()
        try:
            # Use asyncpg directly for lightweight check
            import asyncpg

            # Normalize URL for asyncpg
            db_url = url
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
            if "+asyncpg" in db_url:
                db_url = db_url.replace("+asyncpg", "")

            conn = await asyncio.wait_for(
                asyncpg.connect(db_url),
                timeout=5.0,
            )
            try:
                await conn.fetchval("SELECT 1")
            finally:
                await conn.close()

            return HealthCheckResult(
                name="database",
                status=HealthStatus.HEALTHY,
                latency_ms=(time.perf_counter() - start) * 1000,
            )
        except TimeoutError:
            return HealthCheckResult(
                name="database",
                status=HealthStatus.UNHEALTHY,
                latency_ms=(time.perf_counter() - start) * 1000,
                message="Connection timeout",
            )
        except ImportError:
            # asyncpg not installed, try with httpx to a hypothetical health endpoint
            return HealthCheckResult(
                name="database",
                status=HealthStatus.UNKNOWN,
                latency_ms=0,
                message="asyncpg not installed",
            )
        except Exception as e:
            return HealthCheckResult(
                name="database",
                status=HealthStatus.UNHEALTHY,
                latency_ms=(time.perf_counter() - start) * 1000,
                message=str(e),
            )

    return _check


def check_redis(url: str | None) -> HealthCheckFn:
    """
    Create a health check for Redis.

    Uses PING command to verify connectivity.

    Args:
        url: Redis URL (redis://)

    Returns:
        Async health check function

    Example:
        >>> check = check_redis(os.getenv("REDIS_URL"))
        >>> registry.add("redis", check, critical=False)
    """

    async def _check() -> HealthCheckResult:
        if not url:
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                latency_ms=0,
                message="REDIS_URL not configured",
            )

        start = time.perf_counter()
        try:
            import redis.asyncio as redis_async

            client = redis_async.from_url(url, socket_connect_timeout=5.0)
            try:
                pong = await asyncio.wait_for(client.ping(), timeout=5.0)
                if pong:
                    return HealthCheckResult(
                        name="redis",
                        status=HealthStatus.HEALTHY,
                        latency_ms=(time.perf_counter() - start) * 1000,
                    )
                else:
                    return HealthCheckResult(
                        name="redis",
                        status=HealthStatus.UNHEALTHY,
                        latency_ms=(time.perf_counter() - start) * 1000,
                        message="PING returned False",
                    )
            finally:
                await client.aclose()
        except TimeoutError:
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                latency_ms=(time.perf_counter() - start) * 1000,
                message="Connection timeout",
            )
        except ImportError:
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.UNKNOWN,
                latency_ms=0,
                message="redis-py not installed",
            )
        except Exception as e:
            return HealthCheckResult(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                latency_ms=(time.perf_counter() - start) * 1000,
                message=str(e),
            )

    return _check


def check_url(
    url: str,
    *,
    method: str = "GET",
    expected_status: int = 200,
    timeout: float = 5.0,
    headers: dict[str, str] | None = None,
) -> HealthCheckFn:
    """
    Create a health check for an HTTP endpoint.

    Args:
        url: URL to check
        method: HTTP method (default: GET)
        expected_status: Expected HTTP status code (default: 200)
        timeout: Request timeout in seconds
        headers: Optional headers to include

    Returns:
        Async health check function

    Example:
        >>> check = check_url("http://api:8080/health")
        >>> registry.add("api", check)
        >>>
        >>> # With custom options
        >>> check = check_url(
        ...     "http://service:8080/ready",
        ...     expected_status=204,
        ...     headers={"Authorization": "Bearer token"},
        ... )
    """
    # Extract name from URL for the result
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        name = parsed.netloc.split(":")[0]
    except Exception:
        name = "http"

    async def _check() -> HealthCheckResult:
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                )

                if response.status_code == expected_status:
                    return HealthCheckResult(
                        name=name,
                        status=HealthStatus.HEALTHY,
                        latency_ms=(time.perf_counter() - start) * 1000,
                        details={"status_code": response.status_code},
                    )
                else:
                    return HealthCheckResult(
                        name=name,
                        status=HealthStatus.UNHEALTHY,
                        latency_ms=(time.perf_counter() - start) * 1000,
                        message=f"Expected status {expected_status}, got {response.status_code}",
                        details={"status_code": response.status_code},
                    )
        except httpx.TimeoutException:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                latency_ms=(time.perf_counter() - start) * 1000,
                message=f"Request timeout after {timeout}s",
            )
        except httpx.ConnectError as e:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                latency_ms=(time.perf_counter() - start) * 1000,
                message=f"Connection failed: {e}",
            )
        except Exception as e:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                latency_ms=(time.perf_counter() - start) * 1000,
                message=str(e),
            )

    return _check


def check_tcp(
    host: str,
    port: int,
    *,
    timeout: float = 5.0,
) -> HealthCheckFn:
    """
    Create a health check for a TCP port.

    Useful for checking if a service is listening on a port
    without needing protocol-specific logic.

    Args:
        host: Hostname or IP address
        port: Port number
        timeout: Connection timeout in seconds

    Returns:
        Async health check function

    Example:
        >>> check = check_tcp("database", 5432)
        >>> registry.add("postgres-port", check)
    """
    name = f"{host}:{port}"

    async def _check() -> HealthCheckResult:
        start = time.perf_counter()
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=timeout,
            )
            writer.close()
            await writer.wait_closed()

            return HealthCheckResult(
                name=name,
                status=HealthStatus.HEALTHY,
                latency_ms=(time.perf_counter() - start) * 1000,
            )
        except TimeoutError:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                latency_ms=(time.perf_counter() - start) * 1000,
                message=f"Connection timeout after {timeout}s",
            )
        except OSError as e:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                latency_ms=(time.perf_counter() - start) * 1000,
                message=str(e),
            )

    return _check


# =============================================================================
# FastAPI Integration
# =============================================================================


def add_health_routes(
    app: Any,  # FastAPI
    registry: HealthRegistry,
    *,
    prefix: str = "/_health",
    include_in_schema: bool = False,
    detailed_on_failure: bool = True,
) -> None:
    """
    Add health check routes to a FastAPI application.

    Creates three endpoints:
    - `/_health/live` - Liveness probe (always returns 200)
    - `/_health/ready` - Readiness probe (runs all checks)
    - `/_health/startup` - Startup probe (runs critical checks)

    Args:
        app: FastAPI application instance
        registry: HealthRegistry with registered checks
        prefix: URL prefix for health routes
        include_in_schema: Include in OpenAPI schema
        detailed_on_failure: Include check details in error responses

    Example:
        >>> from fastapi import FastAPI
        >>> from svc_infra.health import HealthRegistry, check_database, add_health_routes
        >>>
        >>> app = FastAPI()
        >>> registry = HealthRegistry()
        >>> registry.add("database", check_database(os.getenv("DATABASE_URL")))
        >>> add_health_routes(app, registry)
    """
    from starlette.responses import JSONResponse

    from svc_infra.api.fastapi.dual.public import public_router

    router = public_router(
        prefix=prefix,
        tags=["health"],
        include_in_schema=include_in_schema,
    )

    @router.get("/live")
    async def liveness() -> JSONResponse:
        """Liveness probe - always returns 200 if process is running."""
        return JSONResponse({"status": "ok"})

    @router.get("/ready")
    async def readiness() -> JSONResponse:
        """Readiness probe - checks all dependencies."""
        result = await registry.check_all()

        if result.status == HealthStatus.HEALTHY:
            return JSONResponse(result.to_dict(), status_code=200)
        elif result.status == HealthStatus.DEGRADED:
            # Degraded is still ready, but indicate the issue
            return JSONResponse(result.to_dict(), status_code=200)
        else:
            if detailed_on_failure:
                return JSONResponse(result.to_dict(), status_code=503)
            else:
                return JSONResponse({"status": "unhealthy"}, status_code=503)

    @router.get("/startup")
    async def startup() -> JSONResponse:
        """Startup probe - checks critical dependencies only."""
        result = await registry.check_all()

        # For startup, only critical checks matter
        critical_healthy = result.status in (
            HealthStatus.HEALTHY,
            HealthStatus.DEGRADED,
        )

        if critical_healthy:
            return JSONResponse({"status": "ok"}, status_code=200)
        else:
            if detailed_on_failure:
                return JSONResponse(result.to_dict(), status_code=503)
            else:
                return JSONResponse({"status": "unhealthy"}, status_code=503)

    @router.get("/checks/{name}")
    async def check_single(name: str) -> JSONResponse:
        """Run a single health check by name."""
        try:
            result = await registry.check_one(name)
            status_code = 200 if result.status == HealthStatus.HEALTHY else 503
            return JSONResponse(result.to_dict(), status_code=status_code)
        except KeyError:
            return JSONResponse(
                {"error": f"Health check '{name}' not found"},
                status_code=404,
            )

    app.include_router(router)


def add_startup_probe(
    app: Any,  # FastAPI
    checks: list[HealthCheckFn],
    *,
    timeout: float = 60.0,
    interval: float = 2.0,
) -> None:
    """
    Add a startup event that waits for dependencies.

    This is useful for ensuring the database, cache, and other
    dependencies are ready before the application starts accepting traffic.

    Args:
        app: FastAPI application instance
        checks: List of health check functions to wait for
        timeout: Maximum time to wait for all checks (seconds)
        interval: Time between check attempts (seconds)

    Raises:
        RuntimeError: If dependencies aren't ready within timeout

    Example:
        >>> from fastapi import FastAPI
        >>> from svc_infra.health import check_database, check_redis, add_startup_probe
        >>>
        >>> app = FastAPI()
        >>> add_startup_probe(
        ...     app,
        ...     checks=[
        ...         check_database(os.getenv("DATABASE_URL")),
        ...         check_redis(os.getenv("REDIS_URL")),
        ...     ],
        ...     timeout=60,
        ... )
    """
    registry = HealthRegistry()
    for i, check in enumerate(checks):
        registry.add(f"startup_{i}", check, critical=True)

    @app.on_event("startup")
    async def _wait_for_dependencies() -> None:
        import logging

        logger = logging.getLogger("svc_infra.health")
        logger.info(f"Waiting for {len(checks)} dependencies (timeout={timeout}s)...")

        if await registry.wait_until_healthy(timeout=timeout, interval=interval):
            logger.info("All dependencies ready")
        else:
            # Log which checks failed
            result = await registry.check_all()
            failed = [c.name for c in result.checks if c.status == HealthStatus.UNHEALTHY]
            error_msg = f"Dependencies not ready after {timeout}s: {failed}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)


def add_dependency_health(
    app: Any,  # FastAPI
    name: str,
    check_fn: HealthCheckFn,
    *,
    critical: bool = True,
) -> None:
    """
    Register a dependency health check on an existing app.

    This adds the check to the app's health registry if one exists,
    or creates a new one.

    Args:
        app: FastAPI application instance
        name: Name for the health check
        check_fn: Async function that returns HealthCheckResult
        critical: Whether failure means service is unhealthy

    Example:
        >>> # Add checks incrementally
        >>> add_dependency_health(app, "database", check_database(db_url))
        >>> add_dependency_health(app, "cache", check_redis(redis_url), critical=False)
    """
    # Get or create registry on app state
    if not hasattr(app, "state"):
        raise ValueError("App must have a 'state' attribute (FastAPI/Starlette)")

    if not hasattr(app.state, "_health_registry"):
        app.state._health_registry = HealthRegistry()
        # Add routes for the registry
        add_health_routes(app, app.state._health_registry)

    app.state._health_registry.add(name, check_fn, critical=critical)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Status types
    "HealthStatus",
    "HealthCheckResult",
    "HealthCheck",
    "HealthCheckFn",
    "AggregatedHealthResult",
    # Registry
    "HealthRegistry",
    # Built-in checks
    "check_database",
    "check_redis",
    "check_url",
    "check_tcp",
    # FastAPI integration
    "add_health_routes",
    "add_startup_probe",
    "add_dependency_health",
]
