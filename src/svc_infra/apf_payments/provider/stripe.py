from __future__ import annotations

from typing import Any, Optional

from ..schemas import CustomerOut, CustomerUpsertIn, IntentCreateIn, IntentOut, NextAction, RefundIn
from ..settings import get_payments_settings
from .base import ProviderAdapter

# Import lazily to avoid hard dependency if not used
try:
    import stripe
except Exception:  # pragma: no cover
    stripe = None  # type: ignore


class StripeAdapter(ProviderAdapter):
    name = "stripe"

    def __init__(self):
        st = get_payments_settings()
        if not st.stripe or not st.stripe.secret_key.get_secret_value():
            raise RuntimeError("Stripe settings not configured")
        if stripe is None:
            raise RuntimeError("stripe SDK is not installed. pip install stripe")
        stripe.api_key = st.stripe.secret_key.get_secret_value()
        self._wh_secret = (
            st.stripe.webhook_secret.get_secret_value() if st.stripe.webhook_secret else None
        )

    async def ensure_customer(self, data: CustomerUpsertIn) -> CustomerOut:
        assert stripe
        # try by email (idempotent enough for demo; production can map via your DB)
        if data.email:
            existing = stripe.Customer.list(email=data.email, limit=1).data
            if existing:
                c = existing[0]
            else:
                c = stripe.Customer.create(
                    email=data.email,
                    name=data.name or None,
                    metadata={"user_id": data.user_id or ""},
                )
        else:
            c = stripe.Customer.create(
                name=data.name or None, metadata={"user_id": data.user_id or ""}
            )
        return CustomerOut(
            id=c.id,
            provider="stripe",
            provider_customer_id=c.id,
            email=c.get("email"),
            name=c.get("name"),
        )

    async def get_customer(self, provider_customer_id: str) -> Optional[CustomerOut]:
        assert stripe
        c = stripe.Customer.retrieve(provider_customer_id)
        return CustomerOut(
            id=c.id,
            provider="stripe",
            provider_customer_id=c.id,
            email=c.get("email"),
            name=c.get("name"),
        )

    async def create_intent(self, data: IntentCreateIn, *, user_id: str | None) -> IntentOut:
        assert stripe
        kwargs: dict[str, Any] = dict(
            amount=int(data.amount),
            currency=data.currency.lower(),
            description=data.description or None,
            capture_method="manual" if data.capture_method == "manual" else "automatic",
            automatic_payment_methods={"enabled": True} if not data.payment_method_types else None,
        )
        if data.payment_method_types:
            kwargs["payment_method_types"] = data.payment_method_types
        pi = stripe.PaymentIntent.create(**{k: v for k, v in kwargs.items() if v is not None})
        return IntentOut(
            id=pi.id,
            provider="stripe",
            provider_intent_id=pi.id,
            status=pi.status,
            amount=int(pi.amount),
            currency=pi.currency.upper(),
            client_secret=pi.client_secret,
            next_action=NextAction(type=getattr(getattr(pi, "next_action", None), "type", None)),
        )

    async def confirm_intent(self, provider_intent_id: str) -> IntentOut:
        assert stripe
        pi = stripe.PaymentIntent.confirm(provider_intent_id)
        return IntentOut(
            id=pi.id,
            provider="stripe",
            provider_intent_id=pi.id,
            status=pi.status,
            amount=int(pi.amount),
            currency=pi.currency.upper(),
            client_secret=getattr(pi, "client_secret", None),
            next_action=NextAction(type=getattr(getattr(pi, "next_action", None), "type", None)),
        )

    async def cancel_intent(self, provider_intent_id: str) -> IntentOut:
        assert stripe
        pi = stripe.PaymentIntent.cancel(provider_intent_id)
        return IntentOut(
            id=pi.id,
            provider="stripe",
            provider_intent_id=pi.id,
            status=pi.status,
            amount=int(pi.amount),
            currency=pi.currency.upper(),
        )

    async def refund(self, provider_intent_id: str, data: RefundIn) -> IntentOut:
        assert stripe
        # Stripe refunds are created against charges; simplify via PaymentIntent last charge
        pi = stripe.PaymentIntent.retrieve(provider_intent_id, expand=["latest_charge"])
        charge_id = pi.latest_charge.id if getattr(pi, "latest_charge", None) else None
        if not charge_id:
            raise ValueError("No charge available to refund")
        stripe.Refund.create(charge=charge_id, amount=int(data.amount) if data.amount else None)
        # Re-hydrate
        return await self.hydrate_intent(provider_intent_id)

    async def verify_and_parse_webhook(
        self, signature: str | None, payload: bytes
    ) -> dict[str, Any]:
        assert stripe
        if not self._wh_secret:
            raise ValueError("Stripe webhook secret not configured")
        event = stripe.Webhook.construct_event(
            payload=payload, sig_header=signature, secret=self._wh_secret
        )
        return {"id": event.id, "type": event.type, "data": event.data.object}

    async def hydrate_intent(self, provider_intent_id: str) -> IntentOut:
        assert stripe
        pi = stripe.PaymentIntent.retrieve(provider_intent_id)
        return IntentOut(
            id=pi.id,
            provider="stripe",
            provider_intent_id=pi.id,
            status=pi.status,
            amount=int(pi.amount),
            currency=pi.currency.upper(),
            client_secret=getattr(pi, "client_secret", None),
            next_action=NextAction(type=getattr(getattr(pi, "next_action", None), "type", None)),
        )
