from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    LedgerEntry,
    PayCustomer,
    PayDispute,
    PayEvent,
    PayIntent,
    PayInvoice,
    PayPaymentMethod,
    PayPayout,
    PayPrice,
    PayProduct,
    PaySetupIntent,
    PaySubscription,
)
from .provider.registry import get_provider_registry
from .schemas import (
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
    UsageRecordIn,
    UsageRecordListFilter,
    UsageRecordOut,
)
from .settings import get_payments_settings


def _default_provider_name() -> str:
    return get_payments_settings().default_provider


class PaymentsService:
    """Payments service facade wrapping provider adapters and persisting key rows.

    NOTE: tenant_id is now required for all persistence operations. This is a breaking
    change; callers must supply a valid tenant scope. (Future: could allow multi-tenant
    mapping via adapter registry.)
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        tenant_id: str,
        provider_name: Optional[str] = None,
    ):
        if not tenant_id:
            raise ValueError("tenant_id is required for PaymentsService")
        self.session = session
        self.tenant_id = tenant_id
        self._provider_name = (provider_name or _default_provider_name()).lower()
        self._adapter = None  # resolved on first use

    # --- internal helpers -----------------------------------------------------

    def _get_adapter(self):
        if self._adapter is not None:
            return self._adapter
        reg = get_provider_registry()
        # Try to fetch the named adapter; if missing, raise a helpful error
        try:
            self._adapter = reg.get(self._provider_name)
        except Exception as e:
            raise RuntimeError(
                f"No payments adapter registered for '{self._provider_name}'. "
                "Install and register a provider (e.g., `stripe`) OR pass a custom adapter via "
                "`add_payments(app, adapters=[...])`. If you only need DB endpoints (like "
                "`/payments/transactions`), this error will not occur unless you call a provider API."
            ) from e
        return self._adapter

    # --- internal event dispatcher (shared by webhook + replay) ---------------
    async def _dispatch_event(self, provider: str, parsed: dict) -> None:
        typ = parsed.get("type", "")
        obj = parsed.get("data") or {}

        if provider == "stripe":
            if typ == "payment_intent.succeeded":
                await self._post_sale(obj)
            elif typ == "charge.refunded":
                await self._post_refund(obj)
            elif typ == "charge.captured":
                await self._post_capture(obj)

    # --- Customers ------------------------------------------------------------

    async def ensure_customer(self, data: CustomerUpsertIn) -> CustomerOut:
        adapter = self._get_adapter()
        out = await adapter.ensure_customer(data)
        # upsert local row
        existing = await self.session.scalar(
            select(PayCustomer).where(
                PayCustomer.provider == out.provider,
                PayCustomer.provider_customer_id == out.provider_customer_id,
            )
        )
        if not existing:
            # If your PayCustomer model has additional columns (email/name), include them here.
            self.session.add(
                PayCustomer(
                    tenant_id=self.tenant_id,
                    provider=out.provider,
                    provider_customer_id=out.provider_customer_id,
                    user_id=data.user_id,
                )
            )
        return out

    # --- Intents --------------------------------------------------------------

    async def create_intent(self, user_id: Optional[str], data: IntentCreateIn) -> IntentOut:
        adapter = self._get_adapter()
        out = await adapter.create_intent(data, user_id=user_id)
        self.session.add(
            PayIntent(
                tenant_id=self.tenant_id,
                provider=out.provider,
                provider_intent_id=out.provider_intent_id,
                user_id=user_id,
                amount=out.amount,
                currency=out.currency,
                status=out.status,
                client_secret=out.client_secret,
            )
        )
        return out

    async def confirm_intent(self, provider_intent_id: str) -> IntentOut:
        adapter = self._get_adapter()
        out = await adapter.confirm_intent(provider_intent_id)
        pi = await self.session.scalar(
            select(PayIntent).where(PayIntent.provider_intent_id == provider_intent_id)
        )
        if pi:
            pi.status = out.status
            pi.client_secret = out.client_secret or pi.client_secret
        return out

    async def cancel_intent(self, provider_intent_id: str) -> IntentOut:
        adapter = self._get_adapter()
        out = await adapter.cancel_intent(provider_intent_id)
        pi = await self.session.scalar(
            select(PayIntent).where(PayIntent.provider_intent_id == provider_intent_id)
        )
        if pi:
            pi.status = out.status
        return out

    async def refund(self, provider_intent_id: str, data: RefundIn) -> IntentOut:
        adapter = self._get_adapter()
        out = await adapter.refund(provider_intent_id, data)
        # Create ledger entry if amount present and not already recorded
        pi = await self.session.scalar(
            select(PayIntent).where(PayIntent.provider_intent_id == provider_intent_id)
        )
        if pi:
            amount = int(data.amount) if data.amount is not None else out.amount
            # Guard against duplicates (same provider_ref + kind)
            existing = await self.session.scalar(
                select(LedgerEntry).where(
                    LedgerEntry.provider_ref == provider_intent_id,
                    LedgerEntry.kind == "refund",
                )
            )
            if amount > 0 and not existing:
                self.session.add(
                    LedgerEntry(
                        tenant_id=self.tenant_id,
                        provider=pi.provider,
                        provider_ref=provider_intent_id,
                        user_id=pi.user_id,
                        amount=+amount,
                        currency=out.currency,
                        kind="refund",
                        status="posted",
                    )
                )
        return out

    # --- Webhooks -------------------------------------------------------------

    async def handle_webhook(self, provider: str, signature: str | None, payload: bytes) -> dict:
        adapter = self._get_adapter()
        parsed = await adapter.verify_and_parse_webhook(signature, payload)
        self.session.add(
            PayEvent(
                tenant_id=self.tenant_id,
                provider=provider,
                provider_event_id=parsed["id"],
                type=parsed.get("type", ""),
                payload_json=parsed,
            )
        )

        await self._dispatch_event(provider, parsed)
        return {"ok": True}

    # --- Ledger postings ------------------------------------------------------

    async def _post_sale(self, pi_obj: dict):
        provider_intent_id = pi_obj.get("id")
        amount = int(pi_obj.get("amount") or 0)
        currency = str(pi_obj.get("currency") or "USD").upper()
        intent = await self.session.scalar(
            select(PayIntent).where(PayIntent.provider_intent_id == provider_intent_id)
        )
        if intent:
            intent.status = "succeeded"
            self.session.add(
                LedgerEntry(
                    tenant_id=self.tenant_id,
                    provider=intent.provider,
                    provider_ref=provider_intent_id,
                    user_id=intent.user_id,
                    amount=+amount,
                    currency=currency,
                    kind="payment",
                    status="posted",
                )
            )

    async def _post_capture(self, charge_obj: dict):
        amount = int(charge_obj.get("amount") or 0)
        currency = str(charge_obj.get("currency") or "USD").upper()
        pi_id = charge_obj.get("payment_intent") or ""
        intent = await self.session.scalar(
            select(PayIntent).where(PayIntent.provider_intent_id == pi_id)
        )
        if intent:
            # Avoid duplicate capture entries
            existing = await self.session.scalar(
                select(LedgerEntry).where(
                    LedgerEntry.provider_ref == charge_obj.get("id"),
                    LedgerEntry.kind == "capture",
                )
            )
            if not existing:
                self.session.add(
                    LedgerEntry(
                        tenant_id=self.tenant_id,
                        provider=intent.provider,
                        provider_ref=charge_obj.get("id"),
                        user_id=intent.user_id,
                        amount=+amount,
                        currency=currency,
                        kind="capture",
                        status="posted",
                    )
                )
            intent.captured = True

    async def _post_refund(self, charge_obj: dict):
        amount = int(charge_obj.get("amount_refunded") or 0)
        currency = str(charge_obj.get("currency") or "USD").upper()
        pi_id = charge_obj.get("payment_intent") or ""
        intent = await self.session.scalar(
            select(PayIntent).where(PayIntent.provider_intent_id == pi_id)
        )
        if intent and amount > 0:
            existing = await self.session.scalar(
                select(LedgerEntry).where(
                    LedgerEntry.provider_ref == charge_obj.get("id"),
                    LedgerEntry.kind == "refund",
                )
            )
            if not existing:
                self.session.add(
                    LedgerEntry(
                        tenant_id=self.tenant_id,
                        provider=intent.provider,
                        provider_ref=charge_obj.get("id"),
                        user_id=intent.user_id,
                        amount=+amount,
                        currency=currency,
                        kind="refund",
                        status="posted",
                    )
                )

    async def attach_payment_method(self, data: PaymentMethodAttachIn) -> PaymentMethodOut:
        out = await self._get_adapter().attach_payment_method(data)
        # Upsert locally for quick listing
        pm = PayPaymentMethod(
            tenant_id=self.tenant_id,
            provider=out.provider,
            provider_customer_id=out.provider_customer_id,
            provider_method_id=out.provider_method_id,
            brand=out.brand,
            last4=out.last4,
            exp_month=out.exp_month,
            exp_year=out.exp_year,
            is_default=out.is_default,
        )
        self.session.add(pm)
        return out

    async def list_payment_methods(self, provider_customer_id: str) -> list[PaymentMethodOut]:
        return await self._get_adapter().list_payment_methods(provider_customer_id)

    async def detach_payment_method(self, provider_method_id: str) -> PaymentMethodOut:
        return await self._get_adapter().detach_payment_method(provider_method_id)

    async def set_default_payment_method(
        self, provider_customer_id: str, provider_method_id: str
    ) -> PaymentMethodOut:
        return await self._get_adapter().set_default_payment_method(
            provider_customer_id, provider_method_id
        )

    # --- Products/Prices ---
    async def create_product(self, data: ProductCreateIn) -> ProductOut:
        out = await self._get_adapter().create_product(data)
        self.session.add(
            PayProduct(
                tenant_id=self.tenant_id,
                provider=out.provider,
                provider_product_id=out.provider_product_id,
                name=out.name,
                active=out.active,
            )
        )
        return out

    async def create_price(self, data: PriceCreateIn) -> PriceOut:
        out = await self._get_adapter().create_price(data)
        self.session.add(
            PayPrice(
                tenant_id=self.tenant_id,
                provider=out.provider,
                provider_price_id=out.provider_price_id,
                provider_product_id=out.provider_product_id,
                currency=out.currency,
                unit_amount=out.unit_amount,
                interval=out.interval,
                trial_days=out.trial_days,
                active=out.active,
            )
        )
        return out

    # --- Subscriptions ---
    async def create_subscription(self, data: SubscriptionCreateIn) -> SubscriptionOut:
        out = await self._get_adapter().create_subscription(data)
        self.session.add(
            PaySubscription(
                tenant_id=self.tenant_id,
                provider=out.provider,
                provider_subscription_id=out.provider_subscription_id,
                provider_price_id=out.provider_price_id,
                status=out.status,
                quantity=out.quantity,
                cancel_at_period_end=out.cancel_at_period_end,
            )
        )
        return out

    async def update_subscription(
        self, provider_subscription_id: str, data: SubscriptionUpdateIn
    ) -> SubscriptionOut:
        out = await self._get_adapter().update_subscription(provider_subscription_id, data)
        # Optionally reflect status/quantity locally (query + update if exists)
        return out

    async def cancel_subscription(
        self, provider_subscription_id: str, at_period_end: bool = True
    ) -> SubscriptionOut:
        out = await self._get_adapter().cancel_subscription(provider_subscription_id, at_period_end)
        return out

    # --- Invoices ---
    async def create_invoice(self, data: InvoiceCreateIn) -> InvoiceOut:
        out = await self._get_adapter().create_invoice(data)
        self.session.add(
            PayInvoice(
                tenant_id=self.tenant_id,
                provider=out.provider,
                provider_invoice_id=out.provider_invoice_id,
                provider_customer_id=out.provider_customer_id,
                status=out.status,
                amount_due=out.amount_due,
                currency=out.currency,
                hosted_invoice_url=out.hosted_invoice_url,
                pdf_url=out.pdf_url,
            )
        )
        return out

    async def finalize_invoice(self, provider_invoice_id: str) -> InvoiceOut:
        return await self._get_adapter().finalize_invoice(provider_invoice_id)

    async def void_invoice(self, provider_invoice_id: str) -> InvoiceOut:
        return await self._get_adapter().void_invoice(provider_invoice_id)

    async def pay_invoice(self, provider_invoice_id: str) -> InvoiceOut:
        return await self._get_adapter().pay_invoice(provider_invoice_id)

    # --- Intents QoL ---
    async def get_intent(self, provider_intent_id: str) -> IntentOut:
        return await self._get_adapter().hydrate_intent(provider_intent_id)

    # --- Statements/Rollups ---
    async def daily_statements_rollup(
        self, date_from: str | None = None, date_to: str | None = None
    ) -> list[StatementRow]:
        from datetime import datetime

        from sqlalchemy import func

        q = select(
            func.date_trunc("day", LedgerEntry.ts).label("day"),
            LedgerEntry.currency,
            func.sum(func.case((LedgerEntry.kind == "payment", LedgerEntry.amount), else_=0)).label(
                "gross"
            ),
            func.sum(func.case((LedgerEntry.kind == "refund", LedgerEntry.amount), else_=0)).label(
                "refunds"
            ),
            func.sum(func.case((LedgerEntry.kind == "fee", LedgerEntry.amount), else_=0)).label(
                "fees"
            ),
            func.count().label("count"),
        )
        if date_from:
            try:
                q = q.where(LedgerEntry.ts >= datetime.fromisoformat(date_from))
            except Exception:
                pass
        if date_to:
            try:
                q = q.where(LedgerEntry.ts <= datetime.fromisoformat(date_to))
            except Exception:
                pass
        q = q.group_by(func.date_trunc("day", LedgerEntry.ts), LedgerEntry.currency).order_by(
            func.date_trunc("day", LedgerEntry.ts).desc()
        )

        rows = (await self.session.execute(q)).all()
        out: list[StatementRow] = []
        for day, currency, gross, refunds, fees, count in rows:
            gross = int(gross or 0)
            refunds = int(refunds or 0)
            fees = int(fees or 0)
            out.append(
                StatementRow(
                    period_start=day.isoformat(),
                    period_end=day.isoformat(),
                    currency=str(currency).upper(),
                    gross=gross,
                    refunds=refunds,
                    fees=fees,
                    net=gross - refunds - fees,
                    count=int(count or 0),
                )
            )
        return out

    async def capture_intent(self, provider_intent_id: str, data: CaptureIn) -> IntentOut:
        out = await self._get_adapter().capture_intent(
            provider_intent_id, amount=int(data.amount) if data.amount is not None else None
        )
        pi = await self.session.scalar(
            select(PayIntent).where(PayIntent.provider_intent_id == provider_intent_id)
        )
        if pi:
            pi.status = out.status
            if out.status in ("succeeded", "requires_capture"):  # Stripe specifics vary
                pi.captured = True if out.status == "succeeded" else pi.captured
                # Add capture ledger entry if succeeded and not already posted
                if out.status == "succeeded":
                    existing = await self.session.scalar(
                        select(LedgerEntry).where(
                            LedgerEntry.provider_ref == provider_intent_id,
                            LedgerEntry.kind == "capture",
                        )
                    )
                    if not existing:
                        self.session.add(
                            LedgerEntry(
                                tenant_id=self.tenant_id,
                                provider=pi.provider,
                                provider_ref=provider_intent_id,
                                user_id=pi.user_id,
                                amount=+out.amount,
                                currency=out.currency,
                                kind="capture",
                                status="posted",
                            )
                        )
        return out

    async def list_intents(self, f: IntentListFilter) -> tuple[list[IntentOut], str | None]:
        return await self._get_adapter().list_intents(
            customer_provider_id=f.customer_provider_id,
            status=f.status,
            limit=f.limit or 50,
            cursor=f.cursor,
        )

    # ---- Invoices: lines/list/get/preview ----
    async def add_invoice_line_item(
        self, provider_invoice_id: str, data: InvoiceLineItemIn
    ) -> InvoiceOut:
        return await self._get_adapter().add_invoice_line_item(provider_invoice_id, data)

    async def list_invoices(self, f: InvoicesListFilter) -> tuple[list[InvoiceOut], str | None]:
        return await self._get_adapter().list_invoices(
            customer_provider_id=f.customer_provider_id,
            status=f.status,
            limit=f.limit or 50,
            cursor=f.cursor,
        )

    async def get_invoice(self, provider_invoice_id: str) -> InvoiceOut:
        return await self._get_adapter().get_invoice(provider_invoice_id)

    async def preview_invoice(
        self, customer_provider_id: str, subscription_id: str | None
    ) -> InvoiceOut:
        return await self._get_adapter().preview_invoice(
            customer_provider_id=customer_provider_id, subscription_id=subscription_id
        )

    # ---- Metered usage ----
    async def create_usage_record(self, data: UsageRecordIn) -> UsageRecordOut:
        return await self._get_adapter().create_usage_record(data)

    # --- Setup Intents --------------------------------------------------------
    async def create_setup_intent(self, data: SetupIntentCreateIn) -> SetupIntentOut:
        out = await self._get_adapter().create_setup_intent(data)
        self.session.add(
            PaySetupIntent(
                tenant_id=self.tenant_id,
                provider=out.provider,
                provider_setup_intent_id=out.provider_setup_intent_id,
                user_id=None,
                status=out.status,
                client_secret=out.client_secret,
            )
        )
        return out

    async def confirm_setup_intent(self, provider_setup_intent_id: str) -> SetupIntentOut:
        out = await self._get_adapter().confirm_setup_intent(provider_setup_intent_id)
        row = await self.session.scalar(
            select(PaySetupIntent).where(
                PaySetupIntent.provider_setup_intent_id == provider_setup_intent_id
            )
        )
        if row:
            row.status = out.status
            row.client_secret = out.client_secret or row.client_secret
        return out

    async def get_setup_intent(self, provider_setup_intent_id: str) -> SetupIntentOut:
        out = await self._get_adapter().get_setup_intent(provider_setup_intent_id)
        # opportunistic upsert
        row = await self.session.scalar(
            select(PaySetupIntent).where(
                PaySetupIntent.provider_setup_intent_id == provider_setup_intent_id
            )
        )
        if row:
            row.status = out.status
            row.client_secret = out.client_secret or row.client_secret
        else:
            self.session.add(
                PaySetupIntent(
                    tenant_id=self.tenant_id,
                    provider=out.provider,
                    provider_setup_intent_id=out.provider_setup_intent_id,
                    user_id=None,
                    status=out.status,
                    client_secret=out.client_secret,
                )
            )
        return out

    # --- SCA / 3DS resume -----------------------------------------------------
    async def resume_intent_after_action(self, provider_intent_id: str) -> IntentOut:
        out = await self._get_adapter().resume_intent_after_action(provider_intent_id)
        pi = await self.session.scalar(
            select(PayIntent).where(PayIntent.provider_intent_id == provider_intent_id)
        )
        if pi:
            pi.status = out.status
            pi.client_secret = out.client_secret or pi.client_secret
        return out

    # --- Disputes -------------------------------------------------------------
    async def list_disputes(
        self, *, status: Optional[str], limit: int, cursor: Optional[str]
    ) -> tuple[list[DisputeOut], Optional[str]]:
        return await self._get_adapter().list_disputes(status=status, limit=limit, cursor=cursor)

    async def get_dispute(self, provider_dispute_id: str) -> DisputeOut:
        out = await self._get_adapter().get_dispute(provider_dispute_id)
        # Upsert locally
        row = await self.session.scalar(
            select(PayDispute).where(PayDispute.provider_dispute_id == provider_dispute_id)
        )
        if row:
            row.status = out.status
            row.amount = out.amount
            row.currency = out.currency
        else:
            self.session.add(
                PayDispute(
                    tenant_id=self.tenant_id,
                    provider=out.provider,
                    provider_dispute_id=out.provider_dispute_id,
                    provider_charge_id=None,  # set if adapter returns it
                    amount=out.amount,
                    currency=out.currency,
                    reason=out.reason,
                    status=out.status,
                )
            )
        return out

    async def submit_dispute_evidence(self, provider_dispute_id: str, evidence: dict) -> DisputeOut:
        out = await self._get_adapter().submit_dispute_evidence(provider_dispute_id, evidence)
        # reflect status
        row = await self.session.scalar(
            select(PayDispute).where(PayDispute.provider_dispute_id == provider_dispute_id)
        )
        if row:
            row.status = out.status
        return out

    # --- Balance --------------------------------------------------------------
    async def get_balance_snapshot(self) -> BalanceSnapshotOut:
        return await self._get_adapter().get_balance_snapshot()

    # --- Payouts --------------------------------------------------------------
    async def list_payouts(
        self, *, limit: int, cursor: Optional[str]
    ) -> tuple[list[PayoutOut], Optional[str]]:
        return await self._get_adapter().list_payouts(limit=limit, cursor=cursor)

    async def get_payout(self, provider_payout_id: str) -> PayoutOut:
        out = await self._get_adapter().get_payout(provider_payout_id)
        # Upsert locally
        row = await self.session.scalar(
            select(PayPayout).where(PayPayout.provider_payout_id == provider_payout_id)
        )
        if row:
            row.status = out.status
            row.amount = out.amount
            row.currency = out.currency
            # arrival_date/type optional; update if present
        else:
            self.session.add(
                PayPayout(
                    tenant_id=self.tenant_id,
                    provider=out.provider,
                    provider_payout_id=out.provider_payout_id,
                    amount=out.amount,
                    currency=out.currency,
                    status=out.status,
                    # arrival_date/out.type if you add them onto PayoutOut
                )
            )
        return out

    # --- Webhook replay -------------------------------------------------------
    async def replay_webhooks(
        self, since: Optional[str], until: Optional[str], event_ids: list[str]
    ) -> int:
        from datetime import datetime

        q = select(PayEvent).where(PayEvent.provider == self._provider_name)
        if event_ids:
            q = q.where(PayEvent.provider_event_id.in_(event_ids))
        else:
            # ISO8601 strings expected; ignore parsing errors safely
            if since:
                try:
                    q = q.where(PayEvent.received_at >= datetime.fromisoformat(since))
                except Exception:
                    pass
            if until:
                try:
                    q = q.where(PayEvent.received_at <= datetime.fromisoformat(until))
                except Exception:
                    pass

        rows = (await self.session.execute(q)).scalars().all()
        for ev in rows:
            await self._dispatch_event(ev.provider, ev.payload_json)

        return len(rows)

    # ---- Customers ----
    async def list_customers(self, f: CustomersListFilter) -> tuple[list[CustomerOut], str | None]:
        adapter = self._get_adapter()
        try:
            return await adapter.list_customers(
                provider=f.provider, user_id=f.user_id, limit=f.limit or 50, cursor=f.cursor
            )
        except NotImplementedError:
            # Fallback to local DB listing
            q = select(PayCustomer).order_by(PayCustomer.provider_customer_id.asc())
            if f.provider:
                q = q.where(PayCustomer.provider == f.provider)
            if f.user_id:
                q = q.where(PayCustomer.user_id == f.user_id)
            rows = (await self.session.execute(q)).scalars().all()
            # simple cursor by provider_customer_id; production can optimize
            next_cursor = None
            if f.limit and len(rows) > f.limit:
                rows = rows[: f.limit]
                next_cursor = rows[-1].provider_customer_id
            return (
                [
                    CustomerOut(
                        id=r.id,
                        provider=r.provider,
                        provider_customer_id=r.provider_customer_id,
                        email=None,
                        name=None,
                    )
                    for r in rows
                ],
                next_cursor,
            )

    async def get_customer(self, provider_customer_id: str) -> CustomerOut:
        adapter = self._get_adapter()
        out = await adapter.get_customer(provider_customer_id)
        if out is None:
            raise RuntimeError("Customer not found")
        # upsert locally
        row = await self.session.scalar(
            select(PayCustomer).where(PayCustomer.provider_customer_id == provider_customer_id)
        )
        if not row:
            self.session.add(
                PayCustomer(
                    tenant_id=self.tenant_id,
                    provider=out.provider,
                    provider_customer_id=out.provider_customer_id,
                    user_id=None,
                )
            )
        return out

    # ---- Products / Prices ----
    async def get_product(self, provider_product_id: str) -> ProductOut:
        return await self._get_adapter().get_product(provider_product_id)

    async def list_products(
        self, *, active: bool | None, limit: int, cursor: str | None
    ) -> tuple[list[ProductOut], str | None]:
        return await self._get_adapter().list_products(active=active, limit=limit, cursor=cursor)

    async def update_product(self, provider_product_id: str, data: ProductUpdateIn) -> ProductOut:
        out = await self._get_adapter().update_product(provider_product_id, data)
        # reflect DB
        row = await self.session.scalar(
            select(PayProduct).where(PayProduct.provider_product_id == provider_product_id)
        )
        if row:
            if data.name is not None:
                row.name = data.name
            if data.active is not None:
                row.active = data.active
        return out

    async def get_price(self, provider_price_id: str) -> PriceOut:
        return await self._get_adapter().get_price(provider_price_id)

    async def list_prices(
        self,
        *,
        provider_product_id: str | None,
        active: bool | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[PriceOut], str | None]:
        return await self._get_adapter().list_prices(
            provider_product_id=provider_product_id, active=active, limit=limit, cursor=cursor
        )

    async def update_price(self, provider_price_id: str, data: PriceUpdateIn) -> PriceOut:
        out = await self._get_adapter().update_price(provider_price_id, data)
        row = await self.session.scalar(
            select(PayPrice).where(PayPrice.provider_price_id == provider_price_id)
        )
        if row and data.active is not None:
            row.active = data.active
        return out

    # ---- Subscriptions ----
    async def get_subscription(self, provider_subscription_id: str) -> SubscriptionOut:
        return await self._get_adapter().get_subscription(provider_subscription_id)

    async def list_subscriptions(
        self,
        *,
        customer_provider_id: str | None,
        status: str | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[SubscriptionOut], str | None]:
        return await self._get_adapter().list_subscriptions(
            customer_provider_id=customer_provider_id, status=status, limit=limit, cursor=cursor
        )

    # ---- Payment Methods (get/update) ----
    async def get_payment_method(self, provider_method_id: str) -> PaymentMethodOut:
        return await self._get_adapter().get_payment_method(provider_method_id)

    async def update_payment_method(
        self, provider_method_id: str, data: PaymentMethodUpdateIn
    ) -> PaymentMethodOut:
        out = await self._get_adapter().update_payment_method(provider_method_id, data)
        row = await self.session.scalar(
            select(PayPaymentMethod).where(
                PayPaymentMethod.provider_method_id == provider_method_id
            )
        )
        if row:
            if data.name is not None:
                pass  # keep local-only if/when you add column
            if data.exp_month is not None:
                row.exp_month = data.exp_month
            if data.exp_year is not None:
                row.exp_year = data.exp_year
        return out

    # ---- Refunds list/get ----
    async def list_refunds(
        self, *, provider_payment_intent_id: str | None, limit: int, cursor: str | None
    ) -> tuple[list[RefundOut], str | None]:
        return await self._get_adapter().list_refunds(
            provider_payment_intent_id=provider_payment_intent_id, limit=limit, cursor=cursor
        )

    async def get_refund(self, provider_refund_id: str) -> RefundOut:
        return await self._get_adapter().get_refund(provider_refund_id)

    # ---- Invoice line items list ----
    async def list_invoice_line_items(
        self, provider_invoice_id: str, *, limit: int, cursor: str | None
    ) -> tuple[list[InvoiceLineItemOut], str | None]:
        return await self._get_adapter().list_invoice_line_items(
            provider_invoice_id, limit=limit, cursor=cursor
        )

    # ---- Usage records list/get ----
    async def list_usage_records(
        self, f: UsageRecordListFilter
    ) -> tuple[list[UsageRecordOut], str | None]:
        return await self._get_adapter().list_usage_records(f)

    async def get_usage_record(self, usage_record_id: str) -> UsageRecordOut:
        return await self._get_adapter().get_usage_record(usage_record_id)
