"""
Tests for authentication security components.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from svc_infra.api.fastapi.auth.security import (
    Principal,
    RequireRoles,
    RequireScopes,
    RequireService,
    RequireUser,
    _current_principal,
    resolve_api_key,
    resolve_bearer_or_cookie_principal,
)


class TestPrincipal:
    """Test Principal class functionality."""

    def test_principal_creation(self):
        user = Mock()
        api_key = Mock()

        principal = Principal(
            user=user,
            scopes=["read", "write"],
            via="api_key",
            api_key=api_key,
        )

        assert principal.user == user
        assert principal.scopes == ["read", "write"]
        assert principal.via == "api_key"
        assert principal.api_key == api_key

    def test_principal_defaults(self):
        principal = Principal()

        assert principal.user is None
        assert principal.scopes == []
        assert principal.via == "jwt"
        assert principal.api_key is None


class TestResolveApiKey:
    """Test API key resolution functionality."""

    @pytest.mark.asyncio
    async def test_resolve_api_key_no_header(self):
        request = Mock()
        request.headers = {}

        session = Mock()

        result = await resolve_api_key(request, session)

        assert result is None


class TestResolveBearerOrCookiePrincipal:
    """Test bearer token and cookie principal resolution."""

    @pytest.mark.asyncio
    async def test_resolve_no_token(self):
        request = Mock()
        request.headers = {}
        request.cookies = {}

        session = Mock()

        result = await resolve_bearer_or_cookie_principal(request, session)

        assert result is None


class TestAuthGuards:
    """Integration tests for guard dependencies."""

    @pytest.mark.asyncio
    async def test_require_roles_success(self):
        app = FastAPI()

        @app.get("/guarded")
        async def guarded(principal=RequireRoles("admin")):
            return {"roles": list(principal.user.roles)}

        user = Mock()
        user.roles = ["admin", "user"]
        app.dependency_overrides[_current_principal] = lambda: Principal(user=user, scopes=["read"])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/guarded")

        assert response.status_code == 200
        payload = response.json()
        assert payload["roles"] == ["admin", "user"]

    @pytest.mark.asyncio
    async def test_require_roles_failure(self):
        app = FastAPI()

        @app.get("/guarded")
        async def guarded(principal=RequireRoles("admin")):
            return {"ok": True}

        user = Mock()
        user.roles = ["user"]  # missing admin
        app.dependency_overrides[_current_principal] = lambda: Principal(user=user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/guarded")

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_require_scopes_success(self):
        app = FastAPI()

        @app.get("/scoped")
        async def scoped(principal=RequireScopes("read", "write")):
            return {"scopes": principal.scopes}

        principal = Principal(user=Mock(), scopes=["read", "write", "admin"])
        app.dependency_overrides[_current_principal] = lambda: principal

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/scoped")

        assert response.status_code == 200
        assert set(response.json()["scopes"]) == {"read", "write", "admin"}

    @pytest.mark.asyncio
    async def test_require_scopes_failure(self):
        app = FastAPI()

        @app.get("/scoped")
        async def scoped(principal=RequireScopes("write")):
            return {"scopes": principal.scopes}

        principal = Principal(user=Mock(), scopes=["read"])
        app.dependency_overrides[_current_principal] = lambda: principal

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/scoped")

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_require_user_success(self):
        app = FastAPI()

        @app.get("/user-only")
        async def user_only(principal=RequireUser()):
            return {"user_id": str(principal.user.id)}

        user = Mock()
        user.id = "user-1"
        app.dependency_overrides[_current_principal] = lambda: Principal(user=user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/user-only")

        assert response.status_code == 200
        assert response.json()["user_id"] == "user-1"

    @pytest.mark.asyncio
    async def test_require_user_failure(self):
        app = FastAPI()

        @app.get("/user-only")
        async def user_only(principal=RequireUser()):
            return {"ok": True}

        app.dependency_overrides[_current_principal] = lambda: Principal(user=None, api_key=Mock())

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/user-only")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_require_service_success(self):
        app = FastAPI()

        @app.get("/service-only")
        async def service_only(principal=RequireService()):
            return {"api_key_id": str(principal.api_key.id)}

        api_key = Mock()
        api_key.id = "svc-key"
        app.dependency_overrides[_current_principal] = lambda: Principal(
            api_key=api_key, via="api_key"
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/service-only")

        assert response.status_code == 200
        assert response.json()["api_key_id"] == "svc-key"

    @pytest.mark.asyncio
    async def test_require_service_failure(self):
        app = FastAPI()

        @app.get("/service-only")
        async def service_only(principal=RequireService()):
            return {"ok": True}

        app.dependency_overrides[_current_principal] = lambda: Principal(user=Mock())

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/service-only")

        assert response.status_code == 401
