"""
Common test utilities and helpers for svc-infra tests.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from unittest.mock import Mock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


def create_mock_object(mocker, **kwargs) -> Mock:
    """Create a mock object with proper attribute values."""
    mock_obj = mocker.Mock()
    for key, value in kwargs.items():
        setattr(mock_obj, key, value)
    return mock_obj


def create_mock_user(mocker, **kwargs) -> Mock:
    """Create a mock user object with common attributes."""
    defaults = {
        "id": "test-user-id",
        "email": "test@example.com",
        "is_active": True,
        "is_verified": True,
        "hashed_password": "$2b$12$dummy.hash.here",
        "roles": [],
    }
    defaults.update(kwargs)
    return create_mock_object(mocker, **defaults)


def create_mock_api_key(mocker, **kwargs) -> Mock:
    """Create a mock API key object with common attributes."""
    defaults = {
        "id": "test-api-key-id",
        "key_prefix": "ak_test_123",
        "key_hash": "hashed_key_value",
        "active": True,
        "expires_at": None,
        "scopes": [],
        "user": None,
    }
    defaults.update(kwargs)
    return create_mock_object(mocker, **defaults)


def create_mock_principal(mocker, **kwargs) -> Mock:
    """Create a mock Principal object."""
    defaults = {
        "user": create_mock_user(mocker),
        "scopes": [],
        "via": "jwt",
        "api_key": None,
    }
    defaults.update(kwargs)
    return create_mock_object(mocker, **defaults)


async def create_test_client(app: FastAPI) -> AsyncClient:
    """Create an async test client for the given FastAPI app."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


def assert_json_response(
    response_data: Dict[str, Any], expected_status: int = 200
) -> None:
    """Assert that a response has the expected JSON structure."""
    assert isinstance(response_data, dict)
    # Add more specific assertions as needed


def assert_error_response(
    response_data: Dict[str, Any],
    expected_status: int,
    error_code: Optional[str] = None,
) -> None:
    """Assert that a response is an error response."""
    assert "detail" in response_data
    if error_code:
        assert response_data["detail"] == error_code


class MockDatabaseSession:
    """Mock database session for testing."""

    def __init__(self):
        self._data = {}
        self._queries = []

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


def setup_auth_mocks(app: FastAPI, mocker, user=None, api_key=None, principal=None):
    """Set up authentication mocks for testing."""
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


def setup_database_mocks(app: FastAPI):
    """Set up database session mocks for testing."""
    from svc_infra.api.fastapi.db.sql.session import get_session

    mock_session = MockDatabaseSession()

    async def _mock_session():
        return mock_session

    app.dependency_overrides[get_session] = _mock_session
    return mock_session
