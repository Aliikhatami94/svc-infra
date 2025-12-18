from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints

# Type aliases for payment fields using Annotated with proper type hints
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
AmountMinor = Annotated[int, Field(ge=0)]  # minor units (cents)


class CustomerUpsertIn(BaseModel):
    user_id: str | None = None
    email: str | None = None
    name: str | None = None


class CustomerOut(BaseModel):
    id: str
    provider: str
    provider_customer_id: str
    email: str | None = None
    name: str | None = None


class IntentCreateIn(BaseModel):
    amount: AmountMinor = Field(..., description="Minor units (e.g., cents)")
    currency: Currency = Field(..., json_schema_extra={"example": "USD"})
    description: str | None = None
    capture_method: Literal["automatic", "manual"] = "automatic"
    payment_method_types: list[str] = Field(default_factory=list)  # let provider default


class NextAction(BaseModel):
    type: str | None = None
    data: dict[str, Any] | None = None


class IntentOut(BaseModel):
    id: str
    provider: str
    provider_intent_id: str
    status: str
    amount: AmountMinor
    currency: Currency
    client_secret: str | None = None
    next_action: NextAction | None = None


class RefundIn(BaseModel):
    amount: AmountMinor | None = None
    reason: str | None = None


class TransactionRow(BaseModel):
    id: str
    ts: str
    type: Literal["payment", "refund", "fee", "payout", "capture"]
    amount: int
    currency: Currency
    status: str
    provider: str
    provider_ref: str
    user_id: str | None = None
    net: int | None = None
    fee: int | None = None


class StatementRow(BaseModel):
    period_start: str
    period_end: str
    currency: Currency
    gross: int
    refunds: int
    fees: int
    net: int
    count: int


class PaymentMethodAttachIn(BaseModel):
    customer_provider_id: str
    payment_method_token: str  # provider token (e.g., stripe pm_ or payment_method id)
    make_default: bool = True


class PaymentMethodOut(BaseModel):
    id: str
    provider: str
    provider_customer_id: str
    provider_method_id: str
    brand: str | None = None
    last4: str | None = None
    exp_month: int | None = None
    exp_year: int | None = None
    is_default: bool = False


class ProductCreateIn(BaseModel):
    name: str
    active: bool = True


class ProductOut(BaseModel):
    id: str
    provider: str
    provider_product_id: str
    name: str
    active: bool


class PriceCreateIn(BaseModel):
    provider_product_id: str
    currency: Currency
    unit_amount: AmountMinor
    interval: Literal["day", "week", "month", "year"] | None = None
    trial_days: int | None = None
    active: bool = True


class PriceOut(BaseModel):
    id: str
    provider: str
    provider_price_id: str
    provider_product_id: str
    currency: Currency
    unit_amount: AmountMinor
    interval: str | None = None
    trial_days: int | None = None
    active: bool = True


class SubscriptionCreateIn(BaseModel):
    customer_provider_id: str
    price_provider_id: str
    quantity: int = 1
    trial_days: int | None = None
    proration_behavior: Literal["create_prorations", "none", "always_invoice"] = "create_prorations"


class SubscriptionUpdateIn(BaseModel):
    price_provider_id: str | None = None
    quantity: int | None = None
    cancel_at_period_end: bool | None = None
    proration_behavior: Literal["create_prorations", "none", "always_invoice"] = "create_prorations"


class SubscriptionOut(BaseModel):
    id: str
    provider: str
    provider_subscription_id: str
    provider_price_id: str
    status: str
    quantity: int
    cancel_at_period_end: bool
    current_period_end: str | None = None


class InvoiceCreateIn(BaseModel):
    customer_provider_id: str
    auto_advance: bool = True


class InvoiceOut(BaseModel):
    id: str
    provider: str
    provider_invoice_id: str
    provider_customer_id: str
    status: str
    amount_due: AmountMinor
    currency: Currency
    hosted_invoice_url: str | None = None
    pdf_url: str | None = None


class CaptureIn(BaseModel):
    amount: AmountMinor | None = None  # partial capture supported


