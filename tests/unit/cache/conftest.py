"""
Caching test fixtures and configuration.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.fixture
def mock_cache_backend():
    """Create a mock cache backend for testing."""
    backend = Mock()
    backend.get = AsyncMock()
    backend.set = AsyncMock()
    backend.delete = AsyncMock()
    backend.exists = AsyncMock()
    backend.clear = AsyncMock()
    backend.ping = AsyncMock(return_value=True)
    return backend


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client for testing."""
    client = Mock()
    client.get = AsyncMock()
    client.set = AsyncMock()
    client.delete = AsyncMock()
    client.exists = AsyncMock()
    client.flushdb = AsyncMock()
    client.ping = AsyncMock(return_value=True)
    client.close = AsyncMock()
    return client


@pytest.fixture
def sample_cache_data():
    """Provide sample cache data for testing."""
    return {
        "user:123": {"id": 123, "name": "Test User", "email": "test@example.com"},
        "product:456": {"id": 456, "name": "Test Product", "price": 1999},
        "session:789": {"user_id": 123, "expires_at": "2023-12-31T23:59:59Z"},
    }


@pytest.fixture
def cache_key_templates():
    """Provide cache key templates for testing."""
    return {
        "user_profile": "user:{user_id}:profile",
        "user_permissions": "user:{user_id}:permissions:{role}",
        "product_details": "product:{product_id}:details",
        "session_data": "session:{session_id}",
    }


@pytest.fixture
def cache_tags():
    """Provide cache tags for testing."""
    return {
        "user": "user:{user_id}",
        "product": "product:{product_id}",
        "category": "category:{category_id}",
        "session": "session:{session_id}",
    }


@pytest.fixture(autouse=True)
def _cache_env(monkeypatch):
    """Set up caching environment for testing."""
    # Mock cache settings
    monkeypatch.setenv("CACHE_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("CACHE_PREFIX", "test")
    monkeypatch.setenv("CACHE_VERSION", "v1")
    monkeypatch.setenv("CACHE_TTL_SHORT", "30")
    monkeypatch.setenv("CACHE_TTL_DEFAULT", "300")
    monkeypatch.setenv("CACHE_TTL_LONG", "3600")

    # Mock cache backend initialization
    with patch("svc_infra.cache.backend.setup_cache") as mock_setup:
        mock_setup.return_value = None
        yield mock_setup


@pytest.fixture
def mock_cache_decorator():
    """Create a mock cache decorator for testing."""

    def decorator(*args, **kwargs):
        def wrapper(func):
            # Store original function and return it
            func._cache_config = kwargs
            return func

        return wrapper

    return decorator


@pytest.fixture
def mock_resource_cache():
    """Create a mock resource cache for testing."""

    class MockResource:
        def __init__(self, name: str, id_field: str):
            self.name = name
            self.id_field = id_field

        def cache_read(self, *, suffix: str, ttl: int, **kwargs):
            def decorator(func):
                func._cache_read_config = {"suffix": suffix, "ttl": ttl, **kwargs}
                return func

            return decorator

        def cache_write(self, **kwargs):
            def decorator(func):
                func._cache_write_config = kwargs
                return func

            return decorator

        def cache_delete(self, **kwargs):
            def decorator(func):
                func._cache_delete_config = kwargs
                return func

            return decorator

    return MockResource


@pytest.fixture
def cache_test_data():
    """Provide test data for cache operations."""
    return {
        "users": [
            {"id": 1, "name": "Alice", "email": "alice@example.com"},
            {"id": 2, "name": "Bob", "email": "bob@example.com"},
            {"id": 3, "name": "Charlie", "email": "charlie@example.com"},
        ],
        "products": [
            {"id": 101, "name": "Laptop", "price": 99999, "category_id": 1},
            {"id": 102, "name": "Mouse", "price": 2999, "category_id": 1},
            {"id": 103, "name": "Keyboard", "price": 7999, "category_id": 1},
        ],
        "categories": [
            {"id": 1, "name": "Electronics", "parent_id": None},
            {"id": 2, "name": "Clothing", "parent_id": None},
            {"id": 3, "name": "Books", "parent_id": None},
        ],
    }
