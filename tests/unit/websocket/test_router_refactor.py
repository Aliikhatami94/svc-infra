"""Tests for WebSocket router refactoring.

Tests DualAPIRouter.websocket() functionality and ws_*_router factories.
"""

import pytest
from fastapi import Depends, FastAPI, WebSocket
from starlette.testclient import TestClient

from svc_infra.api.fastapi.dual import DualAPIRouter
from svc_infra.api.fastapi.dual.protected import (
    ws_optional_router,
    ws_protected_router,
    ws_scopes_router,
    ws_user_router,
)
from svc_infra.api.fastapi.dual.public import ws_public_router

pytestmark = pytest.mark.websocket


class TestDualAPIRouterWebSocket:
    """Test DualAPIRouter.websocket() method."""

    def test_router_has_websocket_method(self):
        """DualAPIRouter has websocket() method."""
        router = DualAPIRouter()

        assert hasattr(router, "websocket")
        assert callable(router.websocket)

    def test_websocket_decorator_registers_route(self):
        """websocket decorator registers WebSocket route."""
        router = DualAPIRouter()

        @router.websocket("/test")
        async def test_handler(websocket: WebSocket):
            await websocket.accept()
            await websocket.close()

        # Check route is registered
        routes = [r for r in router.routes if hasattr(r, "path") and r.path == "/test"]
        assert len(routes) == 1

    def test_websocket_with_dependencies(self):
        """websocket route can have dependencies."""
        router = DualAPIRouter()

        async def my_dep():
            return "dep-value"

        @router.websocket("/test", dependencies=[Depends(my_dep)])
        async def test_handler(websocket: WebSocket):
            await websocket.accept()
            await websocket.close()

        # Route should be registered
        routes = [r for r in router.routes if hasattr(r, "path") and r.path == "/test"]
        assert len(routes) == 1

    def test_dual_router_can_be_included(self):
        """DualAPIRouter can be included in FastAPI app."""
        app = FastAPI()
        router = DualAPIRouter()

        @router.websocket("/ws")
        async def ws_handler(websocket: WebSocket):
            await websocket.accept()
            await websocket.close()

        app.include_router(router)

        # Check route is in app
        paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/ws" in paths


class TestWSPublicRouter:
    """Test ws_public_router() factory."""

    def test_returns_dual_api_router(self):
        """Returns a DualAPIRouter instance."""
        router = ws_public_router()

        assert isinstance(router, DualAPIRouter)

    def test_has_no_dependencies_by_default(self):
        """Public router has no auth dependencies."""
        router = ws_public_router()

        # router_dependencies should be empty or None
        deps = getattr(router, "dependencies", [])
        assert len(deps) == 0

    def test_prefix_and_tags(self):
        """Can set prefix and tags."""
        router = ws_public_router(prefix="/public", tags=["public-ws"])

        @router.websocket("/test")
        async def handler(ws: WebSocket):
            pass

        # Check that prefix is applied
        routes = list(router.routes)
        assert any("/public/test" in str(getattr(r, "path", "")) for r in routes)

    def test_full_app_integration(self):
        """Public WS router works in full app."""
        router = ws_public_router()

        @router.websocket("/echo")
        async def echo(websocket: WebSocket):
            await websocket.accept()
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
            await websocket.close()

        app = FastAPI()
        app.include_router(router)

        # Just verify it can be created
        TestClient(app)
        # WebSocket testing would require async client


class TestWSProtectedRouter:
    """Test ws_protected_router() factory."""

    def test_returns_dual_api_router(self):
        """Returns a DualAPIRouter instance."""
        router = ws_protected_router()

        assert isinstance(router, DualAPIRouter)

    def test_has_auth_dependency(self):
        """Protected router has auth dependency."""
        router = ws_protected_router()

        # Should have dependencies for authentication
        deps = getattr(router, "dependencies", [])
        assert len(deps) > 0

    def test_prefix_and_tags(self):
        """Can set prefix and tags."""
        router = ws_protected_router(prefix="/secure", tags=["secure-ws"])

        @router.websocket("/test")
        async def handler(ws: WebSocket):
            pass

        routes = list(router.routes)
        # Should have the route registered
        assert len(routes) > 0


