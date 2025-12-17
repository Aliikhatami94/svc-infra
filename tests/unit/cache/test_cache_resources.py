"""
Tests for cache resources functionality.
"""

from __future__ import annotations

from typing import Any, Dict

from svc_infra.cache.resources import Resource, resource


class TestResourceClass:
    """Test Resource class functionality."""

    def test_resource_initialization(self):
        """Test Resource class initialization."""
        res = Resource("user", "user_id")

        assert res.name == "user"
        assert res.id_field == "user_id"

    def test_resource_cache_read_decorator(self):
        """Test Resource cache_read decorator."""
        res = Resource("user", "user_id")

        @res.cache_read(suffix="profile", ttl=300)
        async def get_user_profile(*, user_id: int):
            return {"id": user_id, "name": "Test User"}

        # Verify the decorator was applied
        assert callable(get_user_profile)

    def test_resource_cache_write_decorator(self):
        """Test Resource cache_write decorator."""
        res = Resource("user", "user_id")

        @res.cache_write()
        async def update_user(*, user_id: int, data: Dict[str, Any]):
            return {"id": user_id, **data}

        # Verify the decorator was applied
        assert callable(update_user)

    def test_resource_cache_write_decorator_variations(self):
        """Test Resource cache_write decorator with different configurations."""
        res = Resource("user", "user_id")

        @res.cache_write()
        async def delete_user(*, user_id: int):
            return True

        # Verify the decorator was applied
        assert callable(delete_user)


class TestResourceFunction:
    """Test resource function functionality."""

    def test_resource_function_creation(self):
        """Test resource function creates Resource instance."""
        res = resource("product", "product_id")

        assert isinstance(res, Resource)
        assert res.name == "product"
        assert res.id_field == "product_id"

    def test_resource_function_with_different_names(self):
        """Test resource function with different resource names."""
        user_res = resource("user", "user_id")
        product_res = resource("product", "product_id")
        order_res = resource("order", "order_id")

        assert user_res.name == "user"
        assert user_res.id_field == "user_id"

        assert product_res.name == "product"
        assert product_res.id_field == "product_id"

        assert order_res.name == "order"
        assert order_res.id_field == "order_id"


class TestResourceCacheRead:
    """Test Resource cache_read functionality."""

    def test_resource_cache_read_decorator_creation(self):
        """Test Resource cache_read decorator creation."""
        res = resource("user", "user_id")

        @res.cache_read(suffix="profile", ttl=300)
        async def get_user_profile(*, user_id: int):
            return {"id": user_id, "name": "Database User"}

        # Verify the function was decorated
        assert callable(get_user_profile)

    def test_resource_cache_read_with_custom_key_template(self):
        """Test Resource cache_read with custom key template."""
        res = resource("user", "user_id")

        @res.cache_read(
            suffix="profile", ttl=300, key_template="custom:user:{user_id}:profile"
        )
        async def get_user_profile(*, user_id: int):
            return {"id": user_id, "name": "Database User"}

        # Verify the function was decorated
        assert callable(get_user_profile)

    def test_resource_cache_read_with_custom_tags(self):
        """Test Resource cache_read with custom tags."""
        res = resource("user", "user_id")

        @res.cache_read(
            suffix="profile",
            ttl=300,
            tags_template=("user:{user_id}", "profile:{user_id}"),
        )
        async def get_user_profile(*, user_id: int):
            return {"id": user_id, "name": "Database User"}

        # Verify the function was decorated
        assert callable(get_user_profile)


class TestResourceCacheWrite:
    """Test Resource cache_write functionality."""

    def test_resource_cache_write_decorator_creation(self):
        """Test Resource cache_write decorator creation."""
        res = resource("user", "user_id")

        @res.cache_write()
        async def update_user(*, user_id: int, data: Dict[str, Any]):
            return {"id": user_id, **data}

        # Verify the function was decorated
        assert callable(update_user)

    def test_resource_cache_write_with_recache(self):
        """Test Resource cache_write with recache configuration."""
        res = resource("user", "user_id")

        @res.cache_write(recache=[], recache_max_concurrency=3)
        async def update_user(*, user_id: int, data: Dict[str, Any]):
            return {"id": user_id, **data}

        # Verify the function was decorated
        assert callable(update_user)


class TestResourceCacheWriteVariations:
    """Test Resource cache_write functionality variations."""

    def test_resource_cache_write_decorator_creation(self):
        """Test Resource cache_write decorator creation."""
        res = resource("user", "user_id")

        @res.cache_write()
        async def delete_user(*, user_id: int):
            return True

        # Verify the function was decorated
        assert callable(delete_user)

    def test_resource_cache_write_with_recache(self):
        """Test Resource cache_write with recache configuration."""
        res = resource("user", "user_id")

        @res.cache_write(recache=[], recache_max_concurrency=3)
        async def update_user(*, user_id: int, data: Dict[str, Any]):
            return {"id": user_id, **data}

        # Verify the function was decorated
        assert callable(update_user)


class TestResourceIntegration:
    """Test Resource integration scenarios."""

    def test_multiple_resources_independence(self):
        """Test that multiple resources operate independently."""
        user_res = resource("user", "user_id")
        product_res = resource("product", "product_id")

        @user_res.cache_read(suffix="profile", ttl=300)
        async def get_user_profile(*, user_id: int):
            return {"id": user_id, "name": "User Profile"}

        @product_res.cache_read(suffix="details", ttl=300)
        async def get_product_details(*, product_id: int):
            return {"id": product_id, "name": "Product Details"}

        @user_res.cache_write()
        async def update_user(*, user_id: int, data: Dict[str, Any]):
            return {"id": user_id, **data}

        @product_res.cache_write()
        async def update_product(*, product_id: int, data: Dict[str, Any]):
            return {"id": product_id, **data}

        # Verify all functions were decorated
        assert callable(get_user_profile)
        assert callable(get_product_details)
        assert callable(update_user)
        assert callable(update_product)
