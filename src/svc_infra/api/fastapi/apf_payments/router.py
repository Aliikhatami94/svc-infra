from __future__ import annotations

from typing import Literal, Optional, cast

from fastapi import Body, Depends, Header, Request, Response, status
from starlette.responses import JSONResponse

from svc_infra.apf_payments.schemas import (
    BalanceSnapshotOut,
    CaptureIn,
    CustomerOut,
    CustomerUpsertIn,
    DisputeOut,
    IntentCreateIn,
    IntentListFilter,
    IntentOut,
    InvoiceCreateIn,
    InvoiceLineItemIn,
    InvoiceOut,
    InvoicesListFilter,
    PaymentMethodAttachIn,
    PaymentMethodOut,
    PayoutOut,
    PriceCreateIn,
    PriceOut,
    ProductCreateIn,
    ProductOut,
    RefundIn,
    SetupIntentCreateIn,
    SetupIntentOut,
    StatementRow,
    SubscriptionCreateIn,
    SubscriptionOut,
    SubscriptionUpdateIn,
    TransactionRow,
    UsageRecordIn,
    WebhookReplayOut,
)
from svc_infra.apf_payments.service import PaymentsService
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep
from svc_infra.api.fastapi.dual import protected_router, public_router, service_router, user_router
from svc_infra.api.fastapi.dual.router import DualAPIRouter
from svc_infra.api.fastapi.middleware.idempotency import require_idempotency_key
from svc_infra.api.fastapi.pagination import (
    Paginated,
    cursor_pager,
    cursor_window,
    sort_by,
    use_pagination,
)

_TX_KINDS = {"payment", "refund", "fee", "payout", "capture"}


def _tx_kind(kind: str) -> Literal["payment", "refund", "fee", "payout", "capture"]:
    if kind not in _TX_KINDS:
        raise ValueError(f"Unknown ledger kind: {kind!r}")
    return cast(Literal["payment", "refund", "fee", "payout", "capture"], kind)


# --- deps ---
async def get_service(session: SqlSessionDep) -> PaymentsService:
    return PaymentsService(session=session)


