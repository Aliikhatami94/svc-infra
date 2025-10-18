import pytest


@pytest.mark.asyncio
async def test_methods_pagination_limit_and_cursor(client, fake_adapter, mocker):
    # Create 3 methods to validate windowing
    methods = [
        mocker.Mock(
            id=f"pm_{i}",
            provider="stripe",
            provider_customer_id="cus_1",
            provider_method_id=f"pm_{i}",
            brand="visa",
            last4="4242",
            is_default=(i == 0),
            exp_month=12,
            exp_year=2025,
        )
        for i in range(3)
    ]
    fake_adapter.list_payment_methods.return_value = methods

    # Request with explicit smaller limit
    res = await client.get(
        "/payments/methods",
        params={"customer_provider_id": "cus_1", "limit": 2},
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 2
    assert data["next_cursor"] is not None

    # Follow the cursor to get the next page
    next_cur = data["next_cursor"]
    res2 = await client.get(
        "/payments/methods",
        params={"customer_provider_id": "cus_1", "cursor": next_cur, "limit": 2},
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2["items"]) >= 1


@pytest.mark.asyncio
async def test_intents_pagination_limit_and_cursor(client, fake_adapter, mocker):
    # Adapter returns window and cursor; route passes through
    fake_adapter.list_intents.return_value = (
        [
            mocker.Mock(
                id="pi_1",
                provider="stripe",
                provider_intent_id="pi_1",
                status="succeeded",
                amount=100,
                currency="USD",
                client_secret="secret",
                next_action=None,
            ),
            mocker.Mock(
                id="pi_2",
                provider="stripe",
                provider_intent_id="pi_2",
                status="requires_action",
                amount=200,
                currency="USD",
                client_secret="secret2",
                next_action=None,
            ),
        ],
        "cur2",
    )

    res = await client.get("/payments/intents", params={"limit": 2})
    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"] == "cur2"
