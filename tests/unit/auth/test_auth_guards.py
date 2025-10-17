"""
Tests for authentication guards and middleware.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from svc_infra.api.fastapi.auth.security import (
    AllowIdentity,
    RequireAnyScope,
    RequireIdentity,
    RequireRoles,
    RequireScopes,
    RequireService,
    RequireUser,
    _current_principal,
    _optional_principal,
)


class TestRequireIdentity:
    """Test RequireIdentity guard."""

    @pytest.mark.asyncio
    async def test_require_identity_success(self, auth_client, mock_principal):
        """Test RequireIdentity with valid principal."""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(principal=RequireIdentity):
            return {"user_id": principal.user.id, "via": principal.via}

        # Mock the dependency - RequireIdentity is a Depends object, so we need to override the underlying function
        app.dependency_overrides[_current_principal] = lambda: mock_principal

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test")

            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == mock_principal.user.id
            assert data["via"] == mock_principal.via

    @pytest.mark.asyncio
    async def test_require_identity_failure(self, auth_client):
        """Test RequireIdentity without principal."""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(principal=RequireIdentity):
            return {"user_id": principal.user.id}

        # Mock the dependency to raise HTTPException (no auth)
        def _raise_auth_error():
            raise HTTPException(401, "Missing credentials")

        app.dependency_overrides[_current_principal] = _raise_auth_error

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test")

            # Should fail without proper auth
            assert response.status_code in [401, 403, 422]


class TestAllowIdentity:
    """Test AllowIdentity guard."""

    @pytest.mark.asyncio
    async def test_allow_identity_with_principal(self, auth_client, mock_principal):
        """Test AllowIdentity with valid principal."""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(principal=AllowIdentity):
            if principal:
                return {"user_id": principal.user.id, "authenticated": True}
            else:
                return {"authenticated": False}

        # Mock the dependency - AllowIdentity uses _optional_principal
        app.dependency_overrides[_optional_principal] = lambda: mock_principal

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test")

            assert response.status_code == 200
            data = response.json()
            assert data["authenticated"] is True
            assert data["user_id"] == mock_principal.user.id

    @pytest.mark.asyncio
    async def test_allow_identity_without_principal(self, auth_client):
        """Test AllowIdentity without principal."""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(principal=AllowIdentity):
            if principal:
                return {"user_id": principal.user.id, "authenticated": True}
            else:
                return {"authenticated": False}

        # Mock the dependency to return None
        app.dependency_overrides[_optional_principal] = lambda: None

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test")

            assert response.status_code == 200
            data = response.json()
            assert data["authenticated"] is False


class TestRequireUser:
    """Test RequireUser guard."""

    @pytest.mark.asyncio
    async def test_require_user_success(self, auth_client, mock_principal):
        """Test RequireUser with valid user principal."""
        app = FastAPI()

        # Create the RequireUser guard
        require_user_guard = RequireUser()

        @app.get("/test")
        async def test_endpoint(principal=require_user_guard):
            return {"user_id": principal.user.id, "email": principal.user.email}

        # Mock the underlying _current_principal dependency
        app.dependency_overrides[_current_principal] = lambda: mock_principal

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test")

            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == mock_principal.user.id
            assert data["email"] == mock_principal.user.email

    @pytest.mark.asyncio
    async def test_require_user_failure(self, auth_client):
        """Test RequireUser with service principal."""
        app = FastAPI()

        # Create a service principal (no user)
        service_principal = Mock()
        service_principal.user = None
        service_principal.via = "api_key"
        service_principal.api_key = Mock()

        # Create the RequireUser guard
        require_user_guard = RequireUser()

        @app.get("/test")
        async def test_endpoint(principal=require_user_guard):
            return {"user_id": principal.user.id}

        # Mock the underlying _current_principal dependency
        app.dependency_overrides[_current_principal] = lambda: service_principal

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test")

            # Should fail because it's a service principal, not a user
            assert response.status_code in [401, 403, 422]


class TestRequireService:
    """Test RequireService guard."""

    @pytest.mark.asyncio
    async def test_require_service_success(self, auth_client):
        """Test RequireService with valid service principal."""
        app = FastAPI()

        # Create a service principal
        service_principal = Mock()
        service_principal.user = None
        service_principal.via = "api_key"
        service_principal.api_key = Mock()
        service_principal.api_key.id = "service_key_123"

        # Create the RequireService guard
        require_service_guard = RequireService()

        @app.get("/test")
        async def test_endpoint(principal=require_service_guard):
            return {"api_key_id": principal.api_key.id, "via": principal.via}

        # Mock the underlying _current_principal dependency
        app.dependency_overrides[_current_principal] = lambda: service_principal

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test")

            assert response.status_code == 200
            data = response.json()
            assert data["api_key_id"] == "service_key_123"
            assert data["via"] == "api_key"

    @pytest.mark.asyncio
    async def test_require_service_failure(self, auth_client):
        """Test RequireService with user principal."""
        app = FastAPI()

        # Create a user principal without api_key
        user_principal = Mock()
        user_principal.user = Mock()
        user_principal.user.id = "user_123"
        user_principal.api_key = None  # No API key

        # Create the RequireService guard
        require_service_guard = RequireService()

        @app.get("/test")
        async def test_endpoint(principal=require_service_guard):
            return {"api_key_id": principal.api_key.id}

        # Mock the underlying _current_principal dependency with user principal
        app.dependency_overrides[_current_principal] = lambda: user_principal

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test")

            # Should fail because it's a user principal, not a service
            assert response.status_code in [401, 403, 422]


class TestRequireScopes:
    """Test RequireScopes guard."""

    @pytest.mark.asyncio
    async def test_require_scopes_success(self, auth_client):
        """Test RequireScopes with valid scopes."""
        app = FastAPI()

        # Create principal with required scopes
        principal = Mock()
        principal.scopes = ["read", "write", "admin"]

        # Create the RequireScopes guard
        require_scopes_guard = RequireScopes("read", "write")

        @app.get("/test")
        async def test_endpoint(principal=require_scopes_guard):
            return {"scopes": principal.scopes}

        # Mock the underlying _current_principal dependency
        app.dependency_overrides[_current_principal] = lambda: principal

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test")

            assert response.status_code == 200
            data = response.json()
            assert "read" in data["scopes"]
            assert "write" in data["scopes"]

    @pytest.mark.asyncio
    async def test_require_scopes_failure(self, auth_client):
        """Test RequireScopes with insufficient scopes."""
        app = FastAPI()

        # Create principal with insufficient scopes
        principal = Mock()
        principal.scopes = ["read"]  # Missing "write" scope

        # Create the RequireScopes guard
        require_scopes_guard = RequireScopes("read", "write")

        @app.get("/test")
        async def test_endpoint(principal=require_scopes_guard):
            return {"scopes": principal.scopes}

        # Mock the underlying _current_principal dependency
        app.dependency_overrides[_current_principal] = lambda: principal

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test")

            # Should fail due to insufficient scopes
            assert response.status_code in [401, 403, 422]


class TestRequireAnyScope:
    """Test RequireAnyScope guard."""

    @pytest.mark.asyncio
    async def test_require_any_scope_success(self, auth_client):
        """Test RequireAnyScope with one valid scope."""
        app = FastAPI()

        # Create principal with one of the required scopes
        principal = Mock()
        principal.scopes = ["read"]  # Has "read" but not "write"

        # Create the RequireAnyScope guard
        require_any_scope_guard = RequireAnyScope("read", "write")

        @app.get("/test")
        async def test_endpoint(principal=require_any_scope_guard):
            return {"scopes": principal.scopes}

        # Mock the underlying _current_principal dependency
        app.dependency_overrides[_current_principal] = lambda: principal

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test")

            assert response.status_code == 200
            data = response.json()
            assert "read" in data["scopes"]

    @pytest.mark.asyncio
    async def test_require_any_scope_failure(self, auth_client):
        """Test RequireAnyScope with no valid scopes."""
        app = FastAPI()

        # Create principal with no required scopes
        principal = Mock()
        principal.scopes = ["other"]  # Doesn't have "read" or "write"

        # Create the RequireAnyScope guard
        require_any_scope_guard = RequireAnyScope("read", "write")

        @app.get("/test")
        async def test_endpoint(principal=require_any_scope_guard):
            return {"scopes": principal.scopes}

        # Mock the underlying _current_principal dependency
        app.dependency_overrides[_current_principal] = lambda: principal

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test")

            # Should fail due to no matching scopes
            assert response.status_code in [401, 403, 422]


class TestRequireRoles:
    """Test RequireRoles guard."""

    @pytest.mark.asyncio
    async def test_require_roles_success(self, auth_client):
        """Test RequireRoles with valid roles."""
        app = FastAPI()

        # Create user with required roles
        user = Mock()
        user.roles = ["admin", "user"]

        principal = Mock()
        principal.user = user

        # Create the RequireRoles guard
        require_roles_guard = RequireRoles("admin")

        @app.get("/test")
        async def test_endpoint(principal=require_roles_guard):
            return {"roles": principal.user.roles}

        # Mock the underlying _current_principal dependency
        app.dependency_overrides[_current_principal] = lambda: principal

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test")

            assert response.status_code == 200
            data = response.json()
            assert "admin" in data["roles"]

    @pytest.mark.asyncio
    async def test_require_roles_failure(self, auth_client):
        """Test RequireRoles with insufficient roles."""
        app = FastAPI()

        # Create user without required roles
        user = Mock()
        user.roles = ["user"]  # Missing "admin" role

        principal = Mock()
        principal.user = user

        # Create the RequireRoles guard
        require_roles_guard = RequireRoles("admin")

        @app.get("/test")
        async def test_endpoint(principal=require_roles_guard):
            return {"roles": principal.user.roles}

        # Mock the underlying _current_principal dependency
        app.dependency_overrides[_current_principal] = lambda: principal

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test")

            # Should fail due to insufficient roles
            assert response.status_code in [401, 403, 422]

    @pytest.mark.asyncio
    async def test_require_roles_with_custom_resolver(self, auth_client):
        """Test RequireRoles with custom role resolver."""
        app = FastAPI()

        # Create user with custom role resolver
        user = Mock()
        user.custom_roles = ["super_admin", "moderator"]

        principal = Mock()
        principal.user = user

        # Custom role resolver function
        def custom_role_resolver(user):
            return getattr(user, "custom_roles", [])

        # Create the RequireRoles guard with custom resolver
        require_roles_guard = RequireRoles("super_admin", resolver=custom_role_resolver)

        @app.get("/test")
        async def test_endpoint(principal=require_roles_guard):
            return {"roles": custom_role_resolver(principal.user)}

        # Mock the underlying _current_principal dependency
        app.dependency_overrides[_current_principal] = lambda: principal

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test")

            assert response.status_code == 200
            data = response.json()
            assert "super_admin" in data["roles"]


class TestGuardCombinations:
    """Test combining multiple guards."""

    @pytest.mark.asyncio
    async def test_user_with_scopes(self, auth_client):
        """Test endpoint requiring both user and specific scopes."""
        app = FastAPI()

        # Create user principal with scopes
        user = Mock()
        user.id = "user_123"
        user.email = "test@example.com"

        principal = Mock()
        principal.user = user
        principal.scopes = ["read", "write"]
        principal.via = "jwt"

        # Create the guards
        require_user_guard = RequireUser()
        require_scopes_guard = RequireScopes("read")

        @app.get("/test")
        async def test_endpoint(
            user_principal=require_user_guard, scoped_principal=require_scopes_guard
        ):
            return {"user_id": user_principal.user.id, "scopes": scoped_principal.scopes}

        # Mock the underlying _current_principal dependency
        app.dependency_overrides[_current_principal] = lambda: principal

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test")

            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == "user_123"
            assert "read" in data["scopes"]

    @pytest.mark.asyncio
    async def test_service_with_any_scope(self, auth_client):
        """Test endpoint requiring service with any of multiple scopes."""
        app = FastAPI()

        # Create service principal with one scope
        api_key = Mock()
        api_key.id = "service_key_123"

        principal = Mock()
        principal.user = None
        principal.api_key = api_key
        principal.scopes = ["read"]  # Has "read" but not "write"
        principal.via = "api_key"

        # Create the guards
        require_service_guard = RequireService()
        require_any_scope_guard = RequireAnyScope("read", "write")

        @app.get("/test")
        async def test_endpoint(
            service_principal=require_service_guard, scoped_principal=require_any_scope_guard
        ):
            return {"api_key_id": service_principal.api_key.id, "scopes": scoped_principal.scopes}

        # Mock the underlying _current_principal dependency
        app.dependency_overrides[_current_principal] = lambda: principal

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/test")

            assert response.status_code == 200
            data = response.json()
            assert data["api_key_id"] == "service_key_123"
            assert "read" in data["scopes"]
