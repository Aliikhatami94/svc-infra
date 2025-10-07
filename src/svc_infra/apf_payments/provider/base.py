from __future__ import annotations

from typing import Any, Optional, Protocol

from ..schemas import CustomerOut, CustomerUpsertIn, IntentCreateIn, IntentOut, RefundIn


class ProviderAdapter(Protocol):
    name: str  # "stripe", "adyen", "paypal", ...

    # Customers
    async def ensure_customer(self, data: CustomerUpsertIn) -> CustomerOut:
        pass

    async def get_customer(self, provider_customer_id: str) -> Optional[CustomerOut]:
        pass

    # Payment intents / orders
    async def create_intent(self, data: IntentCreateIn, *, user_id: str | None) -> IntentOut:
        pass

    async def confirm_intent(self, provider_intent_id: str) -> IntentOut:
        pass

    async def cancel_intent(self, provider_intent_id: str) -> IntentOut:
        pass

    async def refund(self, provider_intent_id: str, data: RefundIn) -> IntentOut:
        pass

    # Webhooks
    async def verify_and_parse_webhook(
        self, signature: str | None, payload: bytes
    ) -> dict[str, Any]:
        pass

    async def hydrate_intent(self, provider_intent_id: str) -> IntentOut:
        pass
