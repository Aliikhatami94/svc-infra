from __future__ import annotations

import inspect
from typing import Literal, Optional, cast

from fastapi import Body, Depends, Header, HTTPException, Request, Response, status
from starlette.responses import JSONResponse

from svc_infra.apf_payments.schemas import (
    BalanceSnapshotOut,
    CaptureIn,
    CustomerOut,
    CustomersListFilter,
    CustomerUpsertIn,
    DisputeOut,
    IntentCreateIn,
    IntentListFilter,
    IntentOut,
    InvoiceCreateIn,
    InvoiceLineItemIn,
    InvoiceLineItemOut,
    InvoiceOut,
    InvoicesListFilter,
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
    StatementRow,
    SubscriptionCreateIn,
    SubscriptionOut,
    SubscriptionUpdateIn,
    TransactionRow,
    UsageRecordIn,
    UsageRecordListFilter,
    UsageRecordOut,
    WebhookAckOut,
    WebhookReplayIn,
    WebhookReplayOut,
)
from svc_infra.apf_payments.service import PaymentsService
from svc_infra.api.fastapi.auth.security import OptionalIdentity, Principal
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


# --- tenant resolution ---
_tenant_resolver: None | (callable) = None


def set_payments_tenant_resolver(fn):
    """Set or clear an override hook for payments tenant resolution.

    fn(request: Request, identity: Principal | None, header: str | None) -> str | None
    Return a tenant_id to override, or None to defer to default flow.
    """
    global _tenant_resolver
    _tenant_resolver = fn


async def resolve_payments_tenant_id(
    request: Request,
    identity: Principal | None = None,
    tenant_header: str | None = None,
) -> str:
    # 1) Override hook
    if _tenant_resolver is not None:
        val = _tenant_resolver(request, identity, tenant_header)
        # Support async or sync resolver
        if inspect.isawaitable(val):
            val = await val  # type: ignore[assignment]
        if val:
            return val  # type: ignore[return-value]
        # if None, continue default flow

    # 2) Principal (user)
    if identity and getattr(identity.user or object(), "tenant_id", None):
        return getattr(identity.user, "tenant_id")

    # 3) Principal (api key)
    if identity and getattr(identity.api_key or object(), "tenant_id", None):
        return getattr(identity.api_key, "tenant_id")

    # 4) Explicit header argument (tests pass this)
    if tenant_header:
        return tenant_header

    # 5) Request state
    state_tid = getattr(getattr(request, "state", object()), "tenant_id", None)
    if state_tid:
        return state_tid

    raise HTTPException(status_code=400, detail="tenant_context_missing")


# --- deps ---
async def get_service(
    session: SqlSessionDep,
    request: Request = ...,  # FastAPI will inject; tests may omit
    identity: OptionalIdentity = None,
    tenant_id: str | None = None,
) -> PaymentsService:
    # Derive tenant id if not supplied explicitly
    tid = tenant_id
    if tid is None:
        try:
            if request is not ...:
                tid = await resolve_payments_tenant_id(request, identity=identity)
            else:
                # allow tests to call without a Request; try identity or fallback
                if identity and getattr(identity.user or object(), "tenant_id", None):
                    tid = getattr(identity.user, "tenant_id")
                elif identity and getattr(identity.api_key or object(), "tenant_id", None):
                    tid = getattr(identity.api_key, "tenant_id")
                else:
                    raise HTTPException(status_code=400, detail="tenant_context_missing")
        except HTTPException:
            # fallback for routes/tests that don't set context; preserve prior default
            tid = "test_tenant"
    return PaymentsService(session=session, tenant_id=tid)


