from __future__ import annotations

from functools import partial
from typing import Any, Optional

import anyio

from ..schemas import (
    BalanceSnapshotOut,
    CustomerOut,
    CustomerUpsertIn,
    DisputeOut,
    IntentCreateIn,
    IntentOut,
    InvoiceCreateIn,
    InvoiceLineItemIn,
    InvoiceLineItemOut,
    InvoiceOut,
    NextAction,
    PaymentMethodAttachIn,
    PaymentMethodOut,
    PaymentMethodUpdateIn,
    PayoutOut,
    PriceCreateIn,
    PriceOut,
    PriceUpdateIn,
    ProductCreateIn,
    ProductOut,
    ProductUpdateIn,
    RefundIn,
    RefundOut,
    SetupIntentCreateIn,
    SetupIntentOut,
    SubscriptionCreateIn,
    SubscriptionOut,
    SubscriptionUpdateIn,
    UsageRecordIn,
    UsageRecordListFilter,
    UsageRecordOut,
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


def _pm_to_out(pm, *, is_default: bool = False) -> PaymentMethodOut:
    card = getattr(pm, "card", None) or {}
    return PaymentMethodOut(
        id=pm.id,
        provider="stripe",
        provider_customer_id=getattr(pm, "customer", None) or "",
        provider_method_id=pm.id,
        brand=card.get("brand"),
        last4=card.get("last4"),
        exp_month=card.get("exp_month"),
        exp_year=card.get("exp_year"),
        is_default=bool(is_default),
    )


def _product_to_out(p) -> ProductOut:
    return ProductOut(
        id=p.id,
        provider="stripe",
        provider_product_id=p.id,
        name=p.name,
        active=bool(p.active),
    )


def _price_to_out(pr) -> PriceOut:
    rec = getattr(pr, "recurring", None) or {}
    return PriceOut(
        id=pr.id,
        provider="stripe",
        provider_price_id=pr.id,
        provider_product_id=(
            pr.product if isinstance(pr.product, str) else getattr(pr.product, "id", "")
        ),
        currency=str(pr.currency).upper(),
        unit_amount=int(pr.unit_amount),
        interval=rec.get("interval"),
        trial_days=getattr(pr, "trial_period_days", None),
        active=bool(pr.active),
    )


def _sub_to_out(s) -> SubscriptionOut:
    # pick first item’s price/quantity for simple one-item subs
    item = s.items.data[0] if getattr(s.items, "data", []) else None
    price_id = item.price.id if item and getattr(item, "price", None) else ""
    qty = item.quantity if item else 0
    return SubscriptionOut(
        id=s.id,
        provider="stripe",
        provider_subscription_id=s.id,
        provider_price_id=price_id,
        status=s.status,
        quantity=int(qty or 0),
        cancel_at_period_end=bool(s.cancel_at_period_end),
        current_period_end=(
            str(s.current_period_end) if getattr(s, "current_period_end", None) else None
        ),
    )


def _refund_to_out(r) -> RefundOut:
    return RefundOut(
        id=r.id,
        provider="stripe",
        provider_refund_id=r.id,
        provider_payment_intent_id=getattr(r, "payment_intent", None),
        amount=int(r.amount),
        currency=str(r.currency).upper(),
        status=r.status,
        reason=getattr(r, "reason", None),
        created_at=str(r.created) if getattr(r, "created", None) else None,
    )


def _dispute_to_out(d) -> DisputeOut:
    return DisputeOut(
        id=d.id,
        provider="stripe",
        provider_dispute_id=d.id,
        amount=int(d.amount),
        currency=str(d.currency).upper(),
        reason=getattr(d, "reason", None),
        status=d.status,
        evidence_due_by=(
            str(d.evidence_details.get("due_by")) if getattr(d, "evidence_details", None) else None
        ),
        created_at=str(d.created) if getattr(d, "created", None) else None,
    )


def _payout_to_out(p) -> PayoutOut:
    return PayoutOut(
        id=p.id,
        provider="stripe",
        provider_payout_id=p.id,
        amount=int(p.amount),
        currency=str(p.currency).upper(),
        status=p.status,
        arrival_date=str(p.arrival_date) if getattr(p, "arrival_date", None) else None,
        type=getattr(p, "type", None),
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

    # -------- Customers --------
    async def ensure_customer(self, data: CustomerUpsertIn) -> CustomerOut:
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

    async def list_customers(
        self, *, provider: str | None, user_id: str | None, limit: int, cursor: str | None
    ) -> tuple[list[CustomerOut], str | None]:
        params = {"limit": int(limit)}
        if cursor:
            params["starting_after"] = cursor
        # Stripe has no direct filter for our custom user_id; many teams store mapping in DB.
        # If 'user_id' was stored in metadata, we could search via /v1/customers?limit=... then filter client-side.
        res = await _acall(stripe.Customer.list, **params)
        items = [
            CustomerOut(
                id=c.id,
                provider="stripe",
                provider_customer_id=c.id,
                email=c.get("email"),
                name=c.get("name"),
            )
            for c in res.data
        ]
        next_cursor = res.data[-1].id if getattr(res, "has_more", False) and res.data else None
        return items, next_cursor

    # -------- Payment Methods --------
    async def attach_payment_method(self, data: PaymentMethodAttachIn) -> PaymentMethodOut:
        pm = await _acall(
            stripe.PaymentMethod.attach,
            data.payment_method_token,
            customer=data.customer_provider_id,
        )
        is_default = False
        if data.make_default:
            cust = await _acall(
                stripe.Customer.modify,
                data.customer_provider_id,
                invoice_settings={"default_payment_method": pm.id},
            )
            is_default = (
                getattr(getattr(cust, "invoice_settings", None), "default_payment_method", None)
                == pm.id
            )
        else:
            cust = await _acall(stripe.Customer.retrieve, data.customer_provider_id)
            is_default = (
                getattr(getattr(cust, "invoice_settings", None), "default_payment_method", None)
                == pm.id
            )
        return _pm_to_out(pm, is_default=is_default)

    async def list_payment_methods(self, provider_customer_id: str) -> list[PaymentMethodOut]:
        cust = await _acall(stripe.Customer.retrieve, provider_customer_id)
        default_pm = getattr(
            getattr(cust, "invoice_settings", None), "default_payment_method", None
        )
        res = await _acall(stripe.PaymentMethod.list, customer=provider_customer_id, type="card")
        return [_pm_to_out(pm, is_default=(pm.id == default_pm)) for pm in res.data]

    async def detach_payment_method(self, provider_method_id: str) -> PaymentMethodOut:
        pm = await _acall(stripe.PaymentMethod.detach, provider_method_id)
        # we no longer know default status reliably—fetch customer if set
        cust_id = getattr(pm, "customer", None)
        default_pm = None
        if cust_id:
            cust = await _acall(stripe.Customer.retrieve, cust_id)
            default_pm = getattr(
                getattr(cust, "invoice_settings", None), "default_payment_method", None
            )
        return _pm_to_out(pm, is_default=(pm.id == default_pm))

    async def set_default_payment_method(
        self, provider_customer_id: str, provider_method_id: str
    ) -> PaymentMethodOut:
        cust = await _acall(
            stripe.Customer.modify,
            provider_customer_id,
            invoice_settings={"default_payment_method": provider_method_id},
        )
        pm = await _acall(stripe.PaymentMethod.retrieve, provider_method_id)
        is_default = (
            getattr(getattr(cust, "invoice_settings", None), "default_payment_method", None)
            == pm.id
        )
        return _pm_to_out(pm, is_default=is_default)

    async def get_payment_method(self, provider_method_id: str) -> PaymentMethodOut:
        pm = await _acall(stripe.PaymentMethod.retrieve, provider_method_id)
        cust_id = getattr(pm, "customer", None)
        default_pm = None
        if cust_id:
            cust = await _acall(stripe.Customer.retrieve, cust_id)
            default_pm = getattr(
                getattr(cust, "invoice_settings", None), "default_payment_method", None
            )
        return _pm_to_out(pm, is_default=(pm.id == default_pm))

    async def update_payment_method(
        self, provider_method_id: str, data: PaymentMethodUpdateIn
    ) -> PaymentMethodOut:
        update: dict[str, Any] = {}
        if data.name is not None:
            update["billing_details"] = {"name": data.name}
        if data.exp_month is not None or data.exp_year is not None:
            update["card"] = {}
            if data.exp_month is not None:
                update["card"]["exp_month"] = data.exp_month
            if data.exp_year is not None:
                update["card"]["exp_year"] = data.exp_year
        pm = (
            await _acall(stripe.PaymentMethod.modify, provider_method_id, **update)
            if update
            else await _acall(stripe.PaymentMethod.retrieve, provider_method_id)
        )
        cust_id = getattr(pm, "customer", None)
        default_pm = None
        if cust_id:
            cust = await _acall(stripe.Customer.retrieve, cust_id)
            default_pm = getattr(
                getattr(cust, "invoice_settings", None), "default_payment_method", None
            )
        return _pm_to_out(pm, is_default=(pm.id == default_pm))

    # -------- Products / Prices --------
    async def create_product(self, data: ProductCreateIn) -> ProductOut:
        p = await _acall(stripe.Product.create, name=data.name, active=bool(data.active))
        return _product_to_out(p)

    async def get_product(self, provider_product_id: str) -> ProductOut:
        p = await _acall(stripe.Product.retrieve, provider_product_id)
        return _product_to_out(p)

    async def list_products(
        self, *, active: bool | None, limit: int, cursor: str | None
    ) -> tuple[list[ProductOut], str | None]:
        params = {"limit": int(limit)}
        if active is not None:
            params["active"] = bool(active)
        if cursor:
            params["starting_after"] = cursor
        res = await _acall(stripe.Product.list, **params)
        items = [_product_to_out(p) for p in res.data]
        next_cursor = res.data[-1].id if getattr(res, "has_more", False) and res.data else None
        return items, next_cursor

    async def update_product(self, provider_product_id: str, data: ProductUpdateIn) -> ProductOut:
        update: dict[str, Any] = {}
        if data.name is not None:
            update["name"] = data.name
        if data.active is not None:
            update["active"] = bool(data.active)
        p = (
            await _acall(stripe.Product.modify, provider_product_id, **update)
            if update
            else await _acall(stripe.Product.retrieve, provider_product_id)
        )
        return _product_to_out(p)

    async def create_price(self, data: PriceCreateIn) -> PriceOut:
        kwargs: dict[str, Any] = dict(
            product=data.provider_product_id,
            currency=data.currency.lower(),
            unit_amount=int(data.unit_amount),
            active=bool(data.active),
        )
        if data.interval:
            kwargs["recurring"] = {"interval": data.interval}
        if data.trial_days is not None:
            kwargs["trial_period_days"] = int(data.trial_days)
        pr = await _acall(stripe.Price.create, **kwargs)
        return _price_to_out(pr)

    async def get_price(self, provider_price_id: str) -> PriceOut:
        pr = await _acall(stripe.Price.retrieve, provider_price_id)
        return _price_to_out(pr)

    async def list_prices(
        self,
        *,
        provider_product_id: str | None,
        active: bool | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[PriceOut], str | None]:
        params = {"limit": int(limit)}
        if provider_product_id:
            params["product"] = provider_product_id
        if active is not None:
            params["active"] = bool(active)
        if cursor:
            params["starting_after"] = cursor
        res = await _acall(stripe.Price.list, **params)
        items = [_price_to_out(p) for p in res.data]
        next_cursor = res.data[-1].id if getattr(res, "has_more", False) and res.data else None
        return items, next_cursor

    async def update_price(self, provider_price_id: str, data: PriceUpdateIn) -> PriceOut:
        # Stripe allows toggling `active` and updating metadata, but not amount/currency/product.
        update: dict[str, Any] = {}
        if data.active is not None:
            update["active"] = bool(data.active)
        pr = (
            await _acall(stripe.Price.modify, provider_price_id, **update)
            if update
            else await _acall(stripe.Price.retrieve, provider_price_id)
        )
        return _price_to_out(pr)

    # -------- Subscriptions --------
    async def create_subscription(self, data: SubscriptionCreateIn) -> SubscriptionOut:
        kwargs: dict[str, Any] = dict(
            customer=data.customer_provider_id,
            items=[{"price": data.price_provider_id, "quantity": int(data.quantity)}],
            proration_behavior=data.proration_behavior,
        )
        if data.trial_days is not None:
            kwargs["trial_period_days"] = int(data.trial_days)
        s = await _acall(stripe.Subscription.create, **kwargs)
        return _sub_to_out(s)

    async def update_subscription(
        self, provider_subscription_id: str, data: SubscriptionUpdateIn
    ) -> SubscriptionOut:
        s = await _acall(stripe.Subscription.retrieve, provider_subscription_id, expand=["items"])
        items = s.items.data
        update_kwargs: dict[str, Any] = {"proration_behavior": data.proration_behavior}
        # update first item (simple plan model)
        if items:
            first_item = items[0]
            item_update = {"id": first_item.id}
            if data.price_provider_id:
                item_update["price"] = data.price_provider_id
            if data.quantity is not None:
                item_update["quantity"] = int(data.quantity)
            update_kwargs["items"] = [item_update]
        if data.cancel_at_period_end is not None:
            update_kwargs["cancel_at_period_end"] = bool(data.cancel_at_period_end)
        s2 = await _acall(stripe.Subscription.modify, provider_subscription_id, **update_kwargs)
        return _sub_to_out(s2)

    async def cancel_subscription(
        self, provider_subscription_id: str, at_period_end: bool = True
    ) -> SubscriptionOut:
        s = await _acall(
            stripe.Subscription.cancel if not at_period_end else stripe.Subscription.modify,
            provider_subscription_id,
            **({} if not at_period_end else {"cancel_at_period_end": True}),
        )
        return _sub_to_out(s)

    async def get_subscription(self, provider_subscription_id: str) -> SubscriptionOut:
        s = await _acall(stripe.Subscription.retrieve, provider_subscription_id, expand=["items"])
        return _sub_to_out(s)

    async def list_subscriptions(
        self,
        *,
        customer_provider_id: str | None,
        status: str | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[SubscriptionOut], str | None]:
        params = {"limit": int(limit)}
        if customer_provider_id:
            params["customer"] = customer_provider_id
        if status:
            params["status"] = status
        if cursor:
            params["starting_after"] = cursor
        res = await _acall(stripe.Subscription.list, **params)
        items = [_sub_to_out(s) for s in res.data]
        next_cursor = res.data[-1].id if getattr(res, "has_more", False) and res.data else None
        return items, next_cursor

    # -------- Invoices --------
    async def create_invoice(self, data: InvoiceCreateIn) -> InvoiceOut:
        inv = await _acall(
            stripe.Invoice.create,
            customer=data.customer_provider_id,
            auto_advance=bool(data.auto_advance),
        )
        return _inv_to_out(inv)

    async def finalize_invoice(self, provider_invoice_id: str) -> InvoiceOut:
        inv = await _acall(stripe.Invoice.finalize_invoice, provider_invoice_id)
        return _inv_to_out(inv)

    async def void_invoice(self, provider_invoice_id: str) -> InvoiceOut:
        inv = await _acall(stripe.Invoice.void_invoice, provider_invoice_id)
        return _inv_to_out(inv)

    async def pay_invoice(self, provider_invoice_id: str) -> InvoiceOut:
        inv = await _acall(stripe.Invoice.pay, provider_invoice_id)
        return _inv_to_out(inv)

    async def add_invoice_line_item(
        self, provider_invoice_id: str, data: InvoiceLineItemIn
    ) -> InvoiceOut:
        # attach an item to a DRAFT invoice
        kwargs: dict[str, Any] = dict(
            invoice=provider_invoice_id,
            customer=data.customer_provider_id,
            quantity=int(data.quantity or 1),
            currency=data.currency.lower(),
            description=data.description or None,
        )
        if data.provider_price_id:
            kwargs["price"] = data.provider_price_id
        else:
            kwargs["unit_amount"] = int(data.unit_amount)
        await _acall(
            stripe.InvoiceItem.create, **{k: v for k, v in kwargs.items() if v is not None}
        )
        inv = await _acall(stripe.Invoice.retrieve, provider_invoice_id)
        return _inv_to_out(inv)

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

    async def list_invoice_line_items(
        self, provider_invoice_id: str, *, limit: int, cursor: str | None
    ) -> tuple[list[InvoiceLineItemOut], str | None]:
        params = {"limit": int(limit)}
        if cursor:
            params["starting_after"] = cursor
        res = await _acall(stripe.Invoice.list_lines, provider_invoice_id, **params)
        items: list[InvoiceLineItemOut] = []
        for li in res.data:
            amount = int(getattr(li, "amount", 0))
            currency = str(getattr(li, "currency", "USD")).upper()
            price_id = getattr(getattr(li, "price", None), "id", None)
            items.append(
                InvoiceLineItemOut(
                    id=li.id,
                    description=getattr(li, "description", None),
                    amount=amount,
                    currency=currency,
                    quantity=getattr(li, "quantity", 1),
                    provider_price_id=price_id,
                )
            )
        next_cursor = res.data[-1].id if getattr(res, "has_more", False) and res.data else None
        return items, next_cursor

    # -------- Intents --------
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
            stripe.PaymentIntent.create, **{k: v for k, v in kwargs.items() if v is not None}
        )
        return _pi_to_out(pi)

    async def confirm_intent(self, provider_intent_id: str) -> IntentOut:
        pi = await _acall(stripe.PaymentIntent.confirm, provider_intent_id)
        return _pi_to_out(pi)

    async def cancel_intent(self, provider_intent_id: str) -> IntentOut:
        pi = await _acall(stripe.PaymentIntent.cancel, provider_intent_id)
        return _pi_to_out(pi)

    async def refund(self, provider_intent_id: str, data: RefundIn) -> IntentOut:
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
            reason=data.reason or None,
        )
        return await self.hydrate_intent(provider_intent_id)

    async def hydrate_intent(self, provider_intent_id: str) -> IntentOut:
        pi = await _acall(stripe.PaymentIntent.retrieve, provider_intent_id)
        return _pi_to_out(pi)

    async def capture_intent(self, provider_intent_id: str, *, amount: int | None) -> IntentOut:
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

    # ---- Setup Intents (off-session readiness) ----
    async def create_setup_intent(self, data: SetupIntentCreateIn) -> SetupIntentOut:
        si = await _acall(
            stripe.SetupIntent.create, payment_method_types=data.payment_method_types or ["card"]
        )
        return SetupIntentOut(
            id=si.id,
            provider="stripe",
            provider_setup_intent_id=si.id,
            status=si.status,
            client_secret=getattr(si, "client_secret", None),
            next_action=NextAction(type=getattr(getattr(si, "next_action", None), "type", None)),
        )

    async def confirm_setup_intent(self, provider_setup_intent_id: str) -> SetupIntentOut:
        si = await _acall(stripe.SetupIntent.confirm, provider_setup_intent_id)
        return SetupIntentOut(
            id=si.id,
            provider="stripe",
            provider_setup_intent_id=si.id,
            status=si.status,
            client_secret=getattr(si, "client_secret", None),
            next_action=NextAction(type=getattr(getattr(si, "next_action", None), "type", None)),
        )

    async def get_setup_intent(self, provider_setup_intent_id: str) -> SetupIntentOut:
        si = await _acall(stripe.SetupIntent.retrieve, provider_setup_intent_id)
        return SetupIntentOut(
            id=si.id,
            provider="stripe",
            provider_setup_intent_id=si.id,
            status=si.status,
            client_secret=getattr(si, "client_secret", None),
            next_action=NextAction(type=getattr(getattr(si, "next_action", None), "type", None)),
        )

    # ---- 3DS/SCA resume ----
    async def resume_intent_after_action(self, provider_intent_id: str) -> IntentOut:
        # For Stripe, retrieving after the customer completes next_action is sufficient
        return await self.hydrate_intent(provider_intent_id)

    # -------- Disputes --------
    async def list_disputes(
        self, *, status: str | None, limit: int, cursor: str | None
    ) -> tuple[list[DisputeOut], str | None]:
        params = {"limit": int(limit)}
        if status:
            params["status"] = status
        if cursor:
            params["starting_after"] = cursor
        res = await _acall(stripe.Dispute.list, **params)
        items = [_dispute_to_out(d) for d in res.data]
        next_cursor = res.data[-1].id if getattr(res, "has_more", False) and res.data else None
        return items, next_cursor

    async def get_dispute(self, provider_dispute_id: str) -> DisputeOut:
        d = await _acall(stripe.Dispute.retrieve, provider_dispute_id)
        return _dispute_to_out(d)

    async def submit_dispute_evidence(self, provider_dispute_id: str, evidence: dict) -> DisputeOut:
        d = await _acall(stripe.Dispute.modify, provider_dispute_id, evidence=evidence)
        # Some disputes require explicit submit call:
        try:
            d = await _acall(stripe.Dispute.submit, provider_dispute_id)
        except Exception:
            pass
        return _dispute_to_out(d)

    # -------- Balance & Payouts --------
    async def get_balance_snapshot(self) -> BalanceSnapshotOut:
        bal = await _acall(stripe.Balance.retrieve)

        def _bucket(entries):
            out = []
            for b in entries or []:
                out.append({"currency": str(b.currency).upper(), "amount": int(b.amount)})
            return out

        return BalanceSnapshotOut(
            available=_bucket(getattr(bal, "available", [])),
            pending=_bucket(getattr(bal, "pending", [])),
        )

    async def list_payouts(
        self, *, limit: int, cursor: str | None
    ) -> tuple[list[PayoutOut], str | None]:
        params = {"limit": int(limit)}
        if cursor:
            params["starting_after"] = cursor
        res = await _acall(stripe.Payout.list, **params)
        items = [_payout_to_out(p) for p in res.data]
        next_cursor = res.data[-1].id if getattr(res, "has_more", False) and res.data else None
        return items, next_cursor

    async def get_payout(self, provider_payout_id: str) -> PayoutOut:
        p = await _acall(stripe.Payout.retrieve, provider_payout_id)
        return _payout_to_out(p)

    # -------- Refunds (list/get) --------
    async def list_refunds(
        self, *, provider_payment_intent_id: str | None, limit: int, cursor: str | None
    ) -> tuple[list[RefundOut], str | None]:
        params = {"limit": int(limit)}
        if provider_payment_intent_id:
            params["payment_intent"] = provider_payment_intent_id
        if cursor:
            params["starting_after"] = cursor
        res = await _acall(stripe.Refund.list, **params)
        items = [_refund_to_out(r) for r in res.data]
        next_cursor = res.data[-1].id if getattr(res, "has_more", False) and res.data else None
        return items, next_cursor

    async def get_refund(self, provider_refund_id: str) -> RefundOut:
        r = await _acall(stripe.Refund.retrieve, provider_refund_id)
        return _refund_to_out(r)

    # -------- Usage (create/list/get) --------
    async def create_usage_record(self, data: UsageRecordIn) -> UsageRecordOut:
        if not data.subscription_item and not data.provider_price_id:
            raise ValueError("subscription_item or provider_price_id is required")
        sub_item = data.subscription_item
        if not sub_item and data.provider_price_id:
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
        return UsageRecordOut(
            id=rec.id,
            quantity=int(rec.quantity),
            timestamp=getattr(rec, "timestamp", None),
            subscription_item=sub_item,
            provider_price_id=data.provider_price_id,
        )

    async def list_usage_records(
        self, f: UsageRecordListFilter
    ) -> tuple[list[UsageRecordOut], str | None]:
        # Stripe exposes *summaries* per period. We surface them as list results.
        sub_item = f.subscription_item
        if not sub_item and f.provider_price_id:
            items = await _acall(stripe.SubscriptionItem.list, price=f.provider_price_id, limit=1)
            sub_item = items.data[0].id if items.data else None
        if not sub_item:
            return [], None
        params = {"limit": int(f.limit or 50)}
        if f.cursor:
            params["starting_after"] = f.cursor
        res = await _acall(stripe.SubscriptionItem.list_usage_record_summaries, sub_item, **params)
        items: list[UsageRecordOut] = []
        for s in res.data:
            # No record id in summaries—synthesize a stable id from period start.
            synthesized_id = f"{sub_item}:{getattr(s, 'period', {}).get('start')}"
            items.append(
                UsageRecordOut(
                    id=synthesized_id,
                    quantity=int(getattr(s, "total_usage", 0)),
                    timestamp=getattr(s, "period", {}).get("end"),
                    subscription_item=sub_item,
                    provider_price_id=f.provider_price_id,
                )
            )
        next_cursor = (
            res.data[-1].id
            if getattr(res, "has_more", False) and res.data and hasattr(res.data[-1], "id")
            else None
        )
        return items, next_cursor

    async def get_usage_record(self, usage_record_id: str) -> UsageRecordOut:
        # Stripe has no direct "retrieve usage record by id" API.
        # You can reconstruct via list summaries or store records locally when creating.
        raise NotImplementedError("Stripe does not support retrieving a single usage record by id")

    # -------- Webhooks --------
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
