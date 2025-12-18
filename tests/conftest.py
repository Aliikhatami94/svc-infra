"""
Root conftest.py for svc-infra tests.

This file provides:
1. Common pytest markers for test categorization
2. Shared fixtures used across multiple test modules
3. Common mock helpers and utilities

Fixtures are organized by category:
- Database fixtures (SQL, NoSQL)
- Auth fixtures (users, principals, API keys)
- Cache fixtures (Redis, in-memory)
- API fixtures (FastAPI app, client)
"""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================


def pytest_collection_modifyitems(config, items):
    """Automatically mark security-related tests so `-m security` selects them.

    We tag tests under `tests/security/` and `tests/auth/` with the `security` marker.
    """
    for item in items:
        path = str(item.fspath)
        # Normalize separators just in case
        norm = path.replace("\\", "/")
        if "/tests/security/" in norm or "/tests/auth/" in norm:
            item.add_marker(pytest.mark.security)
        # Include API tests that assert rate limiting / request-size or metrics hooks
        if "/tests/api/" in norm and (
            "rate_limit" in norm or "request_size" in norm or "metrics_hooks" in norm
        ):
            item.add_marker(pytest.mark.security)
            # Also mark as ratelimit when appropriate
            if "rate_limit" in norm or "metrics_hooks" in norm:
                item.add_marker(pytest.mark.ratelimit)
        # Directly mark ratelimit tests anywhere in the path containing 'rate_limit'
        if "rate_limit" in norm:
            item.add_marker(pytest.mark.ratelimit)

        # Mark tenancy-related tests (either under a tenancy folder or filename contains 'tenant')
        if "/tests/tenancy/" in norm or "tenant" in norm:
            item.add_marker(pytest.mark.tenancy)


def pytest_configure(config):
    # Ensure custom markers are registered even if pyproject.toml isn't picked up in some contexts
    for name, desc in [
        ("security", "Security and auth hardening tests"),
        ("ratelimit", "Rate limiting and abuse protection tests"),
        ("concurrency", "Idempotency and concurrency control tests"),
        ("jobs", "Background jobs and scheduling tests"),
        ("webhooks", "Webhooks framework tests"),
        ("billing", "Billing primitives tests"),
        ("tenancy", "Tenancy isolation and enforcement tests"),
        ("data_lifecycle", "Data lifecycle (fixtures, retention, erasure, backups)"),
        ("ops", "SLOs & Ops tests (probes, breaker, instrumentation)"),
        ("dx", "Developer experience and quality gates tests"),
    ]:
        config.addinivalue_line("markers", f"{name}: {desc}")


# =============================================================================
# MOCK DATABASE SESSION
# =============================================================================


class MockDatabaseSession:
    """Mock database session for testing.

    This mock session provides a consistent interface for testing database
    operations without requiring a real database connection.

    Usage in tests:
        @pytest.fixture
        def session(mock_sql_session):
            return mock_sql_session
    """

    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._queries: list = []

    async def execute(self, query):
        """Mock query execution."""
        self._queries.append(query)

        class MockResult:
            def scalars(self):
                return self

            def all(self):
                return []

            def first(self):
                return None

            def scalar_one_or_none(self):
                return None

            def __iter__(self):
                return iter([])

        return MockResult()

    async def get(self, model, id):
        """Mock get operation."""
        return self._data.get(f"{model.__name__}:{id}")

    async def add(self, instance):
        """Mock add operation."""
        model_name = instance.__class__.__name__
        instance_id = getattr(instance, "id", "unknown")
        self._data[f"{model_name}:{instance_id}"] = instance

    def add_sync(self, instance):
        """Mock synchronous add operation (SQLAlchemy Session.add is sync)."""
        model_name = instance.__class__.__name__
        instance_id = getattr(instance, "id", "unknown")
        self._data[f"{model_name}:{instance_id}"] = instance

    async def delete(self, instance):
        """Mock delete operation."""
        model_name = instance.__class__.__name__
        instance_id = getattr(instance, "id", "unknown")
        self._data.pop(f"{model_name}:{instance_id}", None)

    async def commit(self):
        """Mock commit operation."""
        pass

    async def rollback(self):
        """Mock rollback operation."""
        pass

    async def flush(self):
        """Mock flush operation."""
        pass

    async def close(self):
        """Mock close operation."""
        pass


# =============================================================================
# DATABASE FIXTURES
# =============================================================================


