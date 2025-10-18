"""
Authentication test fixtures and configuration.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.unit.utils.test_helpers import (
    MockDatabaseSession,
    create_mock_api_key,
    create_mock_principal,
    create_mock_user,
    setup_auth_mocks,
    setup_database_mocks,
)


@pytest_asyncio.fixture
async def auth_app(mocker) -> FastAPI:
    """Create a FastAPI app with authentication setup for testing."""
    app = FastAPI(title="Auth Test App")

    # Add error handlers
    from svc_infra.api.fastapi.middleware.errors.catchall import CatchAllExceptionMiddleware
    from svc_infra.api.fastapi.middleware.errors.handlers import register_error_handlers

    app.add_middleware(CatchAllExceptionMiddleware)
    register_error_handlers(app)

    # Set up database mocks
    mock_session = setup_database_mocks(app)

    # Set up auth mocks
    user, api_key, principal = setup_auth_mocks(app, mocker)

    return app


@pytest_asyncio.fixture
async def auth_client(auth_app: FastAPI) -> AsyncClient:
    """Create an async test client for authentication tests."""
    transport = ASGITransport(app=auth_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture
def mock_user(mocker):
    """Create a mock user for testing."""
    return create_mock_user(mocker)


@pytest.fixture
def mock_api_key(mocker, mock_user):
    """Create a mock API key for testing."""
    return create_mock_api_key(mocker, user=mock_user)


@pytest.fixture
def mock_principal(mocker, mock_user, mock_api_key):
    """Create a mock principal for testing."""
    return create_mock_principal(mocker, user=mock_user, api_key=mock_api_key)


@pytest.fixture
def mock_database_session():
    """Create a mock database session for testing."""
    return MockDatabaseSession()


@pytest.fixture(autouse=True)
def _auth_env(monkeypatch):
    """Set up authentication environment for testing."""
    # Force LOCAL env for permissive auth in tests
    from svc_infra.app import env as env_mod

    monkeypatch.setattr(env_mod, "CURRENT_ENVIRONMENT", env_mod.LOCAL_ENV, raising=False)

    # Mock auth settings
    from svc_infra.api.fastapi.auth.settings import AuthSettings

    class MockAuthSettings:
        secret_key = "test-secret-key"
        auth_cookie_name = "auth_cookie"
        access_token_expire_minutes = 30
        refresh_token_expire_days = 7
        algorithm = "HS256"
        reset_password_token_secret = "reset-secret"
        verification_token_secret = "verify-secret"

    monkeypatch.setattr(
        "svc_infra.api.fastapi.auth.settings.get_auth_settings", lambda: MockAuthSettings()
    )
