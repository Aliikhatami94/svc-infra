"""Integration tests for billing service with Stripe.

These tests require Stripe test keys to be set:
- STRIPE_API_KEY or STRIPE_SECRET_KEY: Stripe test secret key

Run with: pytest tests/integration/test_billing_stripe.py -v
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

# Skip marker for missing Stripe key
SKIP_NO_STRIPE = pytest.mark.skipif(
    not (os.environ.get("STRIPE_API_KEY") or os.environ.get("STRIPE_SECRET_KEY")),
    reason="STRIPE_API_KEY not set",
)


# =============================================================================
# Stripe Integration Tests (Requires API Key)
# =============================================================================


@SKIP_NO_STRIPE
@pytest.mark.integration
class TestStripeIntegration:
    """Integration tests with real Stripe test API.

    These tests use Stripe test mode and will create test objects.
    Ensure STRIPE_API_KEY is a test key (sk_test_...).
    """

    @pytest.fixture
    def stripe_client(self):
        """Get Stripe client with test API key."""
        import stripe

        api_key = os.environ.get("STRIPE_API_KEY") or os.environ.get("STRIPE_SECRET_KEY")
        stripe.api_key = api_key

        # Verify it's a test key
        if not api_key.startswith("sk_test_"):
            pytest.skip("STRIPE_API_KEY must be a test key (sk_test_...)")

        return stripe

    def test_stripe_connection(self, stripe_client):
        """Test basic Stripe API connection."""
        # List customers to verify connection
        customers = stripe_client.Customer.list(limit=1)
        assert hasattr(customers, "data")

    def test_create_test_customer(self, stripe_client):
        """Test creating a test customer."""
        customer = stripe_client.Customer.create(
            email="test@example.com",
            name="Test Customer",
            metadata={"test": "true", "integration_test": "svc-infra"},
        )

        assert customer.id.startswith("cus_")
        assert customer.email == "test@example.com"

        # Cleanup
        stripe_client.Customer.delete(customer.id)

    def test_create_test_product_and_price(self, stripe_client):
        """Test creating a test product with price."""
        # Create product
        product = stripe_client.Product.create(
            name="Test API Calls",
            metadata={"test": "true", "integration_test": "svc-infra"},
        )

        assert product.id.startswith("prod_")

        # Create metered price
        price = stripe_client.Price.create(
            product=product.id,
            currency="usd",
            recurring={
                "interval": "month",
                "usage_type": "metered",
            },
            unit_amount_decimal="0.001",  # $0.001 per unit
            metadata={"test": "true"},
        )

        assert price.id.startswith("price_")
        assert price.recurring["usage_type"] == "metered"

        # Cleanup
        stripe_client.Product.modify(product.id, active=False)

    def test_webhook_signature_verification(self, stripe_client):
        """Test Stripe webhook signature verification."""
        import hashlib
        import hmac
        import time

        from stripe import WebhookSignature

        payload = '{"type": "customer.created"}'
        secret = "whsec_test_secret"
        timestamp = int(time.time())

        # Create signature
        signed_payload = f"{timestamp}.{payload}"
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        header = f"t={timestamp},v1={expected_sig}"

        # Verify signature
        try:
            WebhookSignature.verify_header(
                payload=payload,
                header=header,
                secret=secret,
                tolerance=300,
            )
        except Exception as e:
            # Expected to work with correct signature
            pytest.fail(f"Webhook signature verification failed: {e}")


# =============================================================================
# Billing Models Tests
# =============================================================================


@pytest.mark.integration
class TestBillingModels:
    """Integration tests for billing models."""

    def test_usage_event_model(self):
        """Test UsageEvent model structure."""
        from svc_infra.billing import UsageEvent

        event = UsageEvent(
            id="test-id",
            tenant_id="tenant_123",
            metric="api_calls",
            amount=100,
            at_ts=datetime.now(UTC),
            idempotency_key="unique",
            metadata_json={"key": "value"},
        )

        assert event.metric == "api_calls"
        assert event.amount == 100

    def test_invoice_model(self):
        """Test Invoice model structure."""
        from svc_infra.billing import Invoice

        invoice = Invoice(
            id="inv_test",
            tenant_id="tenant_123",
            period_start=datetime(2024, 1, 1, tzinfo=UTC),
            period_end=datetime(2024, 2, 1, tzinfo=UTC),
            status="created",
            total_amount=1000,
            currency="USD",
        )

        assert invoice.status == "created"
        assert invoice.total_amount == 1000

    def test_plan_model(self):
        """Test Plan model structure."""
        from svc_infra.billing import Plan

        plan = Plan(
            id="plan_test",
            tenant_id="tenant_123",
            name="Pro Plan",
            description="Professional tier",
            stripe_product_id="prod_xxx",
        )

        assert plan.name == "Pro Plan"
