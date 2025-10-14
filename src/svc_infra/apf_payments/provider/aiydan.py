from __future__ import annotations

import inspect
from datetime import date, datetime, timezone
from typing import Any, Optional, Sequence, Tuple

from svc_infra.apf_payments.schemas import (
    BalanceAmount,
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
    NextAction,
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
from svc_infra.apf_payments.settings import get_payments_settings

from .base import ProviderAdapter

try:  # pragma: no cover - optional dependency
    import aiydan  # type: ignore
except Exception:  # pragma: no cover - handled at runtime
    aiydan = None  # type: ignore


async def _maybe_await(result: Any) -> Any:
    if inspect.isawaitable(result):
        return await result
    return result


def _coerce_id(data: dict[str, Any], *candidates: str) -> str:
    for key in candidates:
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    raise RuntimeError(f"Aiydan payload missing id fields: {candidates}")


def _ensure_utc_isoformat(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc).isoformat()
    try:
        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except Exception:
        return str(value)


def _customer_to_out(data: dict[str, Any]) -> CustomerOut:
    cust_id = _coerce_id(data, "provider_customer_id", "customer_id", "id")
    return CustomerOut(
        id=cust_id,
        provider="aiydan",
        provider_customer_id=cust_id,
        email=data.get("email"),
        name=data.get("name"),
    )


def _intent_to_out(data: dict[str, Any]) -> IntentOut:
    intent_id = _coerce_id(data, "provider_intent_id", "intent_id", "id")
    return IntentOut(
        id=intent_id,
        provider="aiydan",
        provider_intent_id=intent_id,
        status=str(data.get("status", "")),
        amount=int(data.get("amount", 0)),
        currency=str(data.get("currency", "")).upper(),
        client_secret=data.get("client_secret"),
        next_action=NextAction(type=(data.get("next_action") or {}).get("type")),
    )


def _payment_method_to_out(data: dict[str, Any]) -> PaymentMethodOut:
    method_id = _coerce_id(data, "provider_method_id", "payment_method_id", "id")
    card = data.get("card") or {}
    return PaymentMethodOut(
        id=method_id,
        provider="aiydan",
        provider_customer_id=str(data.get("provider_customer_id") or data.get("customer_id") or ""),
        provider_method_id=method_id,
        brand=card.get("brand") or data.get("brand"),
        last4=card.get("last4") or data.get("last4"),
        exp_month=card.get("exp_month") or data.get("exp_month"),
        exp_year=card.get("exp_year") or data.get("exp_year"),
        is_default=bool(data.get("is_default")),
    )


def _product_to_out(data: dict[str, Any]) -> ProductOut:
    product_id = _coerce_id(data, "provider_product_id", "product_id", "id")
    return ProductOut(
        id=product_id,
        provider="aiydan",
        provider_product_id=product_id,
        name=str(data.get("name", "")),
        active=bool(data.get("active", True)),
    )


def _price_to_out(data: dict[str, Any]) -> PriceOut:
    price_id = _coerce_id(data, "provider_price_id", "price_id", "id")
    recurring = data.get("recurring") or {}
    return PriceOut(
        id=price_id,
        provider="aiydan",
        provider_price_id=price_id,
        provider_product_id=str(
            data.get("provider_product_id")
            or data.get("product_id")
            or getattr(data.get("product"), "id", "")
        ),
        currency=str(data.get("currency", "")).upper(),
        unit_amount=int(data.get("unit_amount", data.get("amount", 0) or 0)),
        interval=str(recurring.get("interval")) if recurring.get("interval") else None,
        trial_days=data.get("trial_days"),
        active=bool(data.get("active", True)),
    )


def _subscription_to_out(data: dict[str, Any]) -> SubscriptionOut:
    sub_id = _coerce_id(data, "provider_subscription_id", "subscription_id", "id")
    items = data.get("items") or {}
    first_item = None
    if isinstance(items, dict):
        first_item = (items.get("data") or [None])[0]
    elif isinstance(items, Sequence):
        first_item = items[0] if items else None
    price_id = (
        first_item.get("price")
        if isinstance(first_item, dict)
        else getattr(first_item, "price", None)
    )
    if isinstance(price_id, dict):
        price_id = price_id.get("id")
    elif price_id is not None and not isinstance(price_id, str):
        price_id = getattr(price_id, "id", None)
    quantity = (
        first_item.get("quantity")
        if isinstance(first_item, dict)
        else getattr(first_item, "quantity", 0)
    )
    return SubscriptionOut(
        id=sub_id,
        provider="aiydan",
        provider_subscription_id=sub_id,
        provider_price_id=price_id or "",
        status=str(data.get("status", "")),
        quantity=int(quantity or 0),
        cancel_at_period_end=bool(data.get("cancel_at_period_end", False)),
        current_period_end=_ensure_utc_isoformat(data.get("current_period_end")),
    )


def _invoice_to_out(data: dict[str, Any]) -> InvoiceOut:
    invoice_id = _coerce_id(data, "provider_invoice_id", "invoice_id", "id")
    return InvoiceOut(
        id=invoice_id,
        provider="aiydan",
        provider_invoice_id=invoice_id,
        provider_customer_id=str(data.get("provider_customer_id") or data.get("customer_id") or ""),
        status=str(data.get("status", "")),
        amount_due=int(data.get("amount_due", data.get("amount") or 0) or 0),
        currency=str(data.get("currency", "")).upper(),
        hosted_invoice_url=data.get("hosted_invoice_url") or data.get("hosted_url"),
        pdf_url=data.get("pdf_url") or data.get("invoice_pdf"),
    )


def _invoice_line_item_to_out(data: dict[str, Any]) -> InvoiceLineItemOut:
    line_id = _coerce_id(data, "provider_invoice_line_item_id", "line_id", "id")
    price = data.get("price") or {}
    if not isinstance(price, dict):
        price = {"id": getattr(price, "id", None)}
    return InvoiceLineItemOut(
        id=line_id,
        description=data.get("description"),
        currency=str(data.get("currency", price.get("currency", ""))).upper(),
        quantity=int(data.get("quantity", 0) or 0),
        unit_amount=int(data.get("unit_amount", data.get("amount", 0) or 0)),
        provider_price_id=price.get("id"),
    )


def _refund_to_out(data: dict[str, Any]) -> RefundOut:
    refund_id = _coerce_id(data, "provider_refund_id", "refund_id", "id")
    return RefundOut(
        id=refund_id,
        provider="aiydan",
        provider_refund_id=refund_id,
        provider_payment_intent_id=str(
            data.get("provider_payment_intent_id") or data.get("payment_intent_id") or ""
        ),
        amount=int(data.get("amount", 0) or 0),
        currency=str(data.get("currency", "")).upper(),
        status=str(data.get("status", "")),
        reason=data.get("reason"),
        created_at=_ensure_utc_isoformat(data.get("created_at") or data.get("created")),
    )


def _dispute_to_out(data: dict[str, Any]) -> DisputeOut:
    dispute_id = _coerce_id(data, "provider_dispute_id", "dispute_id", "id")
    evidence = data.get("evidence") or {}
    return DisputeOut(
        id=dispute_id,
        provider="aiydan",
        provider_dispute_id=dispute_id,
        amount=int(data.get("amount", 0) or 0),
        currency=str(data.get("currency", "")).upper(),
        reason=data.get("reason"),
        status=str(data.get("status", "")),
        evidence_due_by=_ensure_utc_isoformat(
            evidence.get("due_by") or data.get("evidence_due_by")
        ),
        created_at=_ensure_utc_isoformat(data.get("created_at") or data.get("created")),
    )


def _payout_to_out(data: dict[str, Any]) -> PayoutOut:
    payout_id = _coerce_id(data, "provider_payout_id", "payout_id", "id")
    return PayoutOut(
        id=payout_id,
        provider="aiydan",
        provider_payout_id=payout_id,
        amount=int(data.get("amount", 0) or 0),
        currency=str(data.get("currency", "")).upper(),
        status=str(data.get("status", "")),
        arrival_date=_ensure_utc_isoformat(data.get("arrival_date")),
        type=data.get("type"),
    )


def _usage_record_to_out(data: dict[str, Any]) -> UsageRecordOut:
    return UsageRecordOut(
        id=str(data.get("id")),
        quantity=int(data.get("quantity", 0) or 0),
        timestamp=data.get("timestamp"),
        subscription_item=(
            str(data.get("subscription_item")) if data.get("subscription_item") else None
        ),
        provider_price_id=(
            str(data.get("provider_price_id")) if data.get("provider_price_id") else None
        ),
        action=(str(data.get("action")) if data.get("action") else None),
    )


def _balance_snapshot_to_out(data: dict[str, Any]) -> BalanceSnapshotOut:
    def _normalize(side: Any) -> list[dict[str, Any]]:
        if isinstance(side, list):
            out: list[dict[str, Any]] = []
            for item in side:
                if isinstance(item, dict) and "currency" in item and "amount" in item:
                    out.append(
                        {
                            "currency": str(item["currency"]).upper(),
                            "amount": int(item["amount"] or 0),
                        }
                    )
            return out
        if isinstance(side, dict):
            return [
                {"currency": str(cur).upper(), "amount": int(amt or 0)} for cur, amt in side.items()
            ]
        return []

    return BalanceSnapshotOut(
        available=[
            BalanceAmount(currency=i["currency"], amount=i["amount"])
            for i in _normalize(data.get("available"))
        ],
        pending=[
            BalanceAmount(currency=i["currency"], amount=i["amount"])
            for i in _normalize(data.get("pending"))
        ],
    )


def _ensure_sequence(result: Any) -> Sequence[dict[str, Any]]:
    if isinstance(result, Sequence):
        return result  # type: ignore[arg-type]
    if isinstance(result, dict):
        items = result.get("items")
        if isinstance(items, Sequence):
            return items  # type: ignore[arg-type]
    raise RuntimeError("Expected sequence payload from Aiydan client")


def _ensure_list_response(result: Any) -> Tuple[Sequence[dict[str, Any]], Optional[str]]:
    if isinstance(result, tuple) and len(result) == 2:
        items, cursor = result
        if isinstance(items, Sequence) or items is None:
            return (items or []), cursor  # type: ignore[arg-type]
    if isinstance(result, dict):
        items = result.get("items")
        cursor = result.get("next_cursor") or result.get("cursor")
        if isinstance(items, Sequence):
            return items, cursor
    if isinstance(result, Sequence):
        return result, None  # type: ignore[arg-type]
    raise RuntimeError("Expected iterable response from Aiydan client")


class AiydanAdapter(ProviderAdapter):
    name = "aiydan"

    def __init__(self, *, client: Optional[Any] = None):
        settings = get_payments_settings()
        cfg = settings.aiydan
        if client is not None:
            self._client = client
            self._webhook_secret = (
                cfg.webhook_secret.get_secret_value() if cfg and cfg.webhook_secret else None
            )
            return
        if cfg is None:
            raise RuntimeError("Aiydan settings not configured")
        if aiydan is None:
            raise RuntimeError("aiydan SDK is not installed. pip install aiydan")
        client_class = getattr(aiydan, "Client", None)
        if client_class is None:
            raise RuntimeError("aiydan SDK missing 'Client' class")
        kwargs: dict[str, Any] = {"api_key": cfg.api_key.get_secret_value()}
        if cfg.client_key:
            kwargs["client_key"] = cfg.client_key.get_secret_value()
        if cfg.merchant_account:
            kwargs["merchant_account"] = cfg.merchant_account
        if cfg.hmac_key:
            kwargs["hmac_key"] = cfg.hmac_key.get_secret_value()
        if cfg.base_url:
            kwargs["base_url"] = cfg.base_url
        self._client = client_class(**kwargs)
        self._webhook_secret = cfg.webhook_secret.get_secret_value() if cfg.webhook_secret else None

    async def ensure_customer(self, data: CustomerUpsertIn) -> CustomerOut:
        payload = data.model_dump(exclude_none=True)
        result = await _maybe_await(self._client.ensure_customer(payload))
        return _customer_to_out(result)

    async def attach_payment_method(self, data: PaymentMethodAttachIn) -> PaymentMethodOut:
        payload = data.model_dump(exclude_none=True)
        result = await _maybe_await(self._client.attach_payment_method(payload))
        return _payment_method_to_out(result)

    async def list_payment_methods(self, provider_customer_id: str) -> list[PaymentMethodOut]:
        result = await _maybe_await(self._client.list_payment_methods(provider_customer_id))
        methods = _ensure_sequence(result)
        return [_payment_method_to_out(method) for method in methods]

    async def detach_payment_method(self, provider_method_id: str) -> PaymentMethodOut:
        result = await _maybe_await(self._client.detach_payment_method(provider_method_id))
        return _payment_method_to_out(result)

    async def set_default_payment_method(
        self, provider_customer_id: str, provider_method_id: str
    ) -> PaymentMethodOut:
        result = await _maybe_await(
            self._client.set_default_payment_method(provider_customer_id, provider_method_id)
        )
        return _payment_method_to_out(result)

    async def get_payment_method(self, provider_method_id: str) -> PaymentMethodOut:
        result = await _maybe_await(self._client.get_payment_method(provider_method_id))
        return _payment_method_to_out(result)

    async def update_payment_method(
        self, provider_method_id: str, data: PaymentMethodUpdateIn
    ) -> PaymentMethodOut:
        payload = data.model_dump(exclude_none=True)
        result = await _maybe_await(self._client.update_payment_method(provider_method_id, payload))
        return _payment_method_to_out(result)

    async def create_product(self, data: ProductCreateIn) -> ProductOut:
        payload = data.model_dump(exclude_none=True)
        result = await _maybe_await(self._client.create_product(payload))
        return _product_to_out(result)

    async def get_product(self, provider_product_id: str) -> ProductOut:
        result = await _maybe_await(self._client.get_product(provider_product_id))
        return _product_to_out(result)

    async def list_products(
        self, *, active: bool | None, limit: int, cursor: str | None
    ) -> tuple[list[ProductOut], str | None]:
        result = await _maybe_await(
            self._client.list_products(active=active, limit=limit, cursor=cursor)
        )
        items, next_cursor = _ensure_list_response(result)
        return [_product_to_out(item) for item in items], next_cursor

    async def update_product(self, provider_product_id: str, data: ProductUpdateIn) -> ProductOut:
        payload = data.model_dump(exclude_none=True)
        result = await _maybe_await(self._client.update_product(provider_product_id, payload))
        return _product_to_out(result)

    async def create_price(self, data: PriceCreateIn) -> PriceOut:
        payload = data.model_dump(exclude_none=True)
        result = await _maybe_await(self._client.create_price(payload))
        return _price_to_out(result)

    async def get_price(self, provider_price_id: str) -> PriceOut:
        result = await _maybe_await(self._client.get_price(provider_price_id))
        return _price_to_out(result)

    async def list_prices(
        self,
        *,
        provider_product_id: str | None,
        active: bool | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[PriceOut], str | None]:
        result = await _maybe_await(
            self._client.list_prices(
                provider_product_id=provider_product_id,
                active=active,
                limit=limit,
                cursor=cursor,
            )
        )
        items, next_cursor = _ensure_list_response(result)
        return [_price_to_out(item) for item in items], next_cursor

    async def update_price(self, provider_price_id: str, data: PriceUpdateIn) -> PriceOut:
        payload = data.model_dump(exclude_none=True)
        result = await _maybe_await(self._client.update_price(provider_price_id, payload))
        return _price_to_out(result)

    async def create_subscription(self, data: SubscriptionCreateIn) -> SubscriptionOut:
        payload = data.model_dump(exclude_none=True)
        result = await _maybe_await(self._client.create_subscription(payload))
        return _subscription_to_out(result)

    async def update_subscription(
        self, provider_subscription_id: str, data: SubscriptionUpdateIn
    ) -> SubscriptionOut:
        payload = data.model_dump(exclude_none=True)
        result = await _maybe_await(
            self._client.update_subscription(provider_subscription_id, payload)
        )
        return _subscription_to_out(result)

    async def cancel_subscription(
        self, provider_subscription_id: str, at_period_end: bool = True
    ) -> SubscriptionOut:
        result = await _maybe_await(
            self._client.cancel_subscription(provider_subscription_id, at_period_end)
        )
        return _subscription_to_out(result)

    async def get_subscription(self, provider_subscription_id: str) -> SubscriptionOut:
        result = await _maybe_await(self._client.get_subscription(provider_subscription_id))
        return _subscription_to_out(result)

    async def list_subscriptions(
        self,
        *,
        customer_provider_id: str | None,
        status: str | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[SubscriptionOut], str | None]:
        result = await _maybe_await(
            self._client.list_subscriptions(
                customer_provider_id=customer_provider_id,
                status=status,
                limit=limit,
                cursor=cursor,
            )
        )
        items, next_cursor = _ensure_list_response(result)
        return [_subscription_to_out(item) for item in items], next_cursor

    async def create_invoice(self, data: InvoiceCreateIn) -> InvoiceOut:
        payload = data.model_dump(exclude_none=True)
        result = await _maybe_await(self._client.create_invoice(payload))
        return _invoice_to_out(result)

    async def finalize_invoice(self, provider_invoice_id: str) -> InvoiceOut:
        result = await _maybe_await(self._client.finalize_invoice(provider_invoice_id))
        return _invoice_to_out(result)

    async def void_invoice(self, provider_invoice_id: str) -> InvoiceOut:
        result = await _maybe_await(self._client.void_invoice(provider_invoice_id))
        return _invoice_to_out(result)

    async def pay_invoice(self, provider_invoice_id: str) -> InvoiceOut:
        result = await _maybe_await(self._client.pay_invoice(provider_invoice_id))
        return _invoice_to_out(result)

    async def add_invoice_line_item(
        self, provider_invoice_id: str, data: InvoiceLineItemIn
    ) -> InvoiceOut:
        payload = data.model_dump(exclude_none=True)
        result = await _maybe_await(
            self._client.add_invoice_line_item(provider_invoice_id, payload)
        )
        return _invoice_to_out(result)

    async def list_invoices(
        self,
        *,
        customer_provider_id: str | None,
        status: str | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[InvoiceOut], str | None]:
        result = await _maybe_await(
            self._client.list_invoices(
                customer_provider_id=customer_provider_id,
                status=status,
                limit=limit,
                cursor=cursor,
            )
        )
        items, next_cursor = _ensure_list_response(result)
        return [_invoice_to_out(item) for item in items], next_cursor

    async def get_invoice(self, provider_invoice_id: str) -> InvoiceOut:
        result = await _maybe_await(self._client.get_invoice(provider_invoice_id))
        return _invoice_to_out(result)

    async def preview_invoice(
        self, *, customer_provider_id: str, subscription_id: str | None = None
    ) -> InvoiceOut:
        result = await _maybe_await(
            self._client.preview_invoice(
                customer_provider_id=customer_provider_id,
                subscription_id=subscription_id,
            )
        )
        return _invoice_to_out(result)

    async def list_invoice_line_items(
        self, provider_invoice_id: str, *, limit: int, cursor: str | None
    ) -> tuple[list[InvoiceLineItemOut], str | None]:
        result = await _maybe_await(
            self._client.list_invoice_line_items(
                provider_invoice_id,
                limit=limit,
                cursor=cursor,
            )
        )
        items, next_cursor = _ensure_list_response(result)
        return [_invoice_line_item_to_out(item) for item in items], next_cursor

    async def create_intent(self, data: IntentCreateIn, *, user_id: str | None) -> IntentOut:
        payload = data.model_dump(exclude_none=True)
        if user_id is not None:
            payload["user_id"] = user_id
        result = await _maybe_await(self._client.create_intent(payload))
        return _intent_to_out(result)

    async def confirm_intent(self, provider_intent_id: str) -> IntentOut:
        result = await _maybe_await(self._client.confirm_intent(provider_intent_id))
        return _intent_to_out(result)

    async def cancel_intent(self, provider_intent_id: str) -> IntentOut:
        result = await _maybe_await(self._client.cancel_intent(provider_intent_id))
        return _intent_to_out(result)

    async def refund(self, provider_intent_id: str, data: RefundIn) -> IntentOut:
        payload = data.model_dump(exclude_none=True)
        result = await _maybe_await(self._client.refund_intent(provider_intent_id, payload))
        return _intent_to_out(result)

    async def hydrate_intent(self, provider_intent_id: str) -> IntentOut:
        result = await _maybe_await(self._client.get_intent(provider_intent_id))
        return _intent_to_out(result)

    async def capture_intent(self, provider_intent_id: str, *, amount: int | None) -> IntentOut:
        result = await _maybe_await(self._client.capture_intent(provider_intent_id, amount=amount))
        return _intent_to_out(result)

    async def list_intents(
        self,
        *,
        customer_provider_id: str | None,
        status: str | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[IntentOut], str | None]:
        result = await _maybe_await(
            self._client.list_intents(
                customer_provider_id=customer_provider_id,
                status=status,
                limit=limit,
                cursor=cursor,
            )
        )
        items, next_cursor = _ensure_list_response(result)
        return [_intent_to_out(item) for item in items], next_cursor

    async def verify_and_parse_webhook(
        self, signature: str | None, payload: bytes
    ) -> dict[str, Any]:
        if hasattr(self._client, "verify_and_parse_webhook"):
            result = await _maybe_await(
                self._client.verify_and_parse_webhook(
                    signature=signature,
                    payload=payload,
                    secret=self._webhook_secret,
                )
            )
        elif hasattr(self._client, "verify_webhook"):
            result = await _maybe_await(
                self._client.verify_webhook(
                    payload=payload,
                    signature=signature,
                    secret=self._webhook_secret,
                )
            )
        else:
            raise RuntimeError("Aiydan client missing webhook verification method")
        if not isinstance(result, dict):
            raise RuntimeError("Aiydan client returned unexpected webhook payload")
        return result

    async def list_disputes(
        self, *, status: str | None, limit: int, cursor: str | None
    ) -> tuple[list[DisputeOut], str | None]:
        result = await _maybe_await(
            self._client.list_disputes(status=status, limit=limit, cursor=cursor)
        )
        items, next_cursor = _ensure_list_response(result)
        return [_dispute_to_out(item) for item in items], next_cursor

    async def get_dispute(self, provider_dispute_id: str) -> DisputeOut:
        result = await _maybe_await(self._client.get_dispute(provider_dispute_id))
        return _dispute_to_out(result)

    async def submit_dispute_evidence(self, provider_dispute_id: str, evidence: dict) -> DisputeOut:
        result = await _maybe_await(
            self._client.submit_dispute_evidence(provider_dispute_id, evidence)
        )
        return _dispute_to_out(result)

    async def get_balance_snapshot(self) -> BalanceSnapshotOut:
        result = await _maybe_await(self._client.get_balance_snapshot())
        if isinstance(result, BalanceSnapshotOut):
            return result
        if not isinstance(result, dict):
            raise RuntimeError("Aiydan client returned unexpected balance payload")
        return _balance_snapshot_to_out(result)

    async def list_payouts(
        self, *, limit: int, cursor: str | None
    ) -> tuple[list[PayoutOut], str | None]:
        result = await _maybe_await(self._client.list_payouts(limit=limit, cursor=cursor))
        items, next_cursor = _ensure_list_response(result)
        return [_payout_to_out(item) for item in items], next_cursor

    async def get_payout(self, provider_payout_id: str) -> PayoutOut:
        result = await _maybe_await(self._client.get_payout(provider_payout_id))
        return _payout_to_out(result)

    async def list_refunds(
        self,
        *,
        provider_payment_intent_id: str | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[RefundOut], str | None]:
        result = await _maybe_await(
            self._client.list_refunds(
                provider_payment_intent_id=provider_payment_intent_id,
                limit=limit,
                cursor=cursor,
            )
        )
        items, next_cursor = _ensure_list_response(result)
        return [_refund_to_out(item) for item in items], next_cursor

    async def get_refund(self, provider_refund_id: str) -> RefundOut:
        result = await _maybe_await(self._client.get_refund(provider_refund_id))
        return _refund_to_out(result)

    async def create_usage_record(self, data: UsageRecordIn) -> UsageRecordOut:
        payload = data.model_dump(exclude_none=True)
        result = await _maybe_await(self._client.create_usage_record(payload))
        return _usage_record_to_out(result)

    async def list_usage_records(
        self, f: UsageRecordListFilter
    ) -> tuple[list[UsageRecordOut], str | None]:
        payload = f.model_dump(exclude_none=True)
        result = await _maybe_await(self._client.list_usage_records(payload))
        items, next_cursor = _ensure_list_response(result)
        return [_usage_record_to_out(item) for item in items], next_cursor

    async def get_usage_record(self, usage_record_id: str) -> UsageRecordOut:
        result = await _maybe_await(self._client.get_usage_record(usage_record_id))
        return _usage_record_to_out(result)

    async def create_setup_intent(self, data: SetupIntentCreateIn) -> SetupIntentOut:
        payload = data.model_dump(exclude_none=True)
        result = await _maybe_await(self._client.create_setup_intent(payload))
        return SetupIntentOut(
            id=_coerce_id(result, "provider_setup_intent_id", "setup_intent_id", "id"),
            provider="aiydan",
            provider_setup_intent_id=_coerce_id(
                result, "provider_setup_intent_id", "setup_intent_id", "id"
            ),
            status=str(result.get("status", "")),
            client_secret=result.get("client_secret"),
            next_action=NextAction(type=(result.get("next_action") or {}).get("type")),
        )

    async def confirm_setup_intent(self, provider_setup_intent_id: str) -> SetupIntentOut:
        result = await _maybe_await(self._client.confirm_setup_intent(provider_setup_intent_id))
        return SetupIntentOut(
            id=_coerce_id(result, "provider_setup_intent_id", "setup_intent_id", "id"),
            provider="aiydan",
            provider_setup_intent_id=_coerce_id(
                result, "provider_setup_intent_id", "setup_intent_id", "id"
            ),
            status=str(result.get("status", "")),
            client_secret=result.get("client_secret"),
            next_action=NextAction(type=(result.get("next_action") or {}).get("type")),
        )

    async def get_setup_intent(self, provider_setup_intent_id: str) -> SetupIntentOut:
        result = await _maybe_await(self._client.get_setup_intent(provider_setup_intent_id))
        return SetupIntentOut(
            id=_coerce_id(result, "provider_setup_intent_id", "setup_intent_id", "id"),
            provider="aiydan",
            provider_setup_intent_id=_coerce_id(
                result, "provider_setup_intent_id", "setup_intent_id", "id"
            ),
            status=str(result.get("status", "")),
            client_secret=result.get("client_secret"),
            next_action=NextAction(type=(result.get("next_action") or {}).get("type")),
        )

    async def resume_intent_after_action(self, provider_intent_id: str) -> IntentOut:
        if hasattr(self._client, "resume_intent_after_action"):
            result = await _maybe_await(self._client.resume_intent_after_action(provider_intent_id))
        else:
            result = await _maybe_await(self._client.get_intent(provider_intent_id))
        return _intent_to_out(result)

    async def list_customers(
        self, *, provider: str | None, user_id: str | None, limit: int, cursor: str | None
    ) -> tuple[list[CustomerOut], str | None]:
        result = await _maybe_await(
            self._client.list_customers(
                provider=provider,
                user_id=user_id,
                limit=limit,
                cursor=cursor,
            )
        )
        items, next_cursor = _ensure_list_response(result)
        return [_customer_to_out(item) for item in items], next_cursor

    async def get_customer(self, provider_customer_id: str) -> Optional[CustomerOut]:
        result = await _maybe_await(self._client.get_customer(provider_customer_id))
        if result is None:
            return None
        return _customer_to_out(result)
