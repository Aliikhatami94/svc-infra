import pytest


@pytest.mark.asyncio
async def test_create_intent_maps_fields(monkeypatch, mocker):
    monkeypatch.setenv("STRIPE_SECRET", "sk_test_123")
    from svc_infra.apf_payments.provider.stripe import StripeAdapter
    from svc_infra.apf_payments.provider.stripe import stripe as stripe_sdk

    adapter = StripeAdapter()

    pi = mocker.Mock(
        id="pi_1",
        status="requires_payment_method",
        amount=1234,
        currency="usd",
        client_secret="cs",
    )
    pi.next_action = None  # <-- important: avoid Mock here

    monkeypatch.setattr(stripe_sdk.PaymentIntent, "create", lambda **kw: pi)

    out = await adapter.create_intent(
        mocker.Mock(
            amount=1234, currency="USD", capture_method="automatic", payment_method_types=[]
        ),
        user_id=None,
    )
    assert out.provider_intent_id == "pi_1"
    assert out.currency == "USD"
