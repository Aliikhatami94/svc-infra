from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import LedgerEntry, PayCustomer, PayEvent, PayIntent
from .provider.registry import get_provider_registry
from .schemas import CustomerOut, CustomerUpsertIn, IntentCreateIn, IntentOut, RefundIn


class PaymentsService:
    def __init__(self, session: AsyncSession, provider_name: Optional[str] = None):
        self.session = session
        self.adapter = get_provider_registry().get(provider_name)

    # Customers
    async def ensure_customer(self, data: CustomerUpsertIn) -> CustomerOut:
        out = await self.adapter.ensure_customer(data)
        # upsert local row
        existing = await self.session.scalar(
            select(PayCustomer).where(
                PayCustomer.provider == "stripe",
                PayCustomer.provider_customer_id == out.provider_customer_id,
            )
        )
        if not existing:
            self.session.add(
                PayCustomer(
                    provider=out.provider,
                    provider_customer_id=out.provider_customer_id,
                    user_id=data.user_id,
                    email=out.email,
                    name=out.name,
                )
            )
        return out

    # Intents
    async def create_intent(self, user_id: Optional[str], data: IntentCreateIn) -> IntentOut:
        out = await self.adapter.create_intent(data, user_id=user_id)
        self.session.add(
            PayIntent(
                provider=out.provider,
                provider_intent_id=out.provider_intent_id,
                user_id=user_id,
                amount=out.amount,
                currency=out.currency,
                status=out.status,
                client_secret=out.client_secret,
                description=data.description,
            )
        )
        # minimal ledger entry (Receivable vs Sales): we’ll post on succeed webhooks; for draft we skip
        return out

    async def confirm_intent(self, provider_intent_id: str) -> IntentOut:
        out = await self.adapter.confirm_intent(provider_intent_id)
        pi = await self.session.scalar(
            select(PayIntent).where(PayIntent.provider_intent_id == provider_intent_id)
        )
        if pi:
            pi.status = out.status
            pi.client_secret = out.client_secret or pi.client_secret
        return out

    async def cancel_intent(self, provider_intent_id: str) -> IntentOut:
        out = await self.adapter.cancel_intent(provider_intent_id)
        pi = await self.session.scalar(
            select(PayIntent).where(PayIntent.provider_intent_id == provider_intent_id)
        )
        if pi:
            pi.status = out.status
        return out

    async def refund(self, provider_intent_id: str, data: RefundIn) -> IntentOut:
        out = await self.adapter.refund(provider_intent_id, data)
        # ledger impact will be handled when webhook finalizes
        return out

    # Webhook handling (verify + persist + ledger postings)
    async def handle_webhook(self, provider: str, signature: str | None, payload: bytes) -> dict:
        parsed = await self.adapter.verify_and_parse_webhook(signature, payload)
        # save raw event (dedupe upstream if unique constraint fails)
        self.session.add(
            PayEvent(
                provider=provider,
                provider_event_id=parsed["id"],
                signature_valid=True,
                payload=parsed,
            )
        )

        typ = parsed.get("type", "")
        obj = parsed.get("data") or {}
        # handle a few core lifecycle events for sales/receivables
        if provider == "stripe":
            if typ == "payment_intent.succeeded":
                await self._post_sale(obj)
            elif typ == "charge.refunded":
                await self._post_refund(obj)
            elif typ == "charge.captured":
                await self._post_capture(obj)
            # fees & payouts handled via balance transactions (future)

        return {"ok": True}

    async def _post_sale(self, pi_obj: dict):
        # Sales (credit), Receivable (debit)
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
                    account="Receivable",
                    amount=+amount,
                    currency=currency,
                    intent_id=intent.id,
                    provider=intent.provider,
                    provider_ref=provider_intent_id,
                    user_id=intent.user_id,
                )
            )
            self.session.add(
                LedgerEntry(
                    account="Sales",
                    amount=-amount,
                    currency=currency,
                    intent_id=intent.id,
                    provider=intent.provider,
                    provider_ref=provider_intent_id,
                    user_id=intent.user_id,
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
            # Cash debit, Receivable credit
            self.session.add(
                LedgerEntry(
                    account="Cash",
                    amount=+amount,
                    currency=currency,
                    intent_id=intent.id,
                    provider=intent.provider,
                    provider_ref=charge_obj.get("id"),
                    user_id=intent.user_id,
                )
            )
            self.session.add(
                LedgerEntry(
                    account="Receivable",
                    amount=-amount,
                    currency=currency,
                    intent_id=intent.id,
                    provider=intent.provider,
                    provider_ref=pi_id,
                    user_id=intent.user_id,
                )
            )

    async def _post_refund(self, charge_obj: dict):
        amount = int(charge_obj.get("amount_refunded") or 0)
        currency = str(charge_obj.get("currency") or "USD").upper()
        pi_id = charge_obj.get("payment_intent") or ""
        intent = await self.session.scalar(
            select(PayIntent).where(PayIntent.provider_intent_id == pi_id)
        )
        if intent and amount > 0:
            # Refunds (debit), Cash (credit)
            self.session.add(
                LedgerEntry(
                    account="Refunds",
                    amount=+amount,
                    currency=currency,
                    intent_id=intent.id,
                    provider=intent.provider,
                    provider_ref=charge_obj.get("id"),
                    user_id=intent.user_id,
                )
            )
            self.session.add(
                LedgerEntry(
                    account="Cash",
                    amount=-amount,
                    currency=currency,
                    intent_id=intent.id,
                    provider=intent.provider,
                    provider_ref=charge_obj.get("id"),
                    user_id=intent.user_id,
                )
            )
