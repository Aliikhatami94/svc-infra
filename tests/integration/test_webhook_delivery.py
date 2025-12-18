"""Integration tests for webhook delivery.

These tests verify webhook creation, delivery, signature verification,
retry logic, and dead letter handling.

Run with: pytest tests/integration/test_webhook_delivery.py -v
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.integration
class TestWebhookCreation:
    """Integration tests for webhook endpoint creation."""

    @pytest.fixture
    def db_session(self, tmp_path):
        """Create a temporary SQLite database for testing."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        db_path = tmp_path / "test_webhooks.db"
        engine = create_engine(f"sqlite:///{db_path}", echo=False)

        # Create tables
        from svc_infra.webhooks.models import Base

        Base.metadata.create_all(engine)

        with Session(engine) as session:
            yield session
            session.rollback()

    def test_create_webhook_endpoint(self, db_session):
        """Test creating a webhook endpoint."""
        from svc_infra.webhooks import WebhookService

        service = WebhookService(session=db_session, tenant_id="tenant_123")

        endpoint = service.create_endpoint(
            url="https://example.com/webhook",
            events=["order.created", "order.updated"],
            description="Order webhooks",
        )

        assert endpoint is not None
        assert endpoint.url == "https://example.com/webhook"
        assert endpoint.secret is not None
        assert len(endpoint.secret) >= 32
        assert "order.created" in endpoint.events

    def test_create_endpoint_generates_secret(self, db_session):
        """Test that endpoint creation generates a unique secret."""
        from svc_infra.webhooks import WebhookService

        service = WebhookService(session=db_session, tenant_id="tenant_123")

        endpoint1 = service.create_endpoint(
            url="https://example1.com/webhook",
            events=["user.created"],
        )
        endpoint2 = service.create_endpoint(
            url="https://example2.com/webhook",
            events=["user.created"],
        )

        assert endpoint1.secret != endpoint2.secret

    def test_list_endpoints(self, db_session):
        """Test listing webhook endpoints."""
        from svc_infra.webhooks import WebhookService

        service = WebhookService(session=db_session, tenant_id="tenant_123")

        # Create multiple endpoints
        service.create_endpoint(url="https://a.com/webhook", events=["event.a"])
        service.create_endpoint(url="https://b.com/webhook", events=["event.b"])

        endpoints = service.list_endpoints()

        assert len(endpoints) >= 2


@pytest.mark.integration
class TestWebhookSignature:
    """Integration tests for webhook signature verification."""

    def test_sign_payload(self):
        """Test signing a webhook payload."""
        from svc_infra.webhooks import WebhookSigner

        signer = WebhookSigner(secret="test_secret_key")
        payload = '{"event": "order.created", "data": {"id": 123}}'

        signature = signer.sign(payload, timestamp=1234567890)

        assert signature is not None
        assert signature.startswith("v1=")
        assert len(signature) > 10

    def test_verify_signature_valid(self):
        """Test verifying a valid signature."""
        from svc_infra.webhooks import WebhookSigner

        secret = "test_secret_key"
        signer = WebhookSigner(secret=secret)
        payload = '{"event": "order.created"}'
        timestamp = int(time.time())

        signature = signer.sign(payload, timestamp=timestamp)

        assert (
            signer.verify(
                payload=payload,
                signature=signature,
                timestamp=timestamp,
                tolerance=300,
            )
            is True
        )

    def test_verify_signature_invalid(self):
        """Test that invalid signatures are rejected."""
        from svc_infra.webhooks import WebhookSigner

        signer = WebhookSigner(secret="correct_secret")
        payload = '{"event": "order.created"}'
        timestamp = int(time.time())

        # Sign with correct secret
        signature = signer.sign(payload, timestamp=timestamp)

        # Verify with wrong secret should fail
        wrong_signer = WebhookSigner(secret="wrong_secret")
        assert (
            wrong_signer.verify(
                payload=payload,
                signature=signature,
                timestamp=timestamp,
                tolerance=300,
            )
            is False
        )

    def test_verify_signature_expired(self):
        """Test that expired signatures are rejected."""
        from svc_infra.webhooks import WebhookSigner

        signer = WebhookSigner(secret="test_secret")
        payload = '{"event": "order.created"}'
        old_timestamp = int(time.time()) - 600  # 10 minutes ago

        signature = signer.sign(payload, timestamp=old_timestamp)

        # Should fail with default 5-minute tolerance
        assert (
            signer.verify(
                payload=payload,
                signature=signature,
                timestamp=old_timestamp,
                tolerance=300,  # 5 minutes
            )
            is False
        )


