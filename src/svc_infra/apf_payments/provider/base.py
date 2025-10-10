from __future__ import annotations

from typing import Any, Optional, Protocol

from ..schemas import (
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
    SubscriptionCreateIn,
    SubscriptionOut,
    SubscriptionUpdateIn,
)


class ProviderAdapter(Protocol):
    name: str

    # Customers
    async def ensure_customer(self, data: CustomerUpsertIn) -> CustomerOut:
        pass

    async def get_customer(self, provider_customer_id: str) -> Optional[CustomerOut]:
        pass

    # Payment Methods
    async def attach_payment_method(self, data: PaymentMethodAttachIn) -> PaymentMethodOut:
        pass

    async def list_payment_methods(self, provider_customer_id: str) -> list[PaymentMethodOut]:
        pass

    async def detach_payment_method(self, provider_method_id: str) -> None:
        pass

    async def set_default_payment_method(
        self, provider_customer_id: str, provider_method_id: str
    ) -> None:
        pass

    # Products / Prices
    async def create_product(self, data: ProductCreateIn) -> ProductOut:
        pass

    async def create_price(self, data: PriceCreateIn) -> PriceOut:
        pass

    # Subscriptions
    async def create_subscription(self, data: SubscriptionCreateIn) -> SubscriptionOut:
        pass

    async def update_subscription(
        self, provider_subscription_id: str, data: SubscriptionUpdateIn
    ) -> SubscriptionOut:
        pass

    async def cancel_subscription(
        self, provider_subscription_id: str, at_period_end: bool = True
    ) -> SubscriptionOut:
        pass

    # Invoices
    async def create_invoice(self, data: InvoiceCreateIn) -> InvoiceOut:
        pass

    async def finalize_invoice(self, provider_invoice_id: str) -> InvoiceOut:
        pass

    async def void_invoice(self, provider_invoice_id: str) -> InvoiceOut:
        pass

    async def pay_invoice(self, provider_invoice_id: str) -> InvoiceOut:
        pass

    # Intents
    async def create_intent(self, data: IntentCreateIn, *, user_id: str | None) -> IntentOut:
        pass

    async def confirm_intent(self, provider_intent_id: str) -> IntentOut:
        pass

    async def cancel_intent(self, provider_intent_id: str) -> IntentOut:
        pass

    async def refund(self, provider_intent_id: str, data: RefundIn) -> IntentOut:
        pass

    async def hydrate_intent(self, provider_intent_id: str) -> IntentOut:
        pass

    # Webhooks
    async def verify_and_parse_webhook(
        self, signature: str | None, payload: bytes
    ) -> dict[str, Any]:
        pass