@pytest.fixture
def mock_sql_session() -> MockDatabaseSession:
    """Create a mock SQL database session.

    This fixture provides a MockDatabaseSession that can be used as a
    dependency override for get_session in tests.

    Example:
        def test_something(mock_sql_session):
            # Use directly or override dependency
            app.dependency_overrides[get_session] = lambda: mock_sql_session
    """
    return MockDatabaseSession()


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client for testing.

    Returns a Mock object with common Redis operations as AsyncMock methods.
    """
    client = Mock()
    client.get = AsyncMock()
    client.set = AsyncMock()
    client.delete = AsyncMock()
    client.exists = AsyncMock()
    client.flushdb = AsyncMock()
    client.ping = AsyncMock(return_value=True)
    client.close = AsyncMock()
    client.incr = AsyncMock()
    client.expire = AsyncMock()
    client.ttl = AsyncMock()
    client.keys = AsyncMock(return_value=[])
    return client


# =============================================================================
# AUTH FIXTURES
# =============================================================================


def create_mock_user(mocker=None, **kwargs) -> Mock:
    """Create a mock user object with common attributes.

    Args:
        mocker: Optional pytest-mock mocker fixture
        **kwargs: Override default user attributes

    Returns:
        Mock user object with id, email, is_active, is_verified, etc.
    """
    mock = mocker.Mock() if mocker else Mock()
    defaults = {
        "id": "test-user-id",
        "email": "test@example.com",
        "is_active": True,
        "is_verified": True,
        "hashed_password": "$2b$12$dummy.hash.here",
        "roles": [],
    }
    defaults.update(kwargs)
    for key, value in defaults.items():
        setattr(mock, key, value)
    return mock


def create_mock_api_key(mocker=None, user=None, **kwargs) -> Mock:
    """Create a mock API key object with common attributes.

    Args:
        mocker: Optional pytest-mock mocker fixture
        user: Optional user to associate with the API key
        **kwargs: Override default API key attributes

    Returns:
        Mock API key object
    """
    mock = mocker.Mock() if mocker else Mock()
    defaults = {
        "id": "test-api-key-id",
        "key_prefix": "ak_test_123",
        "key_hash": "hashed_key_value",
        "active": True,
        "expires_at": None,
        "scopes": [],
        "user": user,
    }
    defaults.update(kwargs)
    for key, value in defaults.items():
        setattr(mock, key, value)
    return mock


def create_mock_principal(mocker=None, user=None, api_key=None, **kwargs) -> Mock:
    """Create a mock Principal object.

    Args:
        mocker: Optional pytest-mock mocker fixture
        user: User associated with the principal
        api_key: Optional API key associated with the principal
        **kwargs: Override default principal attributes

    Returns:
        Mock Principal object
    """
    mock = mocker.Mock() if mocker else Mock()
    defaults = {
        "user": user or create_mock_user(mocker),
        "scopes": [],
        "via": "jwt",
        "api_key": api_key,
    }
    defaults.update(kwargs)
    for key, value in defaults.items():
        setattr(mock, key, value)
    return mock


@pytest.fixture
def mock_user(mocker) -> Mock:
    """Create a mock user for testing."""
    return create_mock_user(mocker)


@pytest.fixture
def mock_api_key(mocker, mock_user) -> Mock:
    """Create a mock API key for testing."""
    return create_mock_api_key(mocker, user=mock_user)


@pytest.fixture
def mock_principal(mocker, mock_user, mock_api_key) -> Mock:
    """Create a mock principal for testing."""
    return create_mock_principal(mocker, user=mock_user, api_key=mock_api_key)


# =============================================================================
# AUTH SETUP HELPERS
# =============================================================================


def setup_auth_mocks(app: FastAPI, mocker, user=None, api_key=None, principal=None):
    """Set up authentication mocks for a FastAPI app.

    This helper overrides all auth-related dependencies to bypass
    authentication in tests.

    Args:
        app: FastAPI application
        mocker: pytest-mock mocker fixture
        user: Optional mock user (created if not provided)
        api_key: Optional mock API key (created if not provided)
        principal: Optional mock principal (created if not provided)

    Returns:
        Tuple of (user, api_key, principal)

    Example:
        @pytest.fixture
        def app(mocker):
            app = FastAPI()
            setup_auth_mocks(app, mocker)
            return app
    """
    from svc_infra.api.fastapi.auth.security import (
        _current_principal,
        _optional_principal,
        resolve_api_key,
        resolve_bearer_or_cookie_principal,
    )

    # Create default mocks if not provided
    if user is None:
        user = create_mock_user(mocker)
    if api_key is None:
        api_key = create_mock_api_key(mocker, user=user)
    if principal is None:
        principal = create_mock_principal(mocker, user=user, api_key=api_key)

    # Mock principal resolution
    async def _mock_principal():
        return principal

    async def _mock_optional_principal():
        return principal

    async def _mock_resolve_api_key(*args, **kwargs):
        return principal

    async def _mock_resolve_bearer_or_cookie(*args, **kwargs):
        return principal

    # Override dependencies
    app.dependency_overrides[_current_principal] = _mock_principal
    app.dependency_overrides[_optional_principal] = _mock_optional_principal
    app.dependency_overrides[resolve_api_key] = _mock_resolve_api_key
    app.dependency_overrides[resolve_bearer_or_cookie_principal] = (
        _mock_resolve_bearer_or_cookie
    )

    return user, api_key, principal


def setup_database_mocks(app: FastAPI) -> MockDatabaseSession:
    """Set up database session mocks for a FastAPI app.

    This helper overrides the get_session dependency to use a MockDatabaseSession.

    Args:
        app: FastAPI application

    Returns:
        The MockDatabaseSession instance used for the override

    Example:
        @pytest.fixture
        def app():
            app = FastAPI()
            mock_session = setup_database_mocks(app)
            return app
    """
    from svc_infra.api.fastapi.db.sql.session import get_session

    mock_session = MockDatabaseSession()

    async def _mock_session():
        return mock_session

    app.dependency_overrides[get_session] = _mock_session
    return mock_session


def setup_tenancy_mocks(app: FastAPI, tenant_id: str = "t_test"):
    """Set up tenancy mocks for a FastAPI app.

    Args:
        app: FastAPI application
        tenant_id: The tenant ID to return (default: "t_test")

    Example:
        @pytest.fixture
        def app():
            app = FastAPI()
            setup_tenancy_mocks(app, tenant_id="my-tenant")
            return app
    """
    from svc_infra.api.fastapi.tenancy.context import require_tenant_id

    async def _tenant():
        return tenant_id

    app.dependency_overrides[require_tenant_id] = _tenant


# =============================================================================
# FASTAPI APP FIXTURES
# =============================================================================


@pytest_asyncio.fixture
async def base_test_app(mocker) -> FastAPI:
    """Create a base FastAPI app with error handlers and middleware.

    This fixture provides a minimal FastAPI app with:
    - CatchAllExceptionMiddleware
    - Error handlers registered
    - Auth mocks set up
    - Database mocks set up

    Use this as a base for more specific test apps.
    """
    app = FastAPI(title="Test App")

    # Add error handlers
    from svc_infra.api.fastapi.middleware.errors.catchall import (
        CatchAllExceptionMiddleware,
    )
    from svc_infra.api.fastapi.middleware.errors.handlers import register_error_handlers

    app.add_middleware(CatchAllExceptionMiddleware)
    register_error_handlers(app)

    # Set up database and auth mocks
    setup_database_mocks(app)
    setup_auth_mocks(app, mocker)

    return app


@pytest_asyncio.fixture
async def test_client(base_test_app: FastAPI) -> AsyncClient:
    """Create an async test client for the base test app."""
    transport = ASGITransport(app=base_test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


# =============================================================================
# ENVIRONMENT FIXTURES
# =============================================================================


@pytest.fixture
def local_env(monkeypatch):
    """Set environment to LOCAL for permissive auth testing.

    This fixture sets CURRENT_ENVIRONMENT to LOCAL_ENV so that
    user/protected routers don't enforce strict auth.
    """
    from svc_infra.app import env as env_mod

    monkeypatch.setattr(
        env_mod, "CURRENT_ENVIRONMENT", env_mod.LOCAL_ENV, raising=False
    )


# =============================================================================
# SAMPLE DATA FIXTURES
# =============================================================================


@pytest.fixture
def sample_user_data() -> Dict[str, Any]:
    """Provide sample user data for testing."""
    return {
        "id": "user_123",
        "email": "test@example.com",
        "name": "Test User",
        "is_active": True,
    }


@pytest.fixture
def sample_tenant_data() -> Dict[str, Any]:
    """Provide sample tenant data for testing."""
    return {
        "id": "tenant_123",
        "name": "Test Tenant",
        "slug": "test-tenant",
        "is_active": True,
    }


@pytest.fixture
def sample_api_response_data() -> Dict[str, Any]:
    """Provide sample API response data for testing."""
    return {
        "user": {
            "id": "user_123",
            "email": "test@example.com",
            "name": "Test User",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
        },
        "status": "success",
    }