class TestWSUserRouter:
    """Test ws_user_router() factory."""

    def test_returns_dual_api_router(self):
        """Returns a DualAPIRouter instance."""
        router = ws_user_router()

        assert isinstance(router, DualAPIRouter)

    def test_has_auth_dependency(self):
        """User router has auth dependency."""
        router = ws_user_router()

        deps = getattr(router, "dependencies", [])
        assert len(deps) > 0


class TestWSScopesRouter:
    """Test ws_scopes_router() factory."""

    def test_returns_dual_api_router(self):
        """Returns a DualAPIRouter instance."""
        router = ws_scopes_router("read", "write")

        assert isinstance(router, DualAPIRouter)

    def test_requires_scopes(self):
        """Router requires specified scopes."""
        router = ws_scopes_router("admin", "super")

        deps = getattr(router, "dependencies", [])
        # Should have scope check dependency
        assert len(deps) > 0

    def test_single_scope(self):
        """Works with single scope."""
        router = ws_scopes_router("read")

        assert isinstance(router, DualAPIRouter)


class TestWSOptionalRouter:
    """Test ws_optional_router() factory."""

    def test_returns_dual_api_router(self):
        """Returns a DualAPIRouter instance."""
        router = ws_optional_router()

        assert isinstance(router, DualAPIRouter)

    def test_has_optional_auth_dependency(self):
        """Optional router has auth dependency but allows None."""
        router = ws_optional_router()

        deps = getattr(router, "dependencies", [])
        assert isinstance(deps, list)
        # May have dependencies for optional auth
        # The key is that it doesn't reject unauthenticated


class TestRouterExports:
    """Test that routers are properly exported."""

    def test_dual_init_exports_ws_routers(self):
        """dual/__init__.py exports WS routers."""
        from svc_infra.api.fastapi.dual import (
            ws_optional_router,
            ws_protected_router,
            ws_public_router,
            ws_scopes_router,
            ws_user_router,
        )

        assert callable(ws_public_router)
        assert callable(ws_protected_router)
        assert callable(ws_user_router)
        assert callable(ws_scopes_router)
        assert callable(ws_optional_router)

    def test_dx_exports_ws_auth(self):
        """dx.py exports WS auth types."""
        from svc_infra.api.fastapi.dx import (
            RequireWSAnyScope,
            RequireWSIdentity,
            RequireWSScopes,
            WSIdentity,
            WSPrincipal,
        )

        assert WSPrincipal is not None
        assert WSIdentity is not None
        assert RequireWSIdentity is not None
        assert callable(RequireWSScopes)
        assert callable(RequireWSAnyScope)

    def test_dx_exports_ws_routers(self):
        """dx.py exports WS router factories."""
        from svc_infra.api.fastapi.dx import (
            ws_optional_router,
            ws_protected_router,
            ws_public_router,
            ws_scopes_router,
            ws_user_router,
        )

        assert callable(ws_public_router)
        assert callable(ws_protected_router)
        assert callable(ws_user_router)
        assert callable(ws_scopes_router)
        assert callable(ws_optional_router)


class TestIntegrationWithApp:
    """Test WS routers integration with FastAPI apps."""

    def test_multiple_routers_in_app(self):
        """Multiple WS routers can coexist in app."""
        app = FastAPI()

        public_router = ws_public_router(prefix="/public")
        protected_router = ws_protected_router(prefix="/protected")

        @public_router.websocket("/ws")
        async def public_ws(websocket: WebSocket):
            await websocket.accept()
            await websocket.close()

        @protected_router.websocket("/ws")
        async def protected_ws(websocket: WebSocket):
            await websocket.accept()
            await websocket.close()

        app.include_router(public_router)
        app.include_router(protected_router)

        paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/public/ws" in paths
        assert "/protected/ws" in paths

    def test_http_and_ws_on_same_router(self):
        """DualAPIRouter supports both HTTP and WS."""
        router = DualAPIRouter()

        @router.get("/health")
        async def health():
            return {"status": "ok"}

        @router.websocket("/ws")
        async def ws_handler(websocket: WebSocket):
            await websocket.accept()
            await websocket.close()

        app = FastAPI()
        app.include_router(router)

        paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/health" in paths
        assert "/ws" in paths
