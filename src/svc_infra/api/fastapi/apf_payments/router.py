from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, Request
from starlette.responses import JSONResponse

from svc_infra.apf_payments.schemas import (
    CustomerOut,
    CustomerUpsertIn,
    IntentCreateIn,
    IntentOut,
    InvoiceCreateIn,
    InvoiceOut,
    PaymentMethodAttachIn,
    PaymentMethodOut,
    PriceCreateIn,
    PriceOut,
    ProductCreateIn,
    ProductOut,
    RefundIn,
    StatementRow,
    SubscriptionCreateIn,
    SubscriptionOut,
    SubscriptionUpdateIn,
    TransactionRow,
)
from svc_infra.apf_payments.service import PaymentsService
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep
from svc_infra.api.fastapi.dual import protected_router, public_router, service_router, user_router
from svc_infra.api.fastapi.dual.router import DualAPIRouter


# --- deps ---
async def get_service(session: SqlSessionDep) -> PaymentsService:
    # No provider forced here; PaymentsService lazy-loads when needed
    return PaymentsService(session=session)


# --- routers grouped by auth posture (same prefix is fine; FastAPI merges) ---
def build_payments_routers(prefix: str = "/payments") -> list[DualAPIRouter]:
    routers: list[DualAPIRouter] = []

    # USER endpoints (require logged-in user)
    user = user_router(prefix=prefix, tags=["payments"])

    # SERVICE endpoints (api key only)
    svc = service_router(prefix=prefix, tags=["payments"])

    # PROTECTED endpoints (user OR api key)
    prot = protected_router(prefix=prefix, tags=["payments"])

    @user.post("/customers", response_model=CustomerOut, name="payments_upsert_customer")
    async def upsert_customer(data: CustomerUpsertIn, svc: PaymentsService = Depends(get_service)):
        out = await svc.ensure_customer(data)
        await svc.session.flush()
        return out

    @user.post("/intents", response_model=IntentOut, name="payments_create_intent")
    async def create_intent(data: IntentCreateIn, svc: PaymentsService = Depends(get_service)):
        # If your RequireUser principal exposes user id somewhere (e.g., request.state.principal.user.id),
        # you can plumb it here. For now, let provider/customer flows attach user_id later.
        out = await svc.create_intent(user_id=None, data=data)
        await svc.session.flush()
        return out

    routers.append(user)

    @prot.post(
        "/intents/{provider_intent_id}/confirm",
        response_model=IntentOut,
        name="payments_confirm_intent",
    )
    async def confirm_intent(provider_intent_id: str, svc: PaymentsService = Depends(get_service)):
        out = await svc.confirm_intent(provider_intent_id)
        await svc.session.flush()
        return out

    @prot.post(
        "/intents/{provider_intent_id}/cancel",
        response_model=IntentOut,
        name="payments_cancel_intent",
    )
    async def cancel_intent(provider_intent_id: str, svc: PaymentsService = Depends(get_service)):
        out = await svc.cancel_intent(provider_intent_id)
        await svc.session.flush()
        return out

    @prot.post(
        "/intents/{provider_intent_id}/refund",
        response_model=IntentOut,
        name="payments_refund_intent",
    )
    async def refund_intent(
        provider_intent_id: str, data: RefundIn, svc: PaymentsService = Depends(get_service)
    ):
        out = await svc.refund(provider_intent_id, data)
        await svc.session.flush()
        return out

    @prot.get(
        "/transactions", response_model=list[TransactionRow], name="payments_list_transactions"
    )
    async def list_transactions(svc: PaymentsService = Depends(get_service)):
        from sqlalchemy import select

        from svc_infra.apf_payments.models import LedgerEntry

        rows = (await svc.session.execute(select(LedgerEntry))).scalars().all()
        return [
            TransactionRow(
                id=e.id,
                ts=e.ts.isoformat(),
                type="payment",
                amount=e.amount,
                currency=e.currency,
                status=e.status,
                provider=e.provider,
                provider_ref=e.provider_ref or "",
                user_id=e.user_id,
            )
            for e in rows
        ]

    routers.append(prot)

    # PUBLIC webhooks
    pub = public_router(prefix=prefix, tags=["payments"])

    @pub.post("/webhooks/{provider}", name="payments_webhook")
    async def webhooks(
        provider: str,
        request: Request,
        svc: PaymentsService = Depends(get_service),
        signature: Optional[str] = Header(None, alias="Stripe-Signature"),
    ):
        payload = await request.body()
        out = await svc.handle_webhook(provider.lower(), signature, payload)
        await svc.session.flush()
        return JSONResponse(out)

    @user.post("/methods/attach", response_model=PaymentMethodOut, name="payments_attach_method")
    async def attach_method(
        data: PaymentMethodAttachIn, svc: PaymentsService = Depends(get_service)
    ):
        out = await svc.attach_payment_method(data)
        await svc.session.flush()
        return out

    @prot.get("/methods", response_model=list[PaymentMethodOut], name="payments_list_methods")
    async def list_methods(customer_provider_id: str, svc: PaymentsService = Depends(get_service)):
        return await svc.list_payment_methods(customer_provider_id)

    @prot.post("/methods/{provider_method_id}/detach", name="payments_detach_method")
    async def detach_method(provider_method_id: str, svc: PaymentsService = Depends(get_service)):
        await svc.detach_payment_method(provider_method_id)
        await svc.session.flush()
        return {"ok": True}

    @prot.post("/methods/{provider_method_id}/default", name="payments_set_default_method")
    async def set_default_method(
        provider_method_id: str,
        customer_provider_id: str,
        svc: PaymentsService = Depends(get_service),
    ):
        await svc.set_default_payment_method(customer_provider_id, provider_method_id)
        await svc.session.flush()
        return {"ok": True}

    # PRODUCTS/PRICES
    @svc.post("/products", response_model=ProductOut, name="payments_create_product")
    async def create_product(data: ProductCreateIn, svc: PaymentsService = Depends(get_service)):
        out = await svc.create_product(data)
        await svc.session.flush()
        return out

    @svc.post("/prices", response_model=PriceOut, name="payments_create_price")
    async def create_price(data: PriceCreateIn, svc: PaymentsService = Depends(get_service)):
        out = await svc.create_price(data)
        await svc.session.flush()
        return out

    # SUBSCRIPTIONS
    @prot.post(
        "/subscriptions", response_model=SubscriptionOut, name="payments_create_subscription"
    )
    async def create_subscription(
        data: SubscriptionCreateIn, svc: PaymentsService = Depends(get_service)
    ):
        out = await svc.create_subscription(data)
        await svc.session.flush()
        return out

    @prot.post(
        "/subscriptions/{provider_subscription_id}",
        response_model=SubscriptionOut,
        name="payments_update_subscription",
    )
    async def update_subscription(
        provider_subscription_id: str,
        data: SubscriptionUpdateIn,
        svc: PaymentsService = Depends(get_service),
    ):
        out = await svc.update_subscription(provider_subscription_id, data)
        await svc.session.flush()
        return out

    @prot.post(
        "/subscriptions/{provider_subscription_id}/cancel",
        response_model=SubscriptionOut,
        name="payments_cancel_subscription",
    )
    async def cancel_subscription(
        provider_subscription_id: str,
        at_period_end: bool = True,
        svc: PaymentsService = Depends(get_service),
    ):
        out = await svc.cancel_subscription(provider_subscription_id, at_period_end)
        await svc.session.flush()
        return out

    # INVOICES
    @prot.post("/invoices", response_model=InvoiceOut, name="payments_create_invoice")
    async def create_invoice(data: InvoiceCreateIn, svc: PaymentsService = Depends(get_service)):
        out = await svc.create_invoice(data)
        await svc.session.flush()
        return out

    @prot.post(
        "/invoices/{provider_invoice_id}/finalize",
        response_model=InvoiceOut,
        name="payments_finalize_invoice",
    )
    async def finalize_invoice(
        provider_invoice_id: str, svc: PaymentsService = Depends(get_service)
    ):
        out = await svc.finalize_invoice(provider_invoice_id)
        await svc.session.flush()
        return out

    @prot.post(
        "/invoices/{provider_invoice_id}/void",
        response_model=InvoiceOut,
        name="payments_void_invoice",
    )
    async def void_invoice(provider_invoice_id: str, svc: PaymentsService = Depends(get_service)):
        out = await svc.void_invoice(provider_invoice_id)
        await svc.session.flush()
        return out

    @prot.post(
        "/invoices/{provider_invoice_id}/pay",
        response_model=InvoiceOut,
        name="payments_pay_invoice",
    )
    async def pay_invoice(provider_invoice_id: str, svc: PaymentsService = Depends(get_service)):
        out = await svc.pay_invoice(provider_invoice_id)
        await svc.session.flush()
        return out

    # INTENTS: get/hydrate
    @prot.get("/intents/{provider_intent_id}", response_model=IntentOut, name="payments_get_intent")
    async def get_intent(provider_intent_id: str, svc: PaymentsService = Depends(get_service)):
        return await svc.get_intent(provider_intent_id)

    # STATEMENTS (rollup)
    @svc.get(
        "/statements/daily", response_model=list[StatementRow], name="payments_daily_statements"
    )
    async def daily_statements(
        date_from: str | None = None,
        date_to: str | None = None,
        svc: PaymentsService = Depends(get_service),
    ):
        return await svc.daily_statements_rollup(date_from, date_to)

    routers.append(svc)
    routers.append(pub)
    return routers
