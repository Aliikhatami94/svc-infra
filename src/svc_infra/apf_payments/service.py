from __future__ import annotations

import os
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import LedgerEntry, PayCustomer, PayEvent, PayIntent
from .provider.registry import get_provider_registry
from .schemas import CustomerOut, CustomerUpsertIn, IntentCreateIn, IntentOut, RefundIn


def _default_provider_name() -> str:
    return (os.getenv("APF_PAYMENTS_PROVIDER") or "stripe").lower()


class PaymentsService:

    def __init__(self, session: AsyncSession, provider_name: Optional[str] = None):
        self.session = session
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
        return out

    # --- Webhooks -------------------------------------------------------------

    async def handle_webhook(self, provider: str, signature: str | None, payload: bytes) -> dict:
        # Webhooks also require provider adapter
        adapter = self._get_adapter()
        parsed = await adapter.verify_and_parse_webhook(signature, payload)

        # Save raw event (keep JSON column/shape aligned with your model)
        self.session.add(
            PayEvent(
                provider=provider,
                provider_event_id=parsed["id"],
                payload_json=parsed,  # or serialize before assign if your column is Text
            )
        )

        typ = parsed.get("type", "")
        obj = parsed.get("data") or {}

        if provider == "stripe":
            if typ == "payment_intent.succeeded":
                await self._post_sale(obj)
            elif typ == "charge.refunded":
                await self._post_refund(obj)
            elif typ == "charge.captured":
                await self._post_capture(obj)

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
            self.session.add(
                LedgerEntry(
                    provider=intent.provider,
                    provider_ref=charge_obj.get("id"),
                    user_id=intent.user_id,
                    amount=+amount,
                    currency=currency,
                    kind="capture",
                    status="posted",
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
            self.session.add(
                LedgerEntry(
                    provider=intent.provider,
                    provider_ref=charge_obj.get("id"),
                    user_id=intent.user_id,
                    amount=+amount,
                    currency=currency,
                    kind="refund",
                    status="posted",
                )
            )
