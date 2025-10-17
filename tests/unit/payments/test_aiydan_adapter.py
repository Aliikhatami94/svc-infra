from __future__ import annotations

import pytest

from svc_infra.apf_payments.provider.aiydan import AiydanAdapter
from svc_infra.apf_payments.schemas import CustomerUpsertIn


@pytest.mark.asyncio
async def test_aiydan_adapter_customer_and_methods(mocker):
    client = mocker.Mock()
    client.ensure_customer = mocker.AsyncMock(
        return_value={
            "id": "cust_123",
            "email": "user@example.com",
            "name": "User",
        }
    )
    client.list_payment_methods = mocker.AsyncMock(
        return_value=[
            {
                "id": "pm_1",
                "customer_id": "cust_123",
                "card": {
                    "brand": "visa",
                    "last4": "4242",
                    "exp_month": 12,
                    "exp_year": 2030,
                },
                "is_default": True,
            }
        ]
    )

    adapter = AiydanAdapter(client=client)

    customer = await adapter.ensure_customer(CustomerUpsertIn(email="user@example.com"))
    assert customer.provider == "aiydan"
    assert customer.provider_customer_id == "cust_123"

    methods = await adapter.list_payment_methods("cust_123")
    assert len(methods) == 1
    assert methods[0].provider_method_id == "pm_1"
    assert methods[0].is_default is True


@pytest.mark.asyncio
async def test_aiydan_adapter_list_prices_with_cursor(mocker):
    client = mocker.Mock()
    client.list_prices = mocker.AsyncMock(
        return_value={
            "items": [
                {
                    "id": "price_basic",
                    "currency": "usd",
                    "unit_amount": 1500,
                    "product_id": "prod_basic",
                    "active": True,
                }
            ],
            "next_cursor": "cursor_2",
        }
    )

    adapter = AiydanAdapter(client=client)
    prices, cursor = await adapter.list_prices(
        provider_product_id=None,
        active=None,
        limit=20,
        cursor=None,
    )

    assert cursor == "cursor_2"
    assert prices[0].provider_price_id == "price_basic"
    assert prices[0].unit_amount == 1500


@pytest.mark.asyncio
async def test_aiydan_adapter_verify_webhook(mocker):
    client = mocker.Mock()
    client.verify_and_parse_webhook = mocker.AsyncMock(return_value={"ok": True})

    adapter = AiydanAdapter(client=client)

    result = await adapter.verify_and_parse_webhook("sig123", b"body")

    client.verify_and_parse_webhook.assert_awaited_once_with(
        signature="sig123",
        payload=b"body",
        secret=None,
    )
    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_aiydan_adapter_list_customers_none(mocker):
    client = mocker.Mock()
    client.list_customers = mocker.AsyncMock(
        return_value={
            "items": [
                {
                    "id": "cust_a",
                    "email": "a@example.com",
                }
            ],
            "next_cursor": "next",
        }
    )
    client.get_customer = mocker.AsyncMock(return_value=None)

    adapter = AiydanAdapter(client=client)

    customers, cursor = await adapter.list_customers(
        provider=None,
        user_id=None,
        limit=10,
        cursor=None,
    )
    assert cursor == "next"
    assert customers[0].provider_customer_id == "cust_a"

    assert await adapter.get_customer("missing") is None
