"""
Tests for cache decorators functionality.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from svc_infra.cache.decorators import cache_read, cache_write, init_cache


@pytest.mark.asyncio
async def test_cache_read_uses_namespace_prefix(mocker):
    mocker.patch("svc_infra.cache.decorators._alias", return_value="svc")
    calls = []

    def fake_cache(ttl, key, *args, **kwargs):
        calls.append({"ttl": ttl, "key": key, "kwargs": kwargs})

        def decorator(func):
            async def wrapper(*f_args, **f_kwargs):
                return await func(*f_args, **f_kwargs)

            return wrapper

        return decorator

    mocker.patch("svc_infra.cache.decorators._cache.cache", side_effect=fake_cache)

    @cache_read(key="user:{user_id}", ttl=60)
    async def fetch_user(user_id: int):
        return {"id": user_id}

    result = await fetch_user(user_id=42)
    assert result == {"id": 42}
    assert calls[0]["kwargs"]["prefix"] == "svc"
    assert hasattr(fetch_user, "__svc_key_variants__")


@pytest.mark.asyncio
async def test_cache_read_falls_back_when_prefix_not_supported(mocker):
    mocker.patch("svc_infra.cache.decorators._alias", return_value="svc")
    call_order = []

    def fake_cache(ttl, key, *args, **kwargs):
        call_order.append({"key": key, "kwargs": kwargs})
        if "prefix" in kwargs:
            raise TypeError("prefix not supported")

        def decorator(func):
            async def wrapper(*f_args, **f_kwargs):
                return await func(*f_args, **f_kwargs)

            return wrapper

        return decorator

    mocker.patch("svc_infra.cache.decorators._cache.cache", side_effect=fake_cache)

    @cache_read(key="user:{user_id}", ttl=30)
    async def fetch(user_id: int):
        return {"id": user_id}

    data = await fetch(user_id=7)
    assert data["id"] == 7
    assert call_order[0]["kwargs"]["prefix"] == "svc"
    # Fallback should embed namespace into the key itself.
    assert call_order[1]["key"].startswith("svc:user:")


@pytest.mark.asyncio
async def test_cache_write_invalidates_tags_and_executes_recache(mocker):
    mocker.patch("svc_infra.cache.decorators.resolve_tags", return_value=["user:123"])
    invalidate = mocker.patch(
        "svc_infra.cache.decorators.invalidate_tags",
        new_callable=AsyncMock,
        return_value=1,
    )
    execute = mocker.patch("svc_infra.cache.decorators.execute_recache", new_callable=AsyncMock)

    recache_specs = [Mock(name="recache-spec")]

    @cache_write(tags=["user:{user_id}"], recache=recache_specs)
    async def update_user(user_id: int, data: dict[str, Any]):
        return {"updated": data, "user_id": user_id}

    result = await update_user(user_id=123, data={"name": "Alice"})

    assert result["updated"] == {"name": "Alice"}
    invalidate.assert_awaited_once_with("user:123")
    execute.assert_awaited_once_with(
        recache_specs,
        max_concurrency=5,
        user_id=123,
        data={"name": "Alice"},
    )


@pytest.mark.asyncio
async def test_cache_write_runs_recache_even_if_invalidation_fails(mocker):
    mocker.patch("svc_infra.cache.decorators.resolve_tags", return_value=["user:123"])
    mocker.patch(
        "svc_infra.cache.decorators.invalidate_tags",
        new_callable=AsyncMock,
        side_effect=RuntimeError("cache error"),
    )
    execute = mocker.patch("svc_infra.cache.decorators.execute_recache", new_callable=AsyncMock)

    @cache_write(tags=["user:{user_id}"], recache=[Mock()])
    async def update_user(user_id: int):
        return user_id

    assert await update_user(user_id=123) == 123
    execute.assert_awaited_once()


class TestCacheInitialization:
    def test_init_cache_default(self):
        with patch("svc_infra.cache.decorators._setup_cache") as mock_setup:
            init_cache()

        mock_setup.assert_called_once_with(url=None, prefix=None, version=None)

    def test_init_cache_with_parameters(self):
        with patch("svc_infra.cache.decorators._setup_cache") as mock_setup:
            init_cache(url="redis://localhost:6379/1", prefix="test_app", version="v2")

        mock_setup.assert_called_once_with(
            url="redis://localhost:6379/1", prefix="test_app", version="v2"
        )


@pytest.mark.asyncio
async def test_cached_alias_behaves_like_cache_read(mocker):
    from svc_infra.cache.decorators import cached

    mocker.patch("svc_infra.cache.decorators._alias", return_value=None)

    def fake_cache(ttl, key, *args, **kwargs):
        def decorator(func):
            async def wrapper(*f_args, **f_kwargs):
                return await func(*f_args, **f_kwargs)

            return wrapper

        return decorator

    mocker.patch("svc_infra.cache.decorators._cache.cache", side_effect=fake_cache)

    @cached(key="user:{user_id}", ttl=15)
    async def fetch(user_id: int):
        return {"id": user_id}

    assert await fetch(user_id=1) == {"id": 1}


@pytest.mark.asyncio
async def test_mutates_alias_behaves_like_cache_write(mocker):
    from svc_infra.cache.decorators import mutates

    mocker.patch("svc_infra.cache.decorators.resolve_tags", return_value=["user:1"])
    invalidate = mocker.patch("svc_infra.cache.decorators.invalidate_tags", new_callable=AsyncMock)

    @mutates(tags=["user:{user_id}"])
    async def update(user_id: int):
        return user_id

    assert await update(user_id=1) == 1
    invalidate.assert_awaited_once_with("user:1")
