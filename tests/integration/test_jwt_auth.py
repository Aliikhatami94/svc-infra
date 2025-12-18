"""Integration tests for JWT authentication.

These tests verify JWT token generation, validation, and refresh flows.

Run with: pytest tests/integration/test_jwt_auth.py -v
"""

from __future__ import annotations

from datetime import timedelta

import pytest


@pytest.mark.integration
class TestJWTGeneration:
    """Integration tests for JWT token generation."""

    @pytest.fixture
    def jwt_config(self):
        """Create JWT configuration for testing."""
        from svc_infra.auth.jwt import JWTConfig

        return JWTConfig(
            secret_key="test_secret_key_32_chars_minimum!",
            algorithm="HS256",
            access_token_expire_minutes=15,
            refresh_token_expire_days=7,
            issuer="test-issuer",
            audience="test-audience",
        )

    def test_generate_access_token(self, jwt_config):
        """Test generating an access token."""
        from svc_infra.auth.jwt import JWTService

        service = JWTService(config=jwt_config)

        token = service.create_access_token(
            user_id="user_123",
            email="user@example.com",
            scopes=["read", "write"],
        )

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are typically long
        assert token.count(".") == 2  # JWT has 3 parts separated by dots

    def test_generate_refresh_token(self, jwt_config):
        """Test generating a refresh token."""
        from svc_infra.auth.jwt import JWTService

        service = JWTService(config=jwt_config)

        token = service.create_refresh_token(
            user_id="user_123",
        )

        assert token is not None
        assert isinstance(token, str)
        assert token.count(".") == 2

    def test_token_contains_claims(self, jwt_config):
        """Test that token contains expected claims."""
        from svc_infra.auth.jwt import JWTService

        service = JWTService(config=jwt_config)

        token = service.create_access_token(
            user_id="user_456",
            email="test@example.com",
            scopes=["admin"],
            extra_claims={"tenant_id": "tenant_789"},
        )

        # Decode without verification to inspect claims
        payload = service.decode_token(token)

        assert payload["sub"] == "user_456"
        assert payload["email"] == "test@example.com"
        assert payload["scopes"] == ["admin"]
        assert payload["tenant_id"] == "tenant_789"
        assert payload["iss"] == "test-issuer"
        assert payload["aud"] == "test-audience"


@pytest.mark.integration
class TestJWTValidation:
    """Integration tests for JWT token validation."""

    @pytest.fixture
    def jwt_service(self):
        """Create JWT service for testing."""
        from svc_infra.auth.jwt import JWTConfig, JWTService

        config = JWTConfig(
            secret_key="test_secret_key_32_chars_minimum!",
            algorithm="HS256",
            access_token_expire_minutes=15,
            refresh_token_expire_days=7,
            issuer="test-issuer",
            audience="test-audience",
        )
        return JWTService(config=config)

    def test_validate_valid_token(self, jwt_service):
        """Test validating a valid token."""
        token = jwt_service.create_access_token(
            user_id="user_123",
            email="user@example.com",
        )

        payload = jwt_service.verify_token(token)

        assert payload is not None
        assert payload["sub"] == "user_123"
        assert payload["email"] == "user@example.com"

    def test_validate_invalid_signature(self, jwt_service):
        """Test that invalid signatures are rejected."""
        from svc_infra.auth.jwt import JWTError

        token = jwt_service.create_access_token(
            user_id="user_123",
            email="user@example.com",
        )

        # Tamper with the token
        parts = token.split(".")
        parts[2] = "invalid_signature"
        tampered_token = ".".join(parts)

        with pytest.raises(JWTError):
            jwt_service.verify_token(tampered_token)

    def test_validate_malformed_token(self, jwt_service):
        """Test that malformed tokens are rejected."""
        from svc_infra.auth.jwt import JWTError

        with pytest.raises(JWTError):
            jwt_service.verify_token("not.a.valid.jwt.token")

        with pytest.raises(JWTError):
            jwt_service.verify_token("completely_invalid")