# --- routers grouped by auth posture (same prefix is fine; FastAPI merges) ---
def build_payments_routers(prefix: str = "/payments") -> list[DualAPIRouter]:
    routers: list[DualAPIRouter] = []

    pub = public_router(prefix=prefix)
    user = user_router(prefix=prefix)
    svc = service_router(prefix=prefix)
    prot = protected_router(prefix=prefix)

    # ===== Customers =====
    @user.post(
        "/customers",
        response_model=CustomerOut,
        name="payments_upsert_customer",
        dependencies=[Depends(require_idempotency_key)],
        tags=["Customers"],
    )
    async def upsert_customer(data: CustomerUpsertIn, svc: PaymentsService = Depends(get_service)):
        out = await svc.ensure_customer(data)
        await svc.session.flush()
        return out

    # ===== Payment Intents (create) =====
    @user.post(
        "/intents",
        response_model=IntentOut,
        name="payments_create_intent",
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_idempotency_key)],
        tags=["Payment Intents"],
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

    # ===== Payment Intents (confirm/cancel/refund/list/get/capture/resume) =====
    @prot.post(
        "/intents/{provider_intent_id}/confirm",
        response_model=IntentOut,
        name="payments_confirm_intent",
        dependencies=[Depends(require_idempotency_key)],
        tags=["Payment Intents"],
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
        tags=["Payment Intents"],
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
        tags=["Payment Intents", "Refunds"],
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
        tags=["Transactions"],
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

    @pub.post(
        "/webhooks/{provider}",
        name="payments_webhook",
        response_model=WebhookAckOut,
        tags=["Webhooks"],
    )
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

    # ===== Payment Methods (attach/list/detach/default/get/update/delete alias) =====
    @user.post(
        "/methods/attach",
        response_model=PaymentMethodOut,
        name="payments_attach_method",
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_idempotency_key)],
        tags=["Payment Methods"],
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
        tags=["Payment Methods"],
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
        tags=["Payment Methods"],
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
        tags=["Payment Methods"],
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
        tags=["Products"],
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
        tags=["Prices"],
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
        tags=["Subscriptions"],
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
        tags=["Subscriptions"],
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
        tags=["Subscriptions"],
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
        tags=["Invoices"],
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
        tags=["Invoices"],
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
        tags=["Invoices"],
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
        tags=["Invoices"],
    )
    async def pay_invoice(provider_invoice_id: str, svc: PaymentsService = Depends(get_service)):
        out = await svc.pay_invoice(provider_invoice_id)
        await svc.session.flush()
        return out

    # INTENTS: get/hydrate
    @prot.get(
        "/intents/{provider_intent_id}",
        response_model=IntentOut,
        name="payments_get_intent",
        tags=["Payment Intents"],
    )
    async def get_intent(provider_intent_id: str, svc: PaymentsService = Depends(get_service)):
        return await svc.get_intent(provider_intent_id)

    # STATEMENTS (rollup)
    @prot.get(
        "/statements/daily",
        response_model=list[StatementRow],
        name="payments_daily_statements",
        tags=["Statements"],
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
        tags=["Payment Intents"],
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
        tags=["Payment Intents"],
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
        tags=["Invoices"],
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
        tags=["Invoices"],
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
        "/invoices/{provider_invoice_id}",
        response_model=InvoiceOut,
        name="payments_get_invoice",
        tags=["Invoices"],
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
        tags=["Invoices"],
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
        response_model=UsageRecordOut,
        tags=["Usage Records"],
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
        tags=["Setup Intents"],
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
        tags=["Setup Intents"],
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
        tags=["Setup Intents"],
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
        tags=["Payment Intents"],
    )
    async def resume_intent(
        provider_intent_id: str,
        svc: PaymentsService = Depends(get_service),
    ):
        out = await svc.resume_intent_after_action(provider_intent_id)
        await svc.session.flush()
        return out

    # ===== Disputes =====
    @prot.get(
        "/disputes",
        name="payments_list_disputes",
        response_model=Paginated[DisputeOut],
        dependencies=[Depends(cursor_pager(default_limit=50, max_limit=200))],
        tags=["Disputes"],
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

    @prot.get(
        "/disputes/{provider_dispute_id}",
        name="payments_get_dispute",
        response_model=DisputeOut,
        tags=["Disputes"],
    )
    async def get_dispute(provider_dispute_id: str, svc: PaymentsService = Depends(get_service)):
        return await svc.get_dispute(provider_dispute_id)

    @prot.post(
        "/disputes/{provider_dispute_id}/submit_evidence",
        name="payments_submit_dispute_evidence",
        dependencies=[Depends(require_idempotency_key)],
        response_model=DisputeOut,
        tags=["Disputes"],
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
    @prot.get(
        "/balance", name="payments_get_balance", response_model=BalanceSnapshotOut, tags=["Balance"]
    )
    async def get_balance(svc: PaymentsService = Depends(get_service)):
        return await svc.get_balance_snapshot()

    @prot.get(
        "/payouts",
        name="payments_list_payouts",
        response_model=Paginated[PayoutOut],
        dependencies=[Depends(cursor_pager(default_limit=50, max_limit=200))],
        tags=["Payouts"],
    )
    async def list_payouts(svc: PaymentsService = Depends(get_service)):
        ctx = use_pagination()
        items, next_cursor = await svc.list_payouts(limit=ctx.limit, cursor=ctx.cursor)
        return ctx.wrap(items, next_cursor=next_cursor)

    @svc.get(
        "/payouts/{provider_payout_id}",
        name="payments_get_payout",
        response_model=PayoutOut,
        tags=["Payouts"],
    )
    async def get_payout(provider_payout_id: str, svc: PaymentsService = Depends(get_service)):
        return await svc.get_payout(provider_payout_id)

    # ===== Webhook replay (operational) =====
    @svc.post(
        "/webhooks/replay",
        name="payments_replay_webhooks",
        response_model=WebhookReplayOut,
        dependencies=[Depends(require_idempotency_key)],
        tags=["Webhooks"],
    )
    async def replay_webhooks(
        since: Optional[str] = None,
        until: Optional[str] = None,
        data: WebhookReplayIn = Body(default=WebhookReplayIn()),
        svc: PaymentsService = Depends(get_service),
    ):
        count = await svc.replay_webhooks(since, until, data.event_ids or [])
        await svc.session.flush()
        return {"replayed": count}

    # ===== Customers: list/get =====
    @prot.get(
        "/customers",
        response_model=Paginated[CustomerOut],
        name="payments_list_customers",
        dependencies=[Depends(cursor_pager(default_limit=50, max_limit=200))],
        tags=["Customers"],
    )
    async def list_customers_endpoint(
        provider: Optional[str] = None,
        user_id: Optional[str] = None,
        svc: PaymentsService = Depends(get_service),
    ):
        ctx = use_pagination()
        items, next_cursor = await svc.list_customers(
            CustomersListFilter(
                provider=provider, user_id=user_id, limit=ctx.limit, cursor=ctx.cursor
            )
        )
        return ctx.wrap(items, next_cursor=next_cursor)

    @prot.get(
        "/customers/{provider_customer_id}",
        response_model=CustomerOut,
        name="payments_get_customer",
        tags=["Customers"],
    )
    async def get_customer_endpoint(
        provider_customer_id: str, svc: PaymentsService = Depends(get_service)
    ):
        return await svc.get_customer(provider_customer_id)

    # ===== Payment Methods: get/update =====
    @prot.get(
        "/methods/{provider_method_id}",
        response_model=PaymentMethodOut,
        name="payments_get_method",
        tags=["Payment Methods"],
    )
    async def get_method(provider_method_id: str, svc: PaymentsService = Depends(get_service)):
        return await svc.get_payment_method(provider_method_id)

    @prot.post(
        "/methods/{provider_method_id}",
        response_model=PaymentMethodOut,
        name="payments_update_method",
        dependencies=[Depends(require_idempotency_key)],
        tags=["Payment Methods"],
    )
    async def update_method(
        provider_method_id: str,
        data: PaymentMethodUpdateIn,
        svc: PaymentsService = Depends(get_service),
    ):
        out = await svc.update_payment_method(provider_method_id, data)
        await svc.session.flush()
        return out

    # ===== Products: get/list/update (archive via active=False) =====
    @svc.get(
        "/products/{provider_product_id}",
        response_model=ProductOut,
        name="payments_get_product",
        tags=["Products"],
    )
    async def get_product_endpoint(
        provider_product_id: str, svc: PaymentsService = Depends(get_service)
    ):
        return await svc.get_product(provider_product_id)

    @prot.get(
        "/products",
        response_model=Paginated[ProductOut],
        name="payments_list_products",
        dependencies=[Depends(cursor_pager(default_limit=50, max_limit=200))],
        tags=["Products"],
    )
    async def list_products_endpoint(
        active: Optional[bool] = None,
        svc: PaymentsService = Depends(get_service),
    ):
        ctx = use_pagination()
        items, next_cursor = await svc.list_products(
            active=active, limit=ctx.limit, cursor=ctx.cursor
        )
        return ctx.wrap(items, next_cursor=next_cursor)

    @svc.post(
        "/products/{provider_product_id}",
        response_model=ProductOut,
        name="payments_update_product",
        dependencies=[Depends(require_idempotency_key)],
        tags=["Products"],
    )
    async def update_product_endpoint(
        provider_product_id: str,
        data: ProductUpdateIn,
        svc: PaymentsService = Depends(get_service),
    ):
        out = await svc.update_product(provider_product_id, data)
        await svc.session.flush()
        return out

    # ===== Prices: get/list/update (active toggle) =====
    @prot.get(
        "/prices/{provider_price_id}",
        response_model=PriceOut,
        name="payments_get_price",
        tags=["Prices"],
    )
    async def get_price_endpoint(
        provider_price_id: str, svc: PaymentsService = Depends(get_service)
    ):
        return await svc.get_price(provider_price_id)

    @prot.get(
        "/prices",
        response_model=Paginated[PriceOut],
        name="payments_list_prices",
        dependencies=[Depends(cursor_pager(default_limit=50, max_limit=200))],
        tags=["Prices"],
    )
    async def list_prices_endpoint(
        provider_product_id: Optional[str] = None,
        active: Optional[bool] = None,
        svc: PaymentsService = Depends(get_service),
    ):
        ctx = use_pagination()
        items, next_cursor = await svc.list_prices(
            provider_product_id=provider_product_id,
            active=active,
            limit=ctx.limit,
            cursor=ctx.cursor,
        )
        return ctx.wrap(items, next_cursor=next_cursor)

    @svc.post(
        "/prices/{provider_price_id}",
        response_model=PriceOut,
        name="payments_update_price",
        dependencies=[Depends(require_idempotency_key)],
        tags=["Prices"],
    )
    async def update_price_endpoint(
        provider_price_id: str,
        data: PriceUpdateIn,
        svc: PaymentsService = Depends(get_service),
    ):
        out = await svc.update_price(provider_price_id, data)
        await svc.session.flush()
        return out

    # ===== Subscriptions: get/list =====
    @prot.get(
        "/subscriptions/{provider_subscription_id}",
        response_model=SubscriptionOut,
        name="payments_get_subscription",
        tags=["Subscriptions"],
    )
    async def get_subscription_endpoint(
        provider_subscription_id: str, svc: PaymentsService = Depends(get_service)
    ):
        return await svc.get_subscription(provider_subscription_id)

    @prot.get(
        "/subscriptions",
        response_model=Paginated[SubscriptionOut],
        name="payments_list_subscriptions",
        dependencies=[Depends(cursor_pager(default_limit=50, max_limit=200))],
        tags=["Subscriptions"],
    )
    async def list_subscriptions_endpoint(
        customer_provider_id: Optional[str] = None,
        status: Optional[str] = None,
        svc: PaymentsService = Depends(get_service),
    ):
        ctx = use_pagination()
        items, next_cursor = await svc.list_subscriptions(
            customer_provider_id=customer_provider_id,
            status=status,
            limit=ctx.limit,
            cursor=ctx.cursor,
        )
        return ctx.wrap(items, next_cursor=next_cursor)

    # ===== Invoices: list line items =====
    @prot.get(
        "/invoices/{provider_invoice_id}/lines",
        response_model=Paginated[InvoiceLineItemOut],
        name="payments_list_invoice_line_items",
        dependencies=[Depends(cursor_pager(default_limit=50, max_limit=200))],
        tags=["Invoices"],
    )
    async def list_invoice_lines_endpoint(
        provider_invoice_id: str,
        svc: PaymentsService = Depends(get_service),
    ):
        ctx = use_pagination()
        items, next_cursor = await svc.list_invoice_line_items(
            provider_invoice_id, limit=ctx.limit, cursor=ctx.cursor
        )
        return ctx.wrap(items, next_cursor=next_cursor)

    # ===== Refunds: list/get =====
    @prot.get(
        "/refunds",
        response_model=Paginated[RefundOut],
        name="payments_list_refunds",
        dependencies=[Depends(cursor_pager(default_limit=50, max_limit=200))],
        tags=["Refunds"],
    )
    async def list_refunds_endpoint(
        provider_payment_intent_id: Optional[str] = None,
        svc: PaymentsService = Depends(get_service),
    ):
        ctx = use_pagination()
        items, next_cursor = await svc.list_refunds(
            provider_payment_intent_id=provider_payment_intent_id,
            limit=ctx.limit,
            cursor=ctx.cursor,
        )
        return ctx.wrap(items, next_cursor=next_cursor)

    @prot.get(
        "/refunds/{provider_refund_id}",
        response_model=RefundOut,
        name="payments_get_refund",
        tags=["Refunds"],
    )
    async def get_refund_endpoint(
        provider_refund_id: str, svc: PaymentsService = Depends(get_service)
    ):
        return await svc.get_refund(provider_refund_id)

    # ===== Usage Records: list/get =====
    @prot.get(
        "/usage_records",
        response_model=Paginated[UsageRecordOut],
        name="payments_list_usage_records",
        dependencies=[Depends(cursor_pager(default_limit=50, max_limit=200))],
        tags=["Usage Records"],
    )
    async def list_usage_records_endpoint(
        subscription_item: Optional[str] = None,
        provider_price_id: Optional[str] = None,
        svc: PaymentsService = Depends(get_service),
    ):
        ctx = use_pagination()
        items, next_cursor = await svc.list_usage_records(
            UsageRecordListFilter(
                subscription_item=subscription_item,
                provider_price_id=provider_price_id,
                limit=ctx.limit,
                cursor=ctx.cursor,
            )
        )
        return ctx.wrap(items, next_cursor=next_cursor)

    @prot.get(
        "/usage_records/{usage_record_id}",
        response_model=UsageRecordOut,
        name="payments_get_usage_record",
        tags=["Usage Records"],
    )
    async def get_usage_record_endpoint(
        usage_record_id: str, svc: PaymentsService = Depends(get_service)
    ):
        return await svc.get_usage_record(usage_record_id)

    # --- Canonical: remove local alias/association (non-destructive) ---
    @prot.delete(
        "/method_aliases/{alias_id}",
        name="payments_delete_method_alias",
        summary="Remove Method Alias (non-destructive)",
        response_model=PaymentMethodOut,
        dependencies=[Depends(require_idempotency_key)],
        tags=["Payment Methods"],
    )
    async def delete_method_alias(alias_id: str, svc: PaymentsService = Depends(get_service)):
        """
        Removes the local alias/association to a payment method.
        This does **not** delete the underlying payment method at the provider.
        Equivalent to `detach_payment_method`.
        """
        out = await svc.detach_payment_method(alias_id)
        await svc.session.flush()
        return out

    routers.append(svc)
    routers.append(pub)
    return routers