class IntentListFilter(BaseModel):
    customer_provider_id: str | None = None
    status: str | None = None
    limit: int | None = Field(default=50, ge=1, le=200)
    cursor: str | None = None  # opaque provider cursor when supported


class UsageRecordIn(BaseModel):
    # Stripe: subscription_item is the target for metered billing.
    # If provider doesn't use subscription_item, allow provider_price_id as fallback.
    subscription_item: str | None = None
    provider_price_id: str | None = None
    quantity: Annotated[int, Field(ge=0)]
    timestamp: int | None = None  # Unix seconds; provider defaults to "now"
    action: Literal["increment", "set"] | None = "increment"


class InvoiceLineItemIn(BaseModel):
    customer_provider_id: str
    description: str | None = None
    unit_amount: AmountMinor
    currency: Currency
    quantity: int | None = 1
    provider_price_id: str | None = None  # if linked to a price, unit_amount may be ignored


class InvoicesListFilter(BaseModel):
    customer_provider_id: str | None = None
    status: str | None = None
    limit: int | None = Field(default=50, ge=1, le=200)
    cursor: str | None = None


class SetupIntentOut(BaseModel):
    id: str
    provider: str
    provider_setup_intent_id: str
    status: str
    client_secret: str | None = None
    next_action: NextAction | None = None


class DisputeOut(BaseModel):
    id: str
    provider: str
    provider_dispute_id: str
    amount: AmountMinor
    currency: Currency
    reason: str | None = None
    status: str
    evidence_due_by: str | None = None
    created_at: str | None = None


class PayoutOut(BaseModel):
    id: str
    provider: str
    provider_payout_id: str
    amount: AmountMinor
    currency: Currency
    status: str
    arrival_date: str | None = None
    type: str | None = None


class BalanceAmount(BaseModel):
    currency: Currency
    amount: AmountMinor


class BalanceSnapshotOut(BaseModel):
    available: list[BalanceAmount] = Field(default_factory=list)
    pending: list[BalanceAmount] = Field(default_factory=list)


class SetupIntentCreateIn(BaseModel):
    payment_method_types: list[str] = Field(default_factory=lambda: ["card"])


class WebhookReplayIn(BaseModel):
    event_ids: list[str] | None = None


class WebhookReplayOut(BaseModel):
    replayed: int


class WebhookAckOut(BaseModel):
    ok: bool


class UsageRecordOut(BaseModel):
    id: str
    quantity: int
    timestamp: int | None = None
    subscription_item: str | None = None
    provider_price_id: str | None = None
    action: Literal["increment", "set"] | None = None


# -------- Customers list filter ----------
class CustomersListFilter(BaseModel):
    provider: str | None = None
    user_id: str | None = None
    limit: int | None = Field(default=50, ge=1, le=200)
    cursor: str | None = None  # we’ll paginate on provider_customer_id asc


# -------- Products / Prices updates ----------
class ProductUpdateIn(BaseModel):
    name: str | None = None
    active: bool | None = None


class PriceUpdateIn(BaseModel):
    active: bool | None = None


# -------- Payment Method update ----------
class PaymentMethodUpdateIn(BaseModel):
    # keep minimal + commonly supported card fields
    name: str | None = None
    exp_month: int | None = None
    exp_year: int | None = None
    # extend here later with address fields (line1, city, etc.)


# -------- Refunds (list/get) ----------
class RefundOut(BaseModel):
    id: str
    provider: str
    provider_refund_id: str
    provider_payment_intent_id: str | None = None
    amount: AmountMinor
    currency: Currency
    status: str
    reason: str | None = None
    created_at: str | None = None


# -------- Invoice line items (list) ----------
class InvoiceLineItemOut(BaseModel):
    id: str
    description: str | None = None
    amount: AmountMinor
    currency: Currency
    quantity: int | None = 1
    provider_price_id: str | None = None


# -------- Usage records list/get ----------
class UsageRecordListFilter(BaseModel):
    subscription_item: str | None = None
    provider_price_id: str | None = None
    limit: int | None = Field(default=50, ge=1, le=200)
    cursor: str | None = None