@pytest.mark.integration
class TestJWTExpiration:
    """Integration tests for JWT token expiration."""

    @pytest.fixture
    def short_lived_service(self):
        """Create JWT service with very short expiration."""
        from svc_infra.auth.jwt import JWTConfig, JWTService

        config = JWTConfig(
            secret_key="test_secret_key_32_chars_minimum!",
            algorithm="HS256",
            access_token_expire_minutes=0,  # Expires immediately (for testing)
            refresh_token_expire_days=0,
            issuer="test-issuer",
            audience="test-audience",
        )
        return JWTService(config=config)

    def test_expired_token_rejected(self):
        """Test that expired tokens are rejected."""
        from svc_infra.auth.jwt import JWTConfig, JWTError, JWTService

        # Create service with custom expiration in the past
        config = JWTConfig(
            secret_key="test_secret_key_32_chars_minimum!",
            algorithm="HS256",
            access_token_expire_minutes=15,
            refresh_token_expire_days=7,
            issuer="test-issuer",
            audience="test-audience",
        )
        service = JWTService(config=config)

        # Create token that's already expired
        token = service.create_access_token(
            user_id="user_123",
            email="user@example.com",
            expires_delta=timedelta(seconds=-1),  # Already expired
        )

        with pytest.raises(JWTError) as exc_info:
            service.verify_token(token)

        assert "expired" in str(exc_info.value).lower()

    def test_token_valid_before_expiration(self):
        """Test that token is valid before expiration."""
        from svc_infra.auth.jwt import JWTConfig, JWTService

        config = JWTConfig(
            secret_key="test_secret_key_32_chars_minimum!",
            algorithm="HS256",
            access_token_expire_minutes=60,  # 1 hour
            refresh_token_expire_days=7,
            issuer="test-issuer",
            audience="test-audience",
        )
        service = JWTService(config=config)

        token = service.create_access_token(
            user_id="user_123",
            email="user@example.com",
        )

        # Should be valid
        payload = service.verify_token(token)
        assert payload["sub"] == "user_123"


@pytest.mark.integration
class TestJWTRefreshFlow:
    """Integration tests for JWT refresh token flow."""

    @pytest.fixture
    def jwt_service(self):
        """Create JWT service for testing."""
        from svc_infra.auth.jwt import JWTConfig, JWTService

        config = JWTConfig(
            secret_key="test_secret_key_32_chars_minimum!",
            algorithm="HS256",
            access_token_expire_minutes=15,
            refresh_token_expire_days=7,
            issuer="test-issuer",
            audience="test-audience",
        )
        return JWTService(config=config)

    def test_refresh_token_flow(self, jwt_service):
        """Test complete refresh token flow."""
        # Generate initial tokens
        access_token = jwt_service.create_access_token(
            user_id="user_123",
            email="user@example.com",
        )
        refresh_token = jwt_service.create_refresh_token(
            user_id="user_123",
        )

        # Verify refresh token
        refresh_payload = jwt_service.verify_token(refresh_token)
        assert refresh_payload["sub"] == "user_123"
        assert refresh_payload["type"] == "refresh"

        # Use refresh token to get new access token
        new_access_token = jwt_service.refresh_access_token(
            refresh_token=refresh_token,
            email="user@example.com",  # Re-fetch from database in real scenario
        )

        assert new_access_token is not None
        assert new_access_token != access_token  # New token should be different

        # Verify new access token
        new_payload = jwt_service.verify_token(new_access_token)
        assert new_payload["sub"] == "user_123"

    def test_refresh_with_invalid_token(self, jwt_service):
        """Test refresh with invalid token fails."""
        from svc_infra.auth.jwt import JWTError

        with pytest.raises(JWTError):
            jwt_service.refresh_access_token(
                refresh_token="invalid_token",
                email="user@example.com",
            )

    def test_refresh_with_access_token_fails(self, jwt_service):
        """Test that using access token as refresh token fails."""
        from svc_infra.auth.jwt import JWTError

        access_token = jwt_service.create_access_token(
            user_id="user_123",
            email="user@example.com",
        )

        # Should fail because it's an access token, not refresh token
        with pytest.raises(JWTError):
            jwt_service.refresh_access_token(
                refresh_token=access_token,
                email="user@example.com",
            )