@pytest.mark.integration
class TestWebhookDelivery:
    """Integration tests for webhook delivery."""

    @pytest.fixture
    def webhook_service(self, tmp_path):
        """Create webhook service with test database."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from svc_infra.webhooks import WebhookService
        from svc_infra.webhooks.models import Base

        db_path = tmp_path / "test_webhooks.db"
        engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(engine)

        session = Session(engine)
        return WebhookService(session=session, tenant_id="tenant_123")

    @pytest.mark.asyncio
    async def test_deliver_webhook(self, webhook_service):
        """Test delivering a webhook."""
        # Create endpoint
        webhook_service.create_endpoint(
            url="https://example.com/webhook",
            events=["order.created"],
        )

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)

            result = await webhook_service.deliver(
                event="order.created",
                payload={"order_id": "123", "total": 99.99},
            )

            assert result.success is True
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_delivery_includes_signature(self, webhook_service):
        """Test that delivery includes signature headers."""
        webhook_service.create_endpoint(
            url="https://example.com/webhook",
            events=["order.created"],
        )

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)

            await webhook_service.deliver(
                event="order.created",
                payload={"order_id": "123"},
            )

            # Verify signature header was included
            call_kwargs = mock_post.call_args[1]
            headers = call_kwargs.get("headers", {})
            assert "X-Webhook-Signature" in headers or "X-Signature" in headers


@pytest.mark.integration
class TestWebhookRetry:
    """Integration tests for webhook retry logic."""

    @pytest.fixture
    def webhook_service(self, tmp_path):
        """Create webhook service with test database."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from svc_infra.webhooks import WebhookService
        from svc_infra.webhooks.models import Base

        db_path = tmp_path / "test_webhooks.db"
        engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(engine)

        session = Session(engine)
        return WebhookService(session=session, tenant_id="tenant_123")

    @pytest.mark.asyncio
    async def test_retry_on_failure(self, webhook_service):
        """Test that failed deliveries are retried."""
        webhook_service.create_endpoint(
            url="https://example.com/webhook",
            events=["order.created"],
        )

        call_count = 0

        async def mock_post_with_failures(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Connection failed")
            return MagicMock(status_code=200)

        with patch("httpx.AsyncClient.post", side_effect=mock_post_with_failures):
            result = await webhook_service.deliver_with_retry(
                event="order.created",
                payload={"order_id": "123"},
                max_retries=3,
                retry_delay=0.01,
            )

            assert result.success is True
            assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, webhook_service):
        """Test behavior when max retries are exceeded."""
        webhook_service.create_endpoint(
            url="https://example.com/webhook",
            events=["order.created"],
        )

        async def always_fail(*args, **kwargs):
            raise Exception("Connection failed")

        with patch("httpx.AsyncClient.post", side_effect=always_fail):
            result = await webhook_service.deliver_with_retry(
                event="order.created",
                payload={"order_id": "123"},
                max_retries=3,
                retry_delay=0.01,
            )

            assert result.success is False
            assert result.attempts == 3


@pytest.mark.integration
class TestWebhookDeadLetter:
    """Integration tests for webhook dead letter handling."""

    @pytest.fixture
    def webhook_service(self, tmp_path):
        """Create webhook service with test database."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from svc_infra.webhooks import WebhookService
        from svc_infra.webhooks.models import Base

        db_path = tmp_path / "test_webhooks.db"
        engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(engine)

        session = Session(engine)
        return WebhookService(session=session, tenant_id="tenant_123")

    @pytest.mark.asyncio
    async def test_failed_delivery_stored(self, webhook_service):
        """Test that failed deliveries are stored for later inspection."""
        webhook_service.create_endpoint(
            url="https://example.com/webhook",
            events=["order.created"],
        )

        async def always_fail(*args, **kwargs):
            raise Exception("Connection failed")

        with patch("httpx.AsyncClient.post", side_effect=always_fail):
            await webhook_service.deliver_with_retry(
                event="order.created",
                payload={"order_id": "123"},
                max_retries=1,
                retry_delay=0.01,
            )

        # Check dead letter queue
        dead_letters = webhook_service.list_dead_letters()
        assert len(dead_letters) >= 1
        assert dead_letters[0].event == "order.created"

    @pytest.mark.asyncio
    async def test_replay_dead_letter(self, webhook_service):
        """Test replaying a dead letter."""
        endpoint = webhook_service.create_endpoint(
            url="https://example.com/webhook",
            events=["order.created"],
        )

        # Store a dead letter
        dead_letter_id = webhook_service.store_dead_letter(
            endpoint_id=endpoint.id,
            event="order.created",
            payload={"order_id": "123"},
            error="Original failure",
        )

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)

            result = await webhook_service.replay_dead_letter(dead_letter_id)

            assert result.success is True
            mock_post.assert_called_once()
