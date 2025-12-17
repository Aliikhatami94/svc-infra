"""Tests for WebSocket authentication.

Tests WSPrincipal, token extraction, JWT validation, scope enforcement,
and the various auth dependencies.
"""

import time
from unittest.mock import MagicMock

import jwt
import pytest

from svc_infra.api.fastapi.auth.ws_security import (
    RequireWSAnyScope,
    RequireWSScopes,
    WSPrincipal,
    _decode_jwt,
    _extract_token,
    _ws_current_principal,
    _ws_optional_principal,
    resolve_ws_bearer_principal,
)

pytestmark = pytest.mark.websocket


class TestWSPrincipal:
    """Test WSPrincipal dataclass."""

    def test_principal_with_all_fields(self):
        """WSPrincipal stores all fields."""
        principal = WSPrincipal(
            id="user-123",
            email="test@example.com",
            scopes=["read", "write"],
            claims={"sub": "user-123", "aud": "my-app"},
            via="query",
        )

        assert principal.id == "user-123"
        assert principal.email == "test@example.com"
        assert principal.scopes == ["read", "write"]
        assert principal.claims == {"sub": "user-123", "aud": "my-app"}
        assert principal.via == "query"

    def test_principal_with_defaults(self):
        """WSPrincipal has sensible defaults."""
        principal = WSPrincipal(id="user-123")

        assert principal.id == "user-123"
        assert principal.email is None
        assert principal.scopes == []
        assert principal.claims == {}
        assert principal.via == "query"


class TestTokenExtraction:
    """Test _extract_token() function."""

    def test_extract_from_query_param(self):
        """Extracts token from query parameter."""
        ws = MagicMock()
        ws.query_params = {"token": "jwt-token-here"}
        ws.headers = {}

        token, source = _extract_token(ws)

        assert token == "jwt-token-here"
        assert source == "query"

    def test_extract_from_authorization_header(self):
        """Extracts token from Authorization header."""
        ws = MagicMock()
        ws.query_params = {}
        ws.headers = {"authorization": "Bearer jwt-token-here"}

        token, source = _extract_token(ws)

        assert token == "jwt-token-here"
        assert source == "header"

    def test_extract_from_subprotocol(self):
        """Extracts token from Sec-WebSocket-Protocol header."""
        ws = MagicMock()
        ws.query_params = {}
        ws.headers = {"sec-websocket-protocol": "bearer, jwt-token-here"}

        token, source = _extract_token(ws)

        assert token == "jwt-token-here"
        assert source == "subprotocol"

    def test_extract_priority_query_over_header(self):
        """Query param takes priority over header."""
        ws = MagicMock()
        ws.query_params = {"token": "query-token"}
        ws.headers = {"authorization": "Bearer header-token"}

        token, source = _extract_token(ws)

        assert token == "query-token"
        assert source == "query"

    def test_extract_no_token(self):
        """Returns None when no token present."""
        ws = MagicMock()
        ws.query_params = {}
        ws.headers = {}

        token, source = _extract_token(ws)

        assert token is None
        assert source == ""

    def test_extract_empty_query_param(self):
        """Handles empty query param."""
        ws = MagicMock()
        ws.query_params = {"token": ""}
        ws.headers = {}

        token, source = _extract_token(ws)

        # Empty string should fall through
        assert token is None or token == ""


class TestJWTDecoding:
    """Test _decode_jwt() function."""

    def test_decode_valid_token(self):
        """Decodes valid JWT."""
        import os

        os.environ["AUTH_JWT__SECRET"] = "test-secret"

        # Reset settings
        from svc_infra.api.fastapi.auth import settings

        settings._settings = None

        secret = "test-secret"
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, secret, algorithm="HS256")

        result = _decode_jwt(token)

        assert result["sub"] == "user-123"
        assert result["email"] == "test@example.com"

    def test_decode_expired_token(self):
        """Raises WebSocketException for expired token."""
        import os

        os.environ["AUTH_JWT__SECRET"] = "test-secret"

        from svc_infra.api.fastapi.auth import settings

        settings._settings = None

        from fastapi import WebSocketException

        secret = "test-secret"
        payload = {
            "sub": "user-123",
            "exp": int(time.time()) - 3600,  # Expired
        }
        token = jwt.encode(payload, secret, algorithm="HS256")

        with pytest.raises(WebSocketException) as exc:
            _decode_jwt(token)

        assert "expired" in str(exc.value.reason).lower()

    def test_decode_invalid_signature(self):
        """Raises WebSocketException for invalid signature."""
        import os

        os.environ["AUTH_JWT__SECRET"] = "correct-secret"

        from svc_infra.api.fastapi.auth import settings

        settings._settings = None

        from fastapi import WebSocketException

        wrong_secret = "wrong-secret"
        payload = {
            "sub": "user-123",
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, wrong_secret, algorithm="HS256")

        with pytest.raises(WebSocketException) as exc:
            _decode_jwt(token)

        assert "invalid" in str(exc.value.reason).lower()


