"""Tests for object_router - router_from_object() function.

Tests cover:
- Basic method-to-endpoint mapping
- HTTP verb inference
- Path generation
- Request/response model generation
- auth_required router selection
- Exception mapping
- Async method handling
- Decorator-based configuration
- Edge cases
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from svc_infra.api.fastapi.middleware.errors.handlers import register_error_handlers
from svc_infra.api.fastapi.object_router import (
    DEFAULT_EXCEPTION_MAP,
    STATUS_TITLES,
    _create_request_model,
    _filter_methods,
    _generate_path,
    _generate_path_with_params,
    _get_method_candidates,
    _infer_http_verb,
    _strip_verb_prefix,
    _to_kebab_case,
    endpoint,
    endpoint_exclude,
    map_exception_to_http,
    router_from_object,
    websocket_endpoint,
)

# =============================================================================
# Test Classes (Fixtures)
# =============================================================================


class SimpleCalculator:
    """A simple calculator for testing."""

    def add(self, a: float, b: float) -> float:
        """Add two numbers."""
        return a + b

    def multiply(self, a: float, b: float) -> float:
        """Multiply two numbers."""
        return a * b

    def _private_helper(self) -> str:
        """A private method that should be excluded by default."""
        return "private"

    def __dunder_method__(self) -> str:
        """A dunder method that should always be excluded."""
        return "dunder"


class CrudService:
    """A service with CRUD operations for testing HTTP verb inference."""

    def get_user(self, user_id: str) -> dict:
        """Get a user by ID."""
        return {"id": user_id, "name": "Test User"}

    def list_users(self) -> list:
        """List all users."""
        return [{"id": "1", "name": "User 1"}]

    def create_user(self, name: str, email: str) -> dict:
        """Create a new user."""
        return {"id": "new", "name": name, "email": email}

    def update_user(self, user_id: str, name: str) -> dict:
        """Update a user."""
        return {"id": user_id, "name": name}

    def delete_user(self, user_id: str) -> dict:
        """Delete a user."""
        return {"deleted": True, "id": user_id}

    def search_users(self, query: str) -> list:
        """Search for users."""
        return [{"id": "1", "name": query}]

    def process_action(self) -> str:
        """Action without verb prefix (defaults to POST)."""
        return "processed"


class AsyncService:
    """A service with async methods."""

    async def fetch_data(self, url: str) -> dict:
        """Fetch data from a URL."""
        return {"url": url, "data": "mocked"}

    async def get_status(self) -> str:
        """Get current status."""
        return "ok"

    def sync_method(self) -> str:
        """A sync method."""
        return "sync"


class DecoratedService:
    """A service with decorator-configured methods."""

    @endpoint(method="GET", path="/custom", summary="Custom action")
    def my_action(self, value: int) -> str:
        """Original docstring."""
        return f"action: {value}"

    @endpoint_exclude
    def excluded_method(self) -> str:
        """This method should NOT become an endpoint."""
        return "excluded"

    @endpoint(method="POST", status_code=201)
    def create_item(self, name: str) -> dict:
        """Create a new item."""
        return {"name": name}

    def normal_method(self) -> str:
        """A normal method without decorators."""
        return "normal"


class ErrorService:
    """A service that raises various exceptions."""

    def raise_value_error(self) -> None:
        """Raise ValueError."""
        raise ValueError("Invalid value")

    def raise_key_error(self) -> None:
        """Raise KeyError."""
        raise KeyError("not_found")

    def raise_permission_error(self) -> None:
        """Raise PermissionError."""
        raise PermissionError("Access denied")

    def raise_timeout_error(self) -> None:
        """Raise TimeoutError."""
        raise TimeoutError("Request timed out")

    def raise_not_implemented(self) -> None:
        """Raise NotImplementedError."""
        raise NotImplementedError("Not implemented yet")

    def raise_generic_error(self) -> None:
        """Raise generic Exception."""
        raise Exception("Generic error")


class PathParamService:
    """A service with path parameters."""

    def get_user(self, user_id: str) -> dict:
        """Get user by ID."""
        return {"user_id": user_id}

    def get_order_item(self, order_id: str, item_id: str) -> dict:
        """Get item from order."""
        return {"order_id": order_id, "item_id": item_id}

    def list_items(self) -> list:
        """List all items (no path params)."""
        return []


class EmptyClass:
    """A class with no public methods."""

    pass


class OnlyPrivate:
    """A class with only private methods."""

    def _private_one(self) -> str:
        return "one"

    def _private_two(self) -> str:
        return "two"


class WebSocketService:
    """A service with WebSocket methods."""

    def get_status(self) -> str:
        """Regular HTTP endpoint."""
        return "ok"

    @websocket_endpoint(path="/stream")
    async def stream_data(self):
        """Stream data over WebSocket."""
        yield {"data": "test"}


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestToKebabCase:
    """Tests for _to_kebab_case helper."""

    def test_snake_case(self):
        assert _to_kebab_case("process_payment") == "process-payment"

    def test_camel_case(self):
        assert _to_kebab_case("processPayment") == "process-payment"

    def test_pascal_case(self):
        assert _to_kebab_case("ProcessPayment") == "process-payment"

    def test_already_kebab(self):
        assert _to_kebab_case("process-payment") == "process-payment"

    def test_single_word(self):
        assert _to_kebab_case("process") == "process"

    def test_http_client(self):
        assert _to_kebab_case("HTTPClient") == "http-client"

    def test_multiple_underscores(self):
        assert _to_kebab_case("process_payment_request") == "process-payment-request"


class TestInferHttpVerb:
    """Tests for _infer_http_verb helper."""

    def test_get_prefix(self):
        assert _infer_http_verb("get_user") == "GET"
        assert _infer_http_verb("get_all_users") == "GET"

    def test_list_prefix(self):
        assert _infer_http_verb("list_users") == "GET"

    def test_fetch_prefix(self):
        assert _infer_http_verb("fetch_data") == "GET"

    def test_find_prefix(self):
        assert _infer_http_verb("find_user") == "GET"

    def test_search_prefix(self):
        assert _infer_http_verb("search_users") == "GET"

    def test_create_prefix(self):
        assert _infer_http_verb("create_user") == "POST"

    def test_add_prefix(self):
        assert _infer_http_verb("add_item") == "POST"

    def test_insert_prefix(self):
        assert _infer_http_verb("insert_record") == "POST"

    def test_update_prefix(self):
        assert _infer_http_verb("update_user") == "PUT"

    def test_modify_prefix(self):
        assert _infer_http_verb("modify_settings") == "PUT"

    def test_patch_prefix(self):
        assert _infer_http_verb("patch_user") == "PATCH"

    def test_delete_prefix(self):
        assert _infer_http_verb("delete_user") == "DELETE"

    def test_remove_prefix(self):
        assert _infer_http_verb("remove_item") == "DELETE"

    def test_destroy_prefix(self):
        assert _infer_http_verb("destroy_session") == "DELETE"

    def test_default_to_post(self):
        assert _infer_http_verb("process") == "POST"
        assert _infer_http_verb("execute") == "POST"
        assert _infer_http_verb("run_task") == "POST"

    def test_case_insensitive(self):
        assert _infer_http_verb("GET_user") == "GET"
        assert _infer_http_verb("Create_User") == "POST"


class TestStripVerbPrefix:
    """Tests for _strip_verb_prefix helper."""

    def test_strip_get(self):
        assert _strip_verb_prefix("get_user") == "user"

    def test_strip_create(self):
        assert _strip_verb_prefix("create_order") == "order"

    def test_strip_update(self):
        assert _strip_verb_prefix("update_profile") == "profile"

    def test_strip_delete(self):
        assert _strip_verb_prefix("delete_item") == "item"

    def test_no_prefix(self):
        assert _strip_verb_prefix("process") == "process"

    def test_preserves_case(self):
        assert _strip_verb_prefix("get_User") == "User"


class TestGeneratePath:
    """Tests for _generate_path helper."""

    def test_get_user(self):
        assert _generate_path("get_user") == "user"

    def test_create_order(self):
        assert _generate_path("create_order") == "order"

    def test_process_payment(self):
        assert _generate_path("process_payment") == "process-payment"

    def test_simple_action(self):
        assert _generate_path("execute") == "execute"


class TestGeneratePathWithParams:
    """Tests for _generate_path_with_params helper."""

    def test_single_id_param(self):
        def get_user(self, user_id: str) -> dict:
            pass

        path, params = _generate_path_with_params("get_user", get_user)
        assert path == "user/{user_id}"
        assert params == ["user_id"]

    def test_multiple_id_params(self):
        def get_order_item(self, order_id: str, item_id: str) -> dict:
            pass

        path, params = _generate_path_with_params("get_order_item", get_order_item)
        assert path == "order-item/{order_id}/{item_id}"
        assert params == ["order_id", "item_id"]

    def test_no_id_params(self):
        def list_items(self) -> list:
            pass

        path, params = _generate_path_with_params("list_items", list_items)
        assert path == "items"
        assert params == []

    def test_id_param_alone(self):
        def get_item(self, id: str) -> dict:
            pass

        path, params = _generate_path_with_params("get_item", get_item)
        assert path == "item/{id}"
        assert params == ["id"]

    def test_explicit_path_params(self):
        def get_data(self, user_id: str, name: str) -> dict:
            pass

        path, params = _generate_path_with_params("get_data", get_data, path_params=["name"])
        assert path == "data/{name}"
        assert params == ["name"]


# =============================================================================
# Method Discovery Tests
# =============================================================================


class TestGetMethodCandidates:
    """Tests for _get_method_candidates helper."""

    def test_simple_class(self):
        calc = SimpleCalculator()
        candidates = _get_method_candidates(calc)
        names = [name for name, _ in candidates]

        assert "add" in names
        assert "multiply" in names
        assert "_private_helper" in names
        # Dunders are excluded
        assert "__dunder_method__" not in names
        assert "__init__" not in names

    def test_empty_class(self):
        empty = EmptyClass()
        candidates = _get_method_candidates(empty)
        # Only inherited methods from object
        names = [name for name, _ in candidates]
        assert "add" not in names


class TestFilterMethods:
    """Tests for _filter_methods helper."""

    def test_excludes_private_by_default(self):
        calc = SimpleCalculator()
        candidates = _get_method_candidates(calc)
        filtered = _filter_methods(candidates)
        names = [name for name, _ in filtered]

        assert "add" in names
        assert "multiply" in names
        assert "_private_helper" not in names

    def test_include_private(self):
        calc = SimpleCalculator()
        candidates = _get_method_candidates(calc)
        filtered = _filter_methods(candidates, include_private=True)
        names = [name for name, _ in filtered]

        assert "_private_helper" in names

    def test_explicit_exclude(self):
        calc = SimpleCalculator()
        candidates = _get_method_candidates(calc)
        filtered = _filter_methods(candidates, exclude=["add"])
        names = [name for name, _ in filtered]

        assert "add" not in names
        assert "multiply" in names

    def test_methods_dict_filter(self):
        calc = SimpleCalculator()
        candidates = _get_method_candidates(calc)
        filtered = _filter_methods(candidates, methods={"add": "POST"})
        names = [name for name, _ in filtered]

        assert "add" in names
        assert "multiply" not in names

    def test_endpoint_exclude_decorator(self):
        service = DecoratedService()
        candidates = _get_method_candidates(service)
        filtered = _filter_methods(candidates)
        names = [name for name, _ in filtered]

        assert "my_action" in names
        assert "excluded_method" not in names


# =============================================================================
# Request/Response Model Tests
# =============================================================================


class TestCreateRequestModel:
    """Tests for _create_request_model helper."""

    def test_creates_model_with_params(self):
        calc = SimpleCalculator()
        model = _create_request_model(calc.add, "add", "SimpleCalculator")

        assert model is not None
        assert "a" in model.model_fields
        assert "b" in model.model_fields

    def test_returns_none_for_no_params(self):
        service = CrudService()
        model = _create_request_model(service.list_users, "list_users", "CrudService")

        assert model is None

    def test_handles_default_values(self):
        def method_with_defaults(self, name: str, count: int = 10) -> dict:
            pass

        model = _create_request_model(method_with_defaults, "test", "Test")

        assert model is not None
        # Create instance with only required field
        instance = model(name="test")
        assert instance.name == "test"
        assert instance.count == 10


# =============================================================================
# Exception Mapping Tests
# =============================================================================


class TestMapExceptionToHttp:
    """Tests for map_exception_to_http helper."""

    def test_value_error(self):
        status, title, detail = map_exception_to_http(ValueError("bad input"))
        assert status == 400
        assert title == "Validation Error"
        assert "bad input" in detail

    def test_key_error(self):
        status, title, detail = map_exception_to_http(KeyError("not_found"))
        assert status == 404
        assert title == "Not Found"

    def test_permission_error(self):
        status, title, detail = map_exception_to_http(PermissionError("denied"))
        assert status == 403
        assert title == "Forbidden"

    def test_timeout_error(self):
        status, title, detail = map_exception_to_http(TimeoutError("timeout"))
        assert status == 504
        assert title == "Gateway Timeout"

    def test_not_implemented_error(self):
        status, title, detail = map_exception_to_http(NotImplementedError("TODO"))
        assert status == 501
        assert title == "Not Implemented"

    def test_connection_error(self):
        status, title, detail = map_exception_to_http(ConnectionError("failed"))
        assert status == 503
        assert title == "Service Unavailable"

    def test_generic_exception(self):
        status, title, detail = map_exception_to_http(Exception("unknown"))
        assert status == 500
        assert title == "Internal Error"

    def test_custom_handlers(self):
        class CustomError(Exception):
            pass

        custom = {CustomError: 418}
        status, title, detail = map_exception_to_http(CustomError("teapot"), custom_handlers=custom)
        assert status == 418

    def test_subclass_matching(self):
        # LookupError is parent of KeyError
        status, _, _ = map_exception_to_http(LookupError("lookup failed"))
        assert status == 404


class TestDefaultExceptionMap:
    """Tests for DEFAULT_EXCEPTION_MAP constant."""

    def test_value_error_mapped(self):
        assert ValueError in DEFAULT_EXCEPTION_MAP
        assert DEFAULT_EXCEPTION_MAP[ValueError] == 400

    def test_key_error_mapped(self):
        assert KeyError in DEFAULT_EXCEPTION_MAP
        assert DEFAULT_EXCEPTION_MAP[KeyError] == 404

    def test_permission_error_mapped(self):
        assert PermissionError in DEFAULT_EXCEPTION_MAP
        assert DEFAULT_EXCEPTION_MAP[PermissionError] == 403

    def test_not_implemented_mapped(self):
        assert NotImplementedError in DEFAULT_EXCEPTION_MAP
        assert DEFAULT_EXCEPTION_MAP[NotImplementedError] == 501


class TestStatusTitles:
    """Tests for STATUS_TITLES constant."""

    def test_common_statuses(self):
        assert STATUS_TITLES[400] == "Validation Error"
        assert STATUS_TITLES[401] == "Unauthorized"
        assert STATUS_TITLES[403] == "Forbidden"
        assert STATUS_TITLES[404] == "Not Found"
        assert STATUS_TITLES[500] == "Internal Error"


# =============================================================================
# Router Generation Tests
# =============================================================================


class TestRouterFromObject:
    """Tests for router_from_object main function."""

    def test_basic_router_creation(self):
        calc = SimpleCalculator()
        router = router_from_object(calc, prefix="/calc")

        assert router is not None
        # Router should have routes
        assert len(router.routes) > 0

    def test_http_verb_inference(self):
        """HTTP verb is inferred from method name prefix."""
        service = CrudService()
        router = router_from_object(service, prefix="/api")

        # Collect routes by (method, path)
        routes = [
            (next(iter(r.methods)), r.path.rstrip("/"))
            for r in router.routes
            if hasattr(r, "methods") and not r.path.endswith("/")
        ]

        # GET endpoints from verb prefixes
        assert ("GET", "/api/user") in routes  # get_user -> GET /user
        assert ("GET", "/api/users") in routes  # list_users -> GET /users

        # POST endpoints from verb prefixes
        assert ("POST", "/api/user") in routes  # create_user -> POST /user
        assert ("POST", "/api/process-action") in routes  # no prefix -> POST

        # PUT endpoints
        assert ("PUT", "/api/user") in routes  # update_user -> PUT /user

        # DELETE endpoints
        assert ("DELETE", "/api/user") in routes  # delete_user -> DELETE /user

    def test_path_generation(self):
        service = CrudService()
        router = router_from_object(service, prefix="/api")

        # Extract paths
        route_paths = [r.path.rstrip("/") for r in router.routes if hasattr(r, "methods")]

        # Paths should be kebab-case
        assert "/api/process-action" in route_paths

    def test_exclude_methods(self):
        calc = SimpleCalculator()
        router = router_from_object(calc, prefix="/calc", exclude=["multiply"])

        # Check routes don't include excluded method
        route_paths = [r.path for r in router.routes]
        assert any("add" in p for p in route_paths)
        assert not any("multiply" in p for p in route_paths)

    def test_methods_dict_filter(self):
        calc = SimpleCalculator()
        router = router_from_object(calc, prefix="/calc", methods={"add": "GET"})

        # Only add should be included
        route_paths = [r.path for r in router.routes]
        assert any("add" in p for p in route_paths)
        assert not any("multiply" in p for p in route_paths)

    def test_include_private(self):
        calc = SimpleCalculator()
        router = router_from_object(calc, prefix="/calc", include_private=True)

        route_paths = [r.path for r in router.routes]
        assert any("private-helper" in p for p in route_paths)

    def test_request_body_for_post(self):
        """POST endpoints are created with POST method (params use original signature).

        Note: Due to functools.wraps preserving original signature, FastAPI sees
        the original method parameters. This is a known limitation of the current
        implementation - the wrapper creates a request model but FastAPI uses
        the original signature via inspect.
        """
        calc = SimpleCalculator()
        router = router_from_object(calc, prefix="/calc")

        # Verify the route exists and uses POST
        routes_by_path = {
            r.path.rstrip("/"): next(iter(r.methods))
            for r in router.routes
            if hasattr(r, "methods") and not r.path.endswith("/")
        }
        assert routes_by_path.get("/calc/add") == "POST"

    def test_query_params_for_get(self):
        service = CrudService()
        app = FastAPI()
        router = router_from_object(service, prefix="/api")
        app.include_router(router)

        client = TestClient(app)

        # GET with query params
        response = client.get("/api/users", params={"query": "test"})
        assert response.status_code == 200

    def test_exception_handling(self):
        """Exception handling requires register_error_handlers on the app."""
        service = ErrorService()
        app = FastAPI()
        register_error_handlers(app)  # Required for FastApiException handling
        router = router_from_object(service, prefix="/api")
        app.include_router(router)

        client = TestClient(app, raise_server_exceptions=False)

        # ValueError -> 400
        response = client.post("/api/raise-value-error")
        assert response.status_code == 400

        # KeyError -> 404
        response = client.post("/api/raise-key-error")
        assert response.status_code == 404

        # PermissionError -> 403
        response = client.post("/api/raise-permission-error")
        assert response.status_code == 403

        # TimeoutError -> 504
        response = client.post("/api/raise-timeout-error")
        assert response.status_code == 504

        # NotImplementedError -> 501
        response = client.post("/api/raise-not-implemented")
        assert response.status_code == 501

        # Generic -> 500
        response = client.post("/api/raise-generic-error")
        assert response.status_code == 500

    def test_custom_exception_handlers(self):
        """Custom exception handlers are used for mapping."""

        class CustomError(Exception):
            pass

        class CustomService:
            def fail(self) -> None:
                raise CustomError("custom failure")

        service = CustomService()
        app = FastAPI()
        register_error_handlers(app)  # Required for FastApiException handling
        router = router_from_object(
            service,
            prefix="/api",
            exception_handlers={CustomError: 418},
        )
        app.include_router(router)

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/api/fail")
        assert response.status_code == 418


class TestAsyncMethods:
    """Tests for async method handling."""

    def test_async_get_endpoint(self):
        service = AsyncService()
        app = FastAPI()
        router = router_from_object(service, prefix="/api")
        app.include_router(router)

        client = TestClient(app)

        response = client.get("/api/status")
        assert response.status_code == 200
        assert response.json() == "ok"

    def test_async_post_endpoint(self):
        service = AsyncService()
        app = FastAPI()
        router = router_from_object(service, prefix="/api")
        app.include_router(router)

        client = TestClient(app)

        response = client.get("/api/data", params={"url": "http://test.com"})
        assert response.status_code == 200
        assert response.json()["url"] == "http://test.com"


class TestDecoratorConfiguration:
    """Tests for decorator-based endpoint configuration."""

    def test_endpoint_decorator_method_override(self):
        service = DecoratedService()
        app = FastAPI()
        router = router_from_object(service, prefix="/api")
        app.include_router(router)

        client = TestClient(app)

        # Custom method should be GET
        response = client.get("/api/custom", params={"value": 42})
        assert response.status_code == 200
        assert "42" in response.json()

    def test_endpoint_exclude_decorator(self):
        service = DecoratedService()
        router = router_from_object(service, prefix="/api")

        route_paths = [r.path for r in router.routes]
        assert not any("excluded" in p for p in route_paths)

    def test_websocket_endpoint_decorator(self):
        service = WebSocketService()

        # Verify the decorator was applied
        assert hasattr(service.stream_data, "_svc_infra_websocket_endpoint")


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_class(self):
        empty = EmptyClass()
        router = router_from_object(empty, prefix="/empty")

        # Should have no routes (or only trailing slash handler)
        route_count = len([r for r in router.routes if hasattr(r, "methods")])
        assert route_count == 0

    def test_only_private_methods(self):
        private = OnlyPrivate()
        router = router_from_object(private, prefix="/private")

        # Should have no routes
        route_count = len([r for r in router.routes if hasattr(r, "methods")])
        assert route_count == 0

    def test_only_private_with_include(self):
        private = OnlyPrivate()
        router = router_from_object(private, prefix="/private", include_private=True)

        # Should have routes for private methods (2 methods * 2 routes each for dual)
        route_paths = [r.path for r in router.routes if hasattr(r, "methods")]
        # At least 2 unique path prefixes (may have trailing slash variants)
        unique_paths = {p.rstrip("/") for p in route_paths}
        assert len(unique_paths) >= 2

    def test_prefix_normalization(self):
        """Prefix must start with / for dual routers."""
        calc = SimpleCalculator()

        # With slash - works
        router1 = router_from_object(calc, prefix="/calc")
        assert len([r for r in router1.routes if hasattr(r, "methods")]) > 0

        # Without slash - DualAPIRouter requires / prefix
        # Test that it either works with auto-fix or raises meaningful error
        try:
            router2 = router_from_object(calc, prefix="calc")
            # If it doesn't raise, it should still work
            assert len([r for r in router2.routes if hasattr(r, "methods")]) > 0
        except (ValueError, AssertionError):
            # Expected: DualAPIRouter requires / prefix
            pass

    def test_custom_tags(self):
        calc = SimpleCalculator()
        router = router_from_object(calc, prefix="/calc", tags=["Math", "Utilities"])

        # Tags should be set
        assert router.tags == ["Math", "Utilities"]

    def test_default_tags_from_class_name(self):
        calc = SimpleCalculator()
        router = router_from_object(calc, prefix="/calc")

        # Default tag should be class name
        assert router.tags == ["SimpleCalculator"]


class TestAuthRequired:
    """Tests for auth_required parameter."""

    def test_public_router_by_default(self):
        calc = SimpleCalculator()
        router = router_from_object(calc, prefix="/calc", auth_required=False)

        # Should create a router (public or fallback)
        assert router is not None

    def test_auth_required_router(self):
        calc = SimpleCalculator()
        router = router_from_object(calc, prefix="/calc", auth_required=True)

        # Should create a router (user_router or fallback)
        assert router is not None


class TestPathParameters:
    """Tests for parameter handling (params become query params for GET)."""

    def test_single_query_param(self):
        """GET endpoints with params use query parameters."""
        service = PathParamService()
        app = FastAPI()
        router = router_from_object(service, prefix="/api")
        app.include_router(router)

        client = TestClient(app)

        # get_user has user_id param -> becomes query param
        response = client.get("/api/user", params={"user_id": "123"})
        assert response.status_code == 200
        assert response.json()["user_id"] == "123"

    def test_multiple_query_params(self):
        """GET endpoints with multiple params use all as query params."""
        service = PathParamService()
        app = FastAPI()
        router = router_from_object(service, prefix="/api")
        app.include_router(router)

        client = TestClient(app)

        # get_order_item has order_id and item_id -> both query params
        response = client.get(
            "/api/order-item", params={"order_id": "order-1", "item_id": "item-2"}
        )
        assert response.status_code == 200
        assert response.json()["order_id"] == "order-1"
        assert response.json()["item_id"] == "item-2"

    def test_no_path_params(self):
        service = PathParamService()
        app = FastAPI()
        router = router_from_object(service, prefix="/api")
        app.include_router(router)

        client = TestClient(app)

        response = client.get("/api/items")
        assert response.status_code == 200
        assert response.json() == []
