"""Integration tests for Redis cache.

These tests verify cache read/write, TTL, invalidation, and concurrent access.

Run with: pytest tests/integration/test_redis_cache.py -v
Requires: REDIS_URL environment variable for live tests
"""

from __future__ import annotations

import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

# Skip if Redis is not available
SKIP_NO_REDIS = pytest.mark.skipif(
    not os.getenv("REDIS_URL"),
    reason="REDIS_URL not set - skipping Redis integration tests",
)


@pytest.mark.integration
class TestCacheReadWrite:
    """Integration tests for basic cache read/write operations."""

    @pytest.fixture
    def memory_cache(self):
        """Create an in-memory cache for testing."""
        from svc_infra.cache import InMemoryCache

        cache = InMemoryCache()
        yield cache
        cache.clear()

    def test_set_and_get(self, memory_cache):
        """Test setting and getting a value."""
        memory_cache.set("key1", "value1")
        result = memory_cache.get("key1")

        assert result == "value1"

    def test_get_nonexistent_key(self, memory_cache):
        """Test getting a nonexistent key returns None."""
        result = memory_cache.get("nonexistent")

        assert result is None

    def test_get_with_default(self, memory_cache):
        """Test getting with a default value."""
        result = memory_cache.get("nonexistent", default="default_value")

        assert result == "default_value"

    def test_set_complex_value(self, memory_cache):
        """Test caching complex objects."""
        data = {
            "user_id": 123,
            "items": [{"name": "item1"}, {"name": "item2"}],
            "nested": {"deep": {"value": True}},
        }

        memory_cache.set("complex_key", data)
        result = memory_cache.get("complex_key")

        assert result == data

    def test_overwrite_value(self, memory_cache):
        """Test overwriting an existing value."""
        memory_cache.set("key", "value1")
        memory_cache.set("key", "value2")
        result = memory_cache.get("key")

        assert result == "value2"


@pytest.mark.integration
class TestCacheTTL:
    """Integration tests for cache TTL (time-to-live)."""

    @pytest.fixture
    def memory_cache(self):
        """Create an in-memory cache for testing."""
        from svc_infra.cache import InMemoryCache

        cache = InMemoryCache()
        yield cache
        cache.clear()

    def test_set_with_ttl(self, memory_cache):
        """Test setting a value with TTL."""
        memory_cache.set("key", "value", ttl=3600)
        result = memory_cache.get("key")

        assert result == "value"

    def test_expired_key(self, memory_cache):
        """Test that expired keys return None."""
        memory_cache.set("key", "value", ttl=0.01)  # 10ms TTL
        time.sleep(0.05)  # Wait for expiration

        result = memory_cache.get("key")

        assert result is None

    def test_ttl_remaining(self, memory_cache):
        """Test getting remaining TTL."""
        memory_cache.set("key", "value", ttl=3600)

        remaining = memory_cache.ttl("key")

        assert remaining is not None
        assert remaining > 0
        assert remaining <= 3600

    def test_ttl_nonexistent_key(self, memory_cache):
        """Test TTL of nonexistent key."""
        remaining = memory_cache.ttl("nonexistent")

        assert remaining is None or remaining == -2


@pytest.mark.integration
class TestCacheInvalidation:
    """Integration tests for cache invalidation."""

    @pytest.fixture
    def memory_cache(self):
        """Create an in-memory cache for testing."""
        from svc_infra.cache import InMemoryCache

        cache = InMemoryCache()
        yield cache
        cache.clear()

    def test_delete_key(self, memory_cache):
        """Test deleting a key."""
        memory_cache.set("key", "value")
        memory_cache.delete("key")
        result = memory_cache.get("key")

        assert result is None

    def test_delete_nonexistent_key(self, memory_cache):
        """Test deleting a nonexistent key doesn't raise."""
        # Should not raise
        memory_cache.delete("nonexistent")

    def test_clear_all(self, memory_cache):
        """Test clearing all keys."""
        memory_cache.set("key1", "value1")
        memory_cache.set("key2", "value2")
        memory_cache.clear()

        assert memory_cache.get("key1") is None
        assert memory_cache.get("key2") is None

    def test_delete_pattern(self, memory_cache):
        """Test deleting keys by pattern."""
        memory_cache.set("user:1:profile", "data1")
        memory_cache.set("user:2:profile", "data2")
        memory_cache.set("order:1:items", "data3")

        memory_cache.delete_pattern("user:*")

        assert memory_cache.get("user:1:profile") is None
        assert memory_cache.get("user:2:profile") is None
        assert memory_cache.get("order:1:items") == "data3"