class TestResolveWSBearerPrincipal:
    """Test resolve_ws_bearer_principal() function."""

    @pytest.mark.asyncio
    async def test_resolve_returns_principal(self):
        """Returns WSPrincipal for valid token."""
        import os

        os.environ["AUTH_JWT__SECRET"] = "test-secret"

        from svc_infra.api.fastapi.auth import settings

        settings._settings = None

        secret = "test-secret"
        payload = {
            "sub": "user-123",
            "email": "test@example.com",
            "scopes": ["read", "write"],
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, secret, algorithm="HS256")

        ws = MagicMock()
        ws.query_params = {"token": token}
        ws.headers = {}

        principal = await resolve_ws_bearer_principal(ws)

        assert principal is not None
        assert principal.id == "user-123"
        assert principal.email == "test@example.com"
        assert principal.scopes == ["read", "write"]

    @pytest.mark.asyncio
    async def test_resolve_returns_none_without_token(self):
        """Returns None when no token present."""
        ws = MagicMock()
        ws.query_params = {}
        ws.headers = {}

        principal = await resolve_ws_bearer_principal(ws)

        assert principal is None


class TestWSCurrentPrincipal:
    """Test _ws_current_principal() dependency."""

    @pytest.mark.asyncio
    async def test_returns_principal_when_present(self):
        """Returns principal when authenticated."""
        ws = MagicMock()
        principal = WSPrincipal(id="user-123")

        result = await _ws_current_principal(ws, principal)

        assert result == principal

    @pytest.mark.asyncio
    async def test_raises_when_no_principal(self):
        """Raises WebSocketException when no principal."""
        from fastapi import WebSocketException

        ws = MagicMock()

        with pytest.raises(WebSocketException):
            await _ws_current_principal(ws, None)


class TestWSOptionalPrincipal:
    """Test _ws_optional_principal() dependency."""

    @pytest.mark.asyncio
    async def test_returns_principal_when_present(self):
        """Returns principal when authenticated."""
        ws = MagicMock()
        principal = WSPrincipal(id="user-123")

        result = await _ws_optional_principal(ws, principal)

        assert result == principal

    @pytest.mark.asyncio
    async def test_returns_none_when_no_principal(self):
        """Returns None when not authenticated."""
        ws = MagicMock()

        result = await _ws_optional_principal(ws, None)

        assert result is None


class TestRequireWSScopes:
    """Test RequireWSScopes guard."""

    @pytest.mark.asyncio
    async def test_allows_with_required_scopes(self):
        """Allows when all required scopes present."""

        principal = WSPrincipal(id="user-123", scopes=["read", "write", "admin"])

        # Get the guard function from the Depends
        guard_depends = RequireWSScopes("read", "write")
        guard_fn = guard_depends.dependency

        # Call the guard
        result = await guard_fn(principal)

        assert result == principal

    @pytest.mark.asyncio
    async def test_rejects_missing_scopes(self):
        """Rejects when required scopes missing."""
        from fastapi import WebSocketException

        principal = WSPrincipal(id="user-123", scopes=["read"])  # Missing "write"

        guard_depends = RequireWSScopes("read", "write")
        guard_fn = guard_depends.dependency

        with pytest.raises(WebSocketException):
            await guard_fn(principal)


class TestRequireWSAnyScope:
    """Test RequireWSAnyScope guard."""

    @pytest.mark.asyncio
    async def test_allows_with_any_required_scope(self):
        """Allows when any required scope present."""
        principal = WSPrincipal(id="user-123", scopes=["admin"])

        guard_depends = RequireWSAnyScope("admin", "moderator")
        guard_fn = guard_depends.dependency

        result = await guard_fn(principal)

        assert result == principal

    @pytest.mark.asyncio
    async def test_rejects_no_matching_scope(self):
        """Rejects when no required scopes present."""
        from fastapi import WebSocketException

        principal = WSPrincipal(id="user-123", scopes=["user"])

        guard_depends = RequireWSAnyScope("admin", "moderator")
        guard_fn = guard_depends.dependency

        with pytest.raises(WebSocketException):
            await guard_fn(principal)