# --- routers grouped by auth posture (same prefix is fine; FastAPI merges) ---
def build_payments_routers(prefix: str = "/payments") -> list[DualAPIRouter]:
    routers: list[DualAPIRouter] = []

    user = user_router(prefix=prefix, tags=["payments"])
    svc = service_router(prefix=prefix, tags=["payments"])
    prot = protected_router(prefix=prefix, tags=["payments"])

    @user.post(
        "/customers",
        response_model=CustomerOut,
        name="payments_upsert_customer",
        dependencies=[Depends(require_idempotency_key)],
    )
    async def upsert_customer(data: CustomerUpsertIn, svc: PaymentsService = Depends(get_service)):
        out = await svc.ensure_customer(data)
        await svc.session.flush()
        return out

    @user.post(
        "/intents",
        response_model=IntentOut,
        name="payments_create_intent",
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_idempotency_key)],
    )
    async def create_intent(
        data: IntentCreateIn,
        request: Request,
        response: Response,
        svc: PaymentsService = Depends(get_service),
    ):
        out = await svc.create_intent(user_id=None, data=data)
        await svc.session.flush()
        response.headers["Location"] = str(
            request.url_for("payments_get_intent", provider_intent_id=out.provider_intent_id)
        )
        return out

    routers.append(user)

    @prot.post(
        "/intents/{provider_intent_id}/confirm",
        response_model=IntentOut,
        name="payments_confirm_intent",
        dependencies=[Depends(require_idempotency_key)],
    )
    async def confirm_intent(provider_intent_id: str, svc: PaymentsService = Depends(get_service)):
        out = await svc.confirm_intent(provider_intent_id)
        await svc.session.flush()
        return out

    @prot.post(
        "/intents/{provider_intent_id}/cancel",
        response_model=IntentOut,
        name="payments_cancel_intent",
        dependencies=[Depends(require_idempotency_key)],
    )
    async def cancel_intent(provider_intent_id: str, svc: PaymentsService = Depends(get_service)):
        out = await svc.cancel_intent(provider_intent_id)
        await svc.session.flush()
        return out

    @prot.post(
        "/intents/{provider_intent_id}/refund",
        response_model=IntentOut,
        name="payments_refund_intent",
        dependencies=[Depends(require_idempotency_key)],
    )
    async def refund_intent(
        provider_intent_id: str, data: RefundIn, svc: PaymentsService = Depends(get_service)
    ):
        out = await svc.refund(provider_intent_id, data)
        await svc.session.flush()
        return out

    @prot.get(
        "/transactions",
        response_model=Paginated[TransactionRow],
        name="payments_list_transactions",
        dependencies=[Depends(cursor_pager(default_limit=50, max_limit=200))],
    )
    async def list_transactions(svc: PaymentsService = Depends(get_service)):
        from sqlalchemy import select

        from svc_infra.apf_payments.models import LedgerEntry

        rows = (await svc.session.execute(select(LedgerEntry))).scalars().all()
        rows_sorted = sort_by(rows, key=lambda e: e.ts, desc=True)

        ctx = use_pagination()
        window, next_cursor = cursor_window(
            rows_sorted,
            cursor=ctx.cursor,
            limit=ctx.limit,
            key=lambda e: int(e.ts.timestamp()),
            descending=True,
        )

        items = [
            TransactionRow(
                id=e.id,
                ts=e.ts.isoformat(),
                type=_tx_kind(e.kind),
                amount=int(e.amount),
                currency=e.currency,
                status=e.status,
                provider=e.provider,
                provider_ref=e.provider_ref or "",
                user_id=e.user_id,
            )
            for e in window
        ]
        return ctx.wrap(items, next_cursor=next_cursor)

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

    @user.post(
        "/methods/attach",
        response_model=PaymentMethodOut,
        name="payments_attach_method",
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_idempotency_key)],
    )
    async def attach_method(
        data: PaymentMethodAttachIn, svc: PaymentsService = Depends(get_service)
    ):
        out = await svc.attach_payment_method(data)
        await svc.session.flush()
        return out

    @prot.get(
        "/methods",
        response_model=Paginated[PaymentMethodOut],
        name="payments_list_methods",
        dependencies=[Depends(cursor_pager(default_limit=50, max_limit=200))],
    )
    async def list_methods(
        customer_provider_id: str,
        svc: PaymentsService = Depends(get_service),
    ):
        methods = await svc.list_payment_methods(customer_provider_id)
        methods_sorted = sort_by(
            sort_by(methods, key=lambda m: m.provider_method_id or "", desc=False),
            key=lambda m: m.is_default,
            desc=True,
        )
        ctx = use_pagination()
        window, next_cursor = cursor_window(
            methods_sorted,
            cursor=ctx.cursor,
            limit=ctx.limit,
            key=lambda m: m.provider_method_id or "",
            descending=False,
        )
        return ctx.wrap(window, next_cursor=next_cursor)

    @prot.post(
        "/methods/{provider_method_id}/detach",
        name="payments_detach_method",
        response_model=PaymentMethodOut,
        dependencies=[Depends(require_idempotency_key)],
    )
    async def detach_method(provider_method_id: str, svc: PaymentsService = Depends(get_service)):
        out = await svc.detach_payment_method(provider_method_id)
        await svc.session.flush()
        return out

    @prot.post(
        "/methods/{provider_method_id}/default",
        name="payments_set_default_method",
        response_model=PaymentMethodOut,  # ADD
        dependencies=[Depends(require_idempotency_key)],
    )
    async def set_default_method(
        provider_method_id: str,
        customer_provider_id: str,
        svc: PaymentsService = Depends(get_service),
    ):
        out = await svc.set_default_payment_method(customer_provider_id, provider_method_id)
        await svc.session.flush()
        return out

    # PRODUCTS/PRICES
    @svc.post(
        "/products",
        response_model=ProductOut,
        name="payments_create_product",
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_idempotency_key)],
    )
    async def create_product(data: ProductCreateIn, svc: PaymentsService = Depends(get_service)):
        out = await svc.create_product(data)
        await svc.session.flush()
        return out

    @svc.post(
        "/prices",
        response_model=PriceOut,
        name="payments_create_price",
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_idempotency_key)],
    )
    async def create_price(data: PriceCreateIn, svc: PaymentsService = Depends(get_service)):
        out = await svc.create_price(data)
        await svc.session.flush()
        return out

    # SUBSCRIPTIONS
    @prot.post(
        "/subscriptions",
        response_model=SubscriptionOut,
        name="payments_create_subscription",
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_idempotency_key)],
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
        dependencies=[Depends(require_idempotency_key)],
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
        dependencies=[Depends(require_idempotency_key)],
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
    @prot.post(
        "/invoices",
        response_model=InvoiceOut,
        name="payments_create_invoice",
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_idempotency_key)],
    )
    async def create_invoice(
        data: InvoiceCreateIn,
        request: Request,
        response: Response,
        svc: PaymentsService = Depends(get_service),
    ):
        out = await svc.create_invoice(data)
        await svc.session.flush()
        response.headers["Location"] = str(
            request.url_for("payments_get_invoice", provider_invoice_id=out.provider_invoice_id)
        )
        return out

    @prot.post(
        "/invoices/{provider_invoice_id}/finalize",
        response_model=InvoiceOut,
        name="payments_finalize_invoice",
        dependencies=[Depends(require_idempotency_key)],
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
        dependencies=[Depends(require_idempotency_key)],
    )
    async def void_invoice(provider_invoice_id: str, svc: PaymentsService = Depends(get_service)):
        out = await svc.void_invoice(provider_invoice_id)
        await svc.session.flush()
        return out

    @prot.post(
        "/invoices/{provider_invoice_id}/pay",
        response_model=InvoiceOut,
        name="payments_pay_invoice",
        dependencies=[Depends(require_idempotency_key)],
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

    # ===== Intents: capture & list =====
    @prot.post(
        "/intents/{provider_intent_id}/capture",
        response_model=IntentOut,
        name="payments_capture_intent",
        dependencies=[Depends(require_idempotency_key)],
    )
    async def capture_intent(
        provider_intent_id: str,
        data: CaptureIn,
        svc: PaymentsService = Depends(get_service),
    ):
        out = await svc.capture_intent(provider_intent_id, data)
        await svc.session.flush()
        return out

    @prot.get(
        "/intents",
        response_model=Paginated[IntentOut],
        name="payments_list_intents",
        dependencies=[Depends(cursor_pager(default_limit=50, max_limit=200))],
    )
    async def list_intents_endpoint(
        customer_provider_id: Optional[str] = None,
        status: Optional[str] = None,
        svc: PaymentsService = Depends(get_service),
    ):
        ctx = use_pagination()
        items, next_cursor = await svc.list_intents(
            IntentListFilter(
                customer_provider_id=customer_provider_id,
                status=status,
                limit=ctx.limit,
                cursor=ctx.cursor,
            )
        )
        return ctx.wrap(items, next_cursor=next_cursor)

    # ===== Invoices: lines/list/get/preview =====
    @prot.post(
        "/invoices/{provider_invoice_id}/lines",
        name="payments_add_invoice_line_item",
        status_code=status.HTTP_201_CREATED,
        response_model=InvoiceOut,
        dependencies=[Depends(require_idempotency_key)],
    )
    async def add_invoice_line(
        provider_invoice_id: str,
        data: InvoiceLineItemIn,
        svc: PaymentsService = Depends(get_service),
    ):
        out = await svc.add_invoice_line_item(provider_invoice_id, data)
        await svc.session.flush()
        return out

    @prot.get(
        "/invoices",
        response_model=Paginated[InvoiceOut],
        name="payments_list_invoices",
        dependencies=[Depends(cursor_pager(default_limit=50, max_limit=200))],
    )
    async def list_invoices_endpoint(
        customer_provider_id: Optional[str] = None,
        status: Optional[str] = None,
        svc: PaymentsService = Depends(get_service),
    ):
        ctx = use_pagination()
        items, next_cursor = await svc.list_invoices(
            InvoicesListFilter(
                customer_provider_id=customer_provider_id,
                status=status,
                limit=ctx.limit,
                cursor=ctx.cursor,
            )
        )
        return ctx.wrap(items, next_cursor=next_cursor)

    @prot.get(
        "/invoices/{provider_invoice_id}", response_model=InvoiceOut, name="payments_get_invoice"
    )
    async def get_invoice_endpoint(
        provider_invoice_id: str, svc: PaymentsService = Depends(get_service)
    ):
        return await svc.get_invoice(provider_invoice_id)

    @prot.post(
        "/invoices/preview",
        response_model=InvoiceOut,
        name="payments_preview_invoice",
        dependencies=[Depends(require_idempotency_key)],
    )
    async def preview_invoice_endpoint(
        customer_provider_id: str,
        subscription_id: Optional[str] = None,
        svc: PaymentsService = Depends(get_service),
    ):
        return await svc.preview_invoice(customer_provider_id, subscription_id)

    # ===== Metered usage =====
    @prot.post(
        "/usage_records",
        name="payments_create_usage_record",
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_idempotency_key)],
    )
    async def create_usage_record_endpoint(
        data: UsageRecordIn, svc: PaymentsService = Depends(get_service)
    ):
        out = await svc.create_usage_record(data)
        await svc.session.flush()
        return out

    # ===== Setup Intents (off-session readiness) =====
    @prot.post(
        "/setup_intents",
        name="payments_create_setup_intent",
        status_code=status.HTTP_201_CREATED,
        response_model=SetupIntentOut,
        dependencies=[Depends(require_idempotency_key)],
    )
    async def create_setup_intent(
        data: SetupIntentCreateIn,
        svc: PaymentsService = Depends(get_service),
    ):
        out = await svc.create_setup_intent(data)
        await svc.session.flush()
        return out

    @prot.post(
        "/setup_intents/{provider_setup_intent_id}/confirm",
        name="payments_confirm_setup_intent",
        response_model=SetupIntentOut,
        dependencies=[Depends(require_idempotency_key)],
    )
    async def confirm_setup_intent(
        provider_setup_intent_id: str, svc: PaymentsService = Depends(get_service)
    ):
        out = await svc.confirm_setup_intent(provider_setup_intent_id)
        await svc.session.flush()
        return out

    @prot.get(
        "/setup_intents/{provider_setup_intent_id}",
        name="payments_get_setup_intent",
        response_model=SetupIntentOut,
    )
    async def get_setup_intent(
        provider_setup_intent_id: str, svc: PaymentsService = Depends(get_service)
    ):
        return await svc.get_setup_intent(provider_setup_intent_id)

    # ===== 3DS/SCA resume (post-action) =====
    @prot.post(
        "/intents/{provider_intent_id}/resume",
        name="payments_resume_intent",
        response_model=IntentOut,
        dependencies=[Depends(require_idempotency_key)],
    )
    async def resume_intent(
        provider_intent_id: str,
        svc: PaymentsService = Depends(get_service),
    ):
        out = await svc.resume_intent_after_action(provider_intent_id)
        await svc.session.flush()
        return out

    # ===== Disputes =====
    @svc.get(
        "/disputes",
        name="payments_list_disputes",
        response_model=Paginated[DisputeOut],
        dependencies=[Depends(cursor_pager(default_limit=50, max_limit=200))],
    )
    async def list_disputes(
        status: Optional[str] = None,
        svc: PaymentsService = Depends(get_service),
    ):
        ctx = use_pagination()
        items, next_cursor = await svc.list_disputes(
            status=status, limit=ctx.limit, cursor=ctx.cursor
        )
        return ctx.wrap(items, next_cursor=next_cursor)

    @svc.get(
        "/disputes/{provider_dispute_id}",
        name="payments_get_dispute",
        response_model=DisputeOut,
    )
    async def get_dispute(provider_dispute_id: str, svc: PaymentsService = Depends(get_service)):
        return await svc.get_dispute(provider_dispute_id)

    @svc.post(
        "/disputes/{provider_dispute_id}/submit_evidence",
        name="payments_submit_dispute_evidence",
        dependencies=[Depends(require_idempotency_key)],
    )
    async def submit_dispute_evidence(
        provider_dispute_id: str,
        evidence: dict = Body(..., embed=True),  # free-form evidence blob you validate internally
        svc: PaymentsService = Depends(get_service),
    ):
        out = await svc.submit_dispute_evidence(provider_dispute_id, evidence)
        await svc.session.flush()
        return out

    # ===== Balance & Payouts =====
    @svc.get("/balance", name="payments_get_balance", response_model=BalanceSnapshotOut)
    async def get_balance(svc: PaymentsService = Depends(get_service)):
        return await svc.get_balance_snapshot()

    @svc.get(
        "/payouts",
        name="payments_list_payouts",
        response_model=Paginated[PayoutOut],
        dependencies=[Depends(cursor_pager(default_limit=50, max_limit=200))],
    )
    async def list_payouts(svc: PaymentsService = Depends(get_service)):
        ctx = use_pagination()
        items, next_cursor = await svc.list_payouts(limit=ctx.limit, cursor=ctx.cursor)
        return ctx.wrap(items, next_cursor=next_cursor)

    @svc.get(
        "/payouts/{provider_payout_id}",
        name="payments_get_payout",
        response_model=PayoutOut,
    )
    async def get_payout(provider_payout_id: str, svc: PaymentsService = Depends(get_service)):
        return await svc.get_payout(provider_payout_id)

    # ===== Webhook replay (operational) =====
    @svc.post(
        "/webhooks/replay",
        name="payments_replay_webhooks",
        response_model=WebhookReplayOut,
        dependencies=[Depends(require_idempotency_key)],
    )
    async def replay_webhooks(
        since: Optional[str] = None,
        until: Optional[str] = None,
        event_ids: Optional[list[str]] = Body(default=None),
        svc: PaymentsService = Depends(get_service),
    ):
        count = await svc.replay_webhooks(since, until, event_ids or [])
        await svc.session.flush()
        return {"replayed": count}

    routers.append(svc)
    routers.append(pub)
    return routers