@pytest.mark.integration
class TestCacheConcurrentAccess:
    """Integration tests for concurrent cache access."""

    @pytest.fixture
    def memory_cache(self):
        """Create an in-memory cache for testing."""
        from svc_infra.cache import InMemoryCache

        cache = InMemoryCache()
        yield cache
        cache.clear()

    def test_concurrent_writes(self, memory_cache):
        """Test concurrent writes don't cause data corruption."""

        def write_value(key_suffix: int):
            for i in range(100):
                memory_cache.set(f"key_{key_suffix}_{i}", f"value_{i}")

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(write_value, i) for i in range(4)]
            for f in futures:
                f.result()

        # Verify all values were written correctly
        for suffix in range(4):
            for i in range(100):
                value = memory_cache.get(f"key_{suffix}_{i}")
                assert value == f"value_{i}"

    def test_concurrent_reads_and_writes(self, memory_cache):
        """Test concurrent reads and writes."""
        memory_cache.set("shared_key", "initial")
        errors = []

        def read_write(thread_id: int):
            try:
                for i in range(50):
                    memory_cache.get("shared_key")  # Read
                    memory_cache.set("shared_key", f"thread_{thread_id}_{i}")
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(read_write, i) for i in range(4)]
            for f in futures:
                f.result()

        # No errors should have occurred
        assert len(errors) == 0
        # Value should be set to something
        assert memory_cache.get("shared_key") is not None


@pytest.mark.integration
class TestAsyncCache:
    """Integration tests for async cache operations."""

    @pytest.fixture
    def async_cache(self):
        """Create an async cache for testing."""
        from svc_infra.cache import AsyncInMemoryCache

        cache = AsyncInMemoryCache()
        return cache

    @pytest.mark.asyncio
    async def test_async_set_and_get(self, async_cache):
        """Test async setting and getting a value."""
        await async_cache.set("key1", "value1")
        result = await async_cache.get("key1")

        assert result == "value1"

    @pytest.mark.asyncio
    async def test_async_concurrent_access(self, async_cache):
        """Test concurrent async access."""

        async def write_values(prefix: str):
            for i in range(50):
                await async_cache.set(f"{prefix}:{i}", f"value_{i}")

        await asyncio.gather(
            write_values("a"),
            write_values("b"),
            write_values("c"),
        )

        # Verify all values
        for prefix in ["a", "b", "c"]:
            for i in range(50):
                value = await async_cache.get(f"{prefix}:{i}")
                assert value == f"value_{i}"


@pytest.mark.integration
@SKIP_NO_REDIS
class TestRedisCache:
    """Integration tests for Redis cache (requires REDIS_URL)."""

    @pytest.fixture
    def redis_cache(self):
        """Create a Redis cache client."""
        from svc_infra.cache import RedisCache

        cache = RedisCache.from_url(os.environ["REDIS_URL"])
        yield cache
        # Clean up test keys
        cache.delete_pattern("test:*")
        cache.close()

    def test_redis_set_and_get(self, redis_cache):
        """Test Redis set and get."""
        redis_cache.set("test:key1", "value1", ttl=60)
        result = redis_cache.get("test:key1")

        assert result == "value1"

    def test_redis_json_serialization(self, redis_cache):
        """Test Redis handles JSON serialization."""
        data = {"user_id": 123, "items": ["a", "b", "c"]}
        redis_cache.set("test:json", data, ttl=60)
        result = redis_cache.get("test:json")

        assert result == data

    def test_redis_ttl(self, redis_cache):
        """Test Redis TTL."""
        redis_cache.set("test:ttl", "value", ttl=60)
        remaining = redis_cache.ttl("test:ttl")

        assert remaining > 0
        assert remaining <= 60

    def test_redis_delete(self, redis_cache):
        """Test Redis delete."""
        redis_cache.set("test:delete", "value", ttl=60)
        redis_cache.delete("test:delete")
        result = redis_cache.get("test:delete")

        assert result is None


@pytest.mark.integration
class TestCacheDecorator:
    """Integration tests for cache decorator."""

    @pytest.fixture
    def memory_cache(self):
        """Create an in-memory cache for testing."""
        from svc_infra.cache import InMemoryCache

        cache = InMemoryCache()
        yield cache
        cache.clear()

    def test_cached_function(self, memory_cache):
        """Test caching function results."""
        from svc_infra.cache import cached

        call_count = 0

        @cached(cache=memory_cache, ttl=3600)
        def expensive_operation(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call - should execute function
        result1 = expensive_operation(5)
        assert result1 == 10
        assert call_count == 1

        # Second call - should use cache
        result2 = expensive_operation(5)
        assert result2 == 10
        assert call_count == 1  # Not incremented

        # Different argument - should execute function
        result3 = expensive_operation(10)
        assert result3 == 20
        assert call_count == 2

    def test_cache_key_generation(self, memory_cache):
        """Test cache key includes all arguments."""
        from svc_infra.cache import cached

        @cached(cache=memory_cache, ttl=3600)
        def func_with_kwargs(a: int, b: str = "default") -> str:
            return f"{a}-{b}"

        result1 = func_with_kwargs(1, b="hello")
        result2 = func_with_kwargs(1, b="world")

        assert result1 == "1-hello"
        assert result2 == "1-world"
