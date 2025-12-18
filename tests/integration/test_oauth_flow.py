"""Integration tests for OAuth authentication flow.

These tests verify OAuth authorization, token exchange, and user creation.
Uses mocked OAuth provider for testing without real OAuth setup.

Run with: pytest tests/integration/test_oauth_flow.py -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.integration
class TestOAuthAuthorization:
    """Integration tests for OAuth authorization flow."""

    @pytest.fixture
    def mock_oauth_client(self):
        """Create a mock OAuth client."""
        client = MagicMock()
        client.authorization_endpoint = "https://oauth.example.com/authorize"
        client.token_endpoint = "https://oauth.example.com/token"
        client.userinfo_endpoint = "https://oauth.example.com/userinfo"
        return client

    def test_authorization_url_generation(self, mock_oauth_client):
        """Test generating OAuth authorization URL."""
        from svc_infra.auth.oauth import OAuthConfig

        config = OAuthConfig(
            client_id="test_client_id",
            client_secret="test_client_secret",
            authorize_url="https://oauth.example.com/authorize",
            token_url="https://oauth.example.com/token",
            scopes=["openid", "email", "profile"],
        )

        # Generate authorization URL
        auth_url = config.get_authorization_url(
            redirect_uri="https://app.example.com/callback",
            state="random_state_123",
        )

        assert "https://oauth.example.com/authorize" in auth_url
        assert "client_id=test_client_id" in auth_url
        assert "state=random_state_123" in auth_url
        assert "redirect_uri=" in auth_url

    def test_authorization_url_with_pkce(self, mock_oauth_client):
        """Test generating OAuth authorization URL with PKCE."""
        from svc_infra.auth.oauth import OAuthConfig

        config = OAuthConfig(
            client_id="test_client_id",
            client_secret="test_client_secret",
            authorize_url="https://oauth.example.com/authorize",
            token_url="https://oauth.example.com/token",
            scopes=["openid", "email"],
            use_pkce=True,
        )

        auth_url, code_verifier = config.get_authorization_url_with_pkce(
            redirect_uri="https://app.example.com/callback",
            state="random_state_123",
        )

        assert "code_challenge=" in auth_url
        assert "code_challenge_method=S256" in auth_url
        assert code_verifier is not None
        assert len(code_verifier) >= 43  # PKCE verifier minimum length


@pytest.mark.integration
class TestOAuthTokenExchange:
    """Integration tests for OAuth token exchange."""

    @pytest.fixture
    def mock_token_response(self):
        """Mock token response from OAuth provider."""
        return {
            "access_token": "mock_access_token_12345",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "mock_refresh_token_67890",
            "id_token": "mock_id_token_abcdef",
            "scope": "openid email profile",
        }

    @pytest.mark.asyncio
    async def test_token_exchange(self, mock_token_response):
        """Test exchanging authorization code for tokens."""
        from svc_infra.auth.oauth import OAuthConfig

        config = OAuthConfig(
            client_id="test_client_id",
            client_secret="test_client_secret",
            authorize_url="https://oauth.example.com/authorize",
            token_url="https://oauth.example.com/token",
            scopes=["openid", "email"],
        )

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_token_response,
            )

            tokens = await config.exchange_code(
                code="auth_code_xyz",
                redirect_uri="https://app.example.com/callback",
            )

            assert tokens["access_token"] == "mock_access_token_12345"
            assert tokens["refresh_token"] == "mock_refresh_token_67890"
            assert tokens["token_type"] == "Bearer"

    @pytest.mark.asyncio
    async def test_token_exchange_error(self):
        """Test handling token exchange errors."""
        from svc_infra.auth.oauth import OAuthConfig, OAuthError

        config = OAuthConfig(
            client_id="test_client_id",
            client_secret="test_client_secret",
            authorize_url="https://oauth.example.com/authorize",
            token_url="https://oauth.example.com/token",
            scopes=["openid", "email"],
        )

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=400,
                json=lambda: {
                    "error": "invalid_grant",
                    "error_description": "Authorization code expired",
                },
            )

            with pytest.raises(OAuthError) as exc_info:
                await config.exchange_code(
                    code="expired_code",
                    redirect_uri="https://app.example.com/callback",
                )

            assert "invalid_grant" in str(exc_info.value)


@pytest.mark.integration
class TestOAuthTokenRefresh:
    """Integration tests for OAuth token refresh."""

    @pytest.mark.asyncio
    async def test_refresh_token(self):
        """Test refreshing access token."""
        from svc_infra.auth.oauth import OAuthConfig

        config = OAuthConfig(
            client_id="test_client_id",
            client_secret="test_client_secret",
            authorize_url="https://oauth.example.com/authorize",
            token_url="https://oauth.example.com/token",
            scopes=["openid", "email"],
        )

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=200,
                json=lambda: {
                    "access_token": "new_access_token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "refresh_token": "new_refresh_token",
                },
            )

            tokens = await config.refresh_access_token(
                refresh_token="old_refresh_token",
            )

            assert tokens["access_token"] == "new_access_token"
            assert tokens["refresh_token"] == "new_refresh_token"

    @pytest.mark.asyncio
    async def test_refresh_token_expired(self):
        """Test handling expired refresh token."""
        from svc_infra.auth.oauth import OAuthConfig, OAuthError

        config = OAuthConfig(
            client_id="test_client_id",
            client_secret="test_client_secret",
            authorize_url="https://oauth.example.com/authorize",
            token_url="https://oauth.example.com/token",
            scopes=["openid", "email"],
        )

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock(
                status_code=400,
                json=lambda: {
                    "error": "invalid_grant",
                    "error_description": "Refresh token expired",
                },
            )

            with pytest.raises(OAuthError):
                await config.refresh_access_token(
                    refresh_token="expired_refresh_token",
                )


@pytest.mark.integration
class TestOAuthUserCreation:
    """Integration tests for OAuth user creation."""

    @pytest.fixture
    def mock_userinfo(self):
        """Mock userinfo response from OAuth provider."""
        return {
            "sub": "oauth_user_id_123",
            "email": "user@example.com",
            "email_verified": True,
            "name": "Test User",
            "picture": "https://example.com/avatar.jpg",
        }

    @pytest.mark.asyncio
    async def test_fetch_userinfo(self, mock_userinfo):
        """Test fetching user info from OAuth provider."""
        from svc_infra.auth.oauth import OAuthConfig

        config = OAuthConfig(
            client_id="test_client_id",
            client_secret="test_client_secret",
            authorize_url="https://oauth.example.com/authorize",
            token_url="https://oauth.example.com/token",
            userinfo_url="https://oauth.example.com/userinfo",
            scopes=["openid", "email", "profile"],
        )

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_userinfo,
            )

            userinfo = await config.fetch_userinfo(
                access_token="valid_access_token",
            )

            assert userinfo["email"] == "user@example.com"
            assert userinfo["sub"] == "oauth_user_id_123"
            assert userinfo["email_verified"] is True

    @pytest.mark.asyncio
    async def test_create_or_update_user_from_oauth(self, mock_userinfo):
        """Test creating/updating user from OAuth data."""
        from svc_infra.auth.oauth import OAuthUserManager

        # Mock database session
        mock_session = MagicMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: None))
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        manager = OAuthUserManager(session=mock_session)

        await manager.get_or_create_user(
            provider="google",
            oauth_id=mock_userinfo["sub"],
            email=mock_userinfo["email"],
            name=mock_userinfo.get("name"),
            picture=mock_userinfo.get("picture"),
        )

        # Verify user was created
        mock_session.add.assert_called_once()
