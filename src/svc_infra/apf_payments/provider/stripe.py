from __future__ import annotations

from functools import partial
from typing import Any, Optional

import anyio

from ..schemas import (
    CustomerOut,
    CustomerUpsertIn,
    IntentCreateIn,
    IntentOut,
    InvoiceLineItemIn,
    InvoiceOut,
    NextAction,
    RefundIn,
    UsageRecordIn,
)
from ..settings import get_payments_settings
from .base import ProviderAdapter

try:
    import stripe
except Exception:  # pragma: no cover
    stripe = None  # type: ignore


async def _acall(fn, /, *args, **kwargs):
    return await anyio.to_thread.run_sync(partial(fn, *args, **kwargs))


def _pi_to_out(pi) -> IntentOut:
    return IntentOut(
        id=pi.id,
        provider="stripe",
        provider_intent_id=pi.id,
        status=pi.status,
        amount=int(pi.amount),
        currency=str(pi.currency).upper(),
        client_secret=getattr(pi, "client_secret", None),
        next_action=NextAction(type=getattr(getattr(pi, "next_action", None), "type", None)),
    )


def _inv_to_out(inv) -> InvoiceOut:
    return InvoiceOut(
        id=inv.id,
        provider="stripe",
        provider_invoice_id=inv.id,
        provider_customer_id=inv.customer,
        status=inv.status,
        amount_due=int(inv.amount_due or 0),
        currency=str(inv.currency).upper(),
        hosted_invoice_url=getattr(inv, "hosted_invoice_url", None),
        pdf_url=getattr(inv, "invoice_pdf", None),
    )


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
        # try by email (idempotent enough for demo; production can map via your DB)
        if data.email:
            existing = await _acall(stripe.Customer.list, email=data.email, limit=1)
            c = (
                existing.data[0]
                if existing.data
                else await _acall(
                    stripe.Customer.create,
                    email=data.email,
                    name=data.name or None,
                    metadata={"user_id": data.user_id or ""},
                )
            )
        else:
            c = await _acall(
                stripe.Customer.create,
                name=data.name or None,
                metadata={"user_id": data.user_id or ""},
            )
        return CustomerOut(
            id=c.id,
            provider="stripe",
            provider_customer_id=c.id,
            email=c.get("email"),
            name=c.get("name"),
        )

    async def get_customer(self, provider_customer_id: str) -> Optional[CustomerOut]:
        c = await _acall(stripe.Customer.retrieve, provider_customer_id)
        return CustomerOut(
            id=c.id,
            provider="stripe",
            provider_customer_id=c.id,
            email=c.get("email"),
            name=c.get("name"),
        )

    async def create_intent(self, data: IntentCreateIn, *, user_id: str | None) -> IntentOut:
        kwargs: dict[str, Any] = dict(
            amount=int(data.amount),
            currency=data.currency.lower(),
            description=data.description or None,
            capture_method="manual" if data.capture_method == "manual" else "automatic",
            automatic_payment_methods={"enabled": True} if not data.payment_method_types else None,
        )
        if data.payment_method_types:
            kwargs["payment_method_types"] = data.payment_method_types
        pi = await _acall(
            stripe.PaymentIntent.create,
            **{k: v for k, v in kwargs.items() if v is not None},
        )
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
        pi = await _acall(stripe.PaymentIntent.confirm, provider_intent_id)
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
        pi = await _acall(stripe.PaymentIntent.cancel, provider_intent_id)
        return IntentOut(
            id=pi.id,
            provider="stripe",
            provider_intent_id=pi.id,
            status=pi.status,
            amount=int(pi.amount),
            currency=pi.currency.upper(),
        )

    async def refund(self, provider_intent_id: str, data: RefundIn) -> IntentOut:
        # Stripe refunds are created against charges; simplify via PaymentIntent last charge
        pi = await _acall(
            stripe.PaymentIntent.retrieve, provider_intent_id, expand=["latest_charge"]
        )
        charge_id = pi.latest_charge.id if getattr(pi, "latest_charge", None) else None
        if not charge_id:
            raise ValueError("No charge available to refund")
        await _acall(
            stripe.Refund.create,
            charge=charge_id,
            amount=int(data.amount) if data.amount else None,
        )
        # Re-hydrate
        return await self.hydrate_intent(provider_intent_id)

    async def verify_and_parse_webhook(
        self, signature: str | None, payload: bytes
    ) -> dict[str, Any]:
        if not self._wh_secret:
            raise ValueError("Stripe webhook secret not configured")
        event = await _acall(
            stripe.Webhook.construct_event,
            payload=payload,
            sig_header=signature,
            secret=self._wh_secret,
        )
        return {"id": event.id, "type": event.type, "data": event.data.object}

    async def hydrate_intent(self, provider_intent_id: str) -> IntentOut:
        pi = await _acall(stripe.PaymentIntent.retrieve, provider_intent_id)
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

    async def capture_intent(self, provider_intent_id: str, *, amount: int | None) -> IntentOut:
        # Stripe: capture on PaymentIntent
        kwargs = {}
        if amount is not None:
            kwargs["amount_to_capture"] = int(amount)
        pi = await _acall(stripe.PaymentIntent.capture, provider_intent_id, **kwargs)
        return _pi_to_out(pi)

    async def list_intents(
        self,
        *,
        customer_provider_id: str | None,
        status: str | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[IntentOut], str | None]:
        params = {"limit": int(limit)}
        if customer_provider_id:
            params["customer"] = customer_provider_id
        if status:
            params["status"] = status
        if cursor:
            params["starting_after"] = cursor
        res = await _acall(stripe.PaymentIntent.list, **params)
        items = [_pi_to_out(pi) for pi in res.data]
        next_cursor = res.data[-1].id if getattr(res, "has_more", False) and res.data else None
        return items, next_cursor

    # ---- Invoice helpers ----
    async def add_invoice_line_item(self, data: InvoiceLineItemIn) -> dict[str, Any]:
        kwargs = dict(
            customer=data.customer_provider_id,
            quantity=data.quantity or 1,
            currency=data.currency.lower(),
            description=data.description or None,
        )
        if data.provider_price_id:
            kwargs["price"] = data.provider_price_id
        else:
            kwargs["unit_amount"] = int(data.unit_amount)
        item = await _acall(
            stripe.InvoiceItem.create, **{k: v for k, v in kwargs.items() if v is not None}
        )
        return {"id": item.id}

    async def list_invoices(
        self,
        *,
        customer_provider_id: str | None,
        status: str | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[InvoiceOut], str | None]:
        params = {"limit": int(limit)}
        if customer_provider_id:
            params["customer"] = customer_provider_id
        if status:
            params["status"] = status
        if cursor:
            params["starting_after"] = cursor
        res = await _acall(stripe.Invoice.list, **params)
        items = [_inv_to_out(inv) for inv in res.data]
        next_cursor = res.data[-1].id if getattr(res, "has_more", False) and res.data else None
        return items, next_cursor

    async def get_invoice(self, provider_invoice_id: str) -> InvoiceOut:
        inv = await _acall(stripe.Invoice.retrieve, provider_invoice_id)
        return _inv_to_out(inv)

    async def preview_invoice(
        self, *, customer_provider_id: str, subscription_id: str | None = None
    ) -> InvoiceOut:
        params = {"customer": customer_provider_id}
        if subscription_id:
            params["subscription"] = subscription_id
        inv = await _acall(stripe.Invoice.upcoming, **params)
        return _inv_to_out(inv)

    # ---- Metered usage ----
    async def create_usage_record(self, data: UsageRecordIn) -> dict[str, Any]:
        if not data.subscription_item and not data.provider_price_id:
            raise ValueError("subscription_item or provider_price_id is required")
        # If a price is given, you’d normally look up the active subscription_item for that price.
        sub_item = data.subscription_item
        if not sub_item and data.provider_price_id:
            # best-effort: find an active subscription item for the price
            items = await _acall(
                stripe.SubscriptionItem.list, price=data.provider_price_id, limit=1
            )
            sub_item = items.data[0].id if items.data else None
        if not sub_item:
            raise ValueError("No subscription item found for usage record")

        body = {
            "subscription_item": sub_item,
            "quantity": int(data.quantity),
            "action": data.action or "increment",
        }
        if data.timestamp:
            body["timestamp"] = int(data.timestamp)
        rec = await _acall(stripe.UsageRecord.create, **body)
        return {"id": rec.id, "quantity": rec.quantity, "timestamp": rec.timestamp}
