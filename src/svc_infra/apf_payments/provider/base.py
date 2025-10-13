from __future__ import annotations

from typing import Any, Optional, Protocol

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


class ProviderAdapter(Protocol):
    name: str

    async def ensure_customer(self, data: CustomerUpsertIn) -> CustomerOut:
        pass

    async def attach_payment_method(self, data: PaymentMethodAttachIn) -> PaymentMethodOut:
        pass

    async def list_payment_methods(self, provider_customer_id: str) -> list[PaymentMethodOut]:
        pass

    async def detach_payment_method(self, provider_method_id: str) -> PaymentMethodOut:
        pass

    async def set_default_payment_method(
        self, provider_customer_id: str, provider_method_id: str
    ) -> PaymentMethodOut:
        pass

    async def create_product(self, data: ProductCreateIn) -> ProductOut:
        pass

    async def create_price(self, data: PriceCreateIn) -> PriceOut:
        pass

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

    async def create_invoice(self, data: InvoiceCreateIn) -> InvoiceOut:
        pass

    async def finalize_invoice(self, provider_invoice_id: str) -> InvoiceOut:
        pass

    async def void_invoice(self, provider_invoice_id: str) -> InvoiceOut:
        pass

    async def pay_invoice(self, provider_invoice_id: str) -> InvoiceOut:
        pass

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

    async def verify_and_parse_webhook(
        self, signature: str | None, payload: bytes
    ) -> dict[str, Any]:
        pass

    async def capture_intent(self, provider_intent_id: str, *, amount: int | None) -> IntentOut:
        pass

    async def list_intents(
        self,
        *,
        customer_provider_id: str | None,
        status: str | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[IntentOut], str | None]:
        pass

    async def add_invoice_line_item(
        self, provider_invoice_id: str, data: InvoiceLineItemIn
    ) -> InvoiceOut:
        pass

    async def list_invoices(
        self,
        *,
        customer_provider_id: str | None,
        status: str | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[InvoiceOut], str | None]:
        pass

    async def get_invoice(self, provider_invoice_id: str) -> InvoiceOut:
        pass

    async def preview_invoice(
        self, *, customer_provider_id: str, subscription_id: str | None = None
    ) -> InvoiceOut:
        pass

    async def create_usage_record(self, data: UsageRecordIn) -> UsageRecordOut:
        pass

    # --- Setup Intents ---
    async def create_setup_intent(self, data: SetupIntentCreateIn) -> SetupIntentOut:
        pass

    async def confirm_setup_intent(self, provider_setup_intent_id: str) -> SetupIntentOut:
        pass

    async def get_setup_intent(self, provider_setup_intent_id: str) -> SetupIntentOut:
        pass

    # --- SCA / 3DS resume ---
    async def resume_intent_after_action(self, provider_intent_id: str) -> IntentOut:
        pass

    # --- Disputes ---
    async def list_disputes(
        self, *, status: str | None, limit: int, cursor: str | None
    ) -> tuple[list[DisputeOut], str | None]:
        pass

    async def get_dispute(self, provider_dispute_id: str) -> DisputeOut:
        pass

    async def submit_dispute_evidence(self, provider_dispute_id: str, evidence: dict) -> DisputeOut:
        pass

    # --- Balance & Payouts ---
    async def get_balance_snapshot(self) -> BalanceSnapshotOut:
        pass

    async def list_payouts(
        self, *, limit: int, cursor: str | None
    ) -> tuple[list[PayoutOut], str | None]:
        pass

    async def get_payout(self, provider_payout_id: str) -> PayoutOut:
        pass

    # --- Customers ---
    async def list_customers(
        self, *, provider: str | None, user_id: str | None, limit: int, cursor: str | None
    ) -> tuple[list[CustomerOut], str | None]:
        """Optional: if not implemented, the service will list from local DB."""
        pass

    async def get_customer(self, provider_customer_id: str) -> Optional[CustomerOut]:
        pass

    # --- Products / Prices ---
    async def get_product(self, provider_product_id: str) -> ProductOut:
        pass

    async def list_products(
        self, *, active: bool | None, limit: int, cursor: str | None
    ) -> tuple[list[ProductOut], str | None]:
        pass

    async def update_product(self, provider_product_id: str, data: ProductUpdateIn) -> ProductOut:
        pass

    async def get_price(self, provider_price_id: str) -> PriceOut:
        pass

    async def list_prices(
        self,
        *,
        provider_product_id: str | None,
        active: bool | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[PriceOut], str | None]:
        pass

    async def update_price(self, provider_price_id: str, data: PriceUpdateIn) -> PriceOut:
        pass

    # --- Subscriptions ---
    async def get_subscription(self, provider_subscription_id: str) -> SubscriptionOut:
        pass

    async def list_subscriptions(
        self,
        *,
        customer_provider_id: str | None,
        status: str | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[SubscriptionOut], str | None]:
        pass

    # --- Payment Method (single + update) ---
    async def get_payment_method(self, provider_method_id: str) -> PaymentMethodOut:
        pass

    async def update_payment_method(
        self, provider_method_id: str, data: PaymentMethodUpdateIn
    ) -> PaymentMethodOut:
        pass

    # --- Refunds list/get ---
    async def list_refunds(
        self, *, provider_payment_intent_id: str | None, limit: int, cursor: str | None
    ) -> tuple[list[RefundOut], str | None]:
        pass

    async def get_refund(self, provider_refund_id: str) -> RefundOut:
        pass

    # --- Invoice line items list ---
    async def list_invoice_line_items(
        self, provider_invoice_id: str, *, limit: int, cursor: str | None
    ) -> tuple[list[InvoiceLineItemOut], str | None]:
        pass

    # --- Usage records list/get ---
    async def list_usage_records(
        self, f: UsageRecordListFilter
    ) -> tuple[list[UsageRecordOut], str | None]:
        pass

    async def get_usage_record(self, usage_record_id: str) -> UsageRecordOut:
        pass
