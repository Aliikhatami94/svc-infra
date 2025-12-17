"""
API test fixtures and configuration.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from tests.unit.utils.test_helpers import setup_auth_mocks, setup_database_mocks


@pytest_asyncio.fixture
async def api_app(mocker) -> FastAPI:
    """Create a FastAPI app for API testing."""
    app = FastAPI(title="API Test App")

    # Add error handlers
    from svc_infra.api.fastapi.middleware.errors.catchall import CatchAllExceptionMiddleware
    from svc_infra.api.fastapi.middleware.errors.handlers import register_error_handlers

    app.add_middleware(CatchAllExceptionMiddleware)
    register_error_handlers(app)

    # Set up database mocks
    setup_database_mocks(app)

    # Set up auth mocks
    setup_auth_mocks(app, mocker)

    return app


@pytest_asyncio.fixture
async def api_client(api_app: FastAPI) -> AsyncClient:
    """Create an async test client for API tests."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture
def mock_fastapi_app():
    """Create a mock FastAPI app for testing."""
    app = Mock()
    app.include_router = Mock()
    app.add_middleware = Mock()
    app.add_route = Mock()
    app.add_exception_handler = Mock()
    app.dependency_overrides = {}
    return app


@pytest.fixture
def mock_router():
    """Create a mock FastAPI router for testing."""
    router = Mock()
    router.get = Mock(return_value=router)
    router.post = Mock(return_value=router)
    router.put = Mock(return_value=router)
    router.delete = Mock(return_value=router)
    router.patch = Mock(return_value=router)
    router.add_api_route = Mock()
    router.include_router = Mock()
    return router


@pytest.fixture
def sample_api_request_data():
    """Provide sample API request data for testing."""
    return {
        "user": {
            "email": "test@example.com",
            "name": "Test User",
            "password": "test_password",
        },
        "product": {
            "name": "Test Product",
            "description": "A test product",
            "price": 1999,
            "category_id": "category_123",
        },
        "order": {
            "user_id": "user_123",
            "items": [{"product_id": "product_456", "quantity": 2, "price": 1999}],
            "total": 3998,
        },
    }


@pytest.fixture
def sample_api_response_data():
    """Provide sample API response data for testing."""
    return {
        "user": {
            "id": "user_123",
            "email": "test@example.com",
            "name": "Test User",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
        },
        "product": {
            "id": "product_456",
            "name": "Test Product",
            "description": "A test product",
            "price": 1999,
            "category_id": "category_123",
            "active": True,
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
        },
        "order": {
            "id": "order_789",
            "user_id": "user_123",
            "items": [
                {
                    "id": "item_1",
                    "product_id": "product_456",
                    "quantity": 2,
                    "price": 1999,
                    "total": 3998,
                }
            ],
            "total": 3998,
            "status": "pending",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
        },
    }


@pytest.fixture
def mock_middleware():
    """Create a mock middleware for testing."""

    class MockMiddleware:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            # Add custom headers or modify request/response
            async def modified_send(message):
                if message["type"] == "http.response.start":
                    message["headers"].append((b"x-middleware", b"applied"))
                await send(message)

            await self.app(scope, receive, modified_send)

    return MockMiddleware


@pytest.fixture
def mock_dependency():
    """Create a mock dependency for testing."""

    async def mock_dependency():
        return {"user_id": "test_user", "permissions": ["read", "write"]}

    return mock_dependency


@pytest.fixture(autouse=True)
def _api_env(monkeypatch):
    """Set up API environment for testing."""
    # Mock environment variables
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("API_PREFIX", "/api/v1")
