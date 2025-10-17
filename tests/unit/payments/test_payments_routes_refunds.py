import pytest


@pytest.mark.asyncio
async def test_list_refunds(client, fake_adapter, mocker):
    """Test refund listing with pagination"""
    fake_adapter.list_refunds.return_value = (
        [
            mocker.Mock(
                id="re_1",
                provider="stripe",
                provider_refund_id="re_123",
                provider_payment_intent_id="pi_123",
                amount=1000,
                currency="USD",
                status="succeeded",
                reason="requested_by_customer",
                created_at="2024-01-01T00:00:00Z",
            ),
            mocker.Mock(
                id="re_2",
                provider="stripe",
                provider_refund_id="re_456",
                provider_payment_intent_id="pi_456",
                amount=500,
                currency="USD",
                status="pending",
                reason="duplicate",
                created_at="2024-01-02T00:00:00Z",
            ),
        ],
        "cursor_next",
    )

    res = await client.get("/payments/refunds")
    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"] == "cursor_next"
    assert body["items"][0]["provider_refund_id"] == "re_123"
    assert body["items"][0]["amount"] == 1000
    assert body["items"][0]["status"] == "succeeded"
    assert body["items"][0]["reason"] == "requested_by_customer"

    fake_adapter.list_refunds.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_refunds_with_payment_intent_filter(client, fake_adapter, mocker):
    """Test refund listing filtered by payment intent"""
    fake_adapter.list_refunds.return_value = ([], None)

    res = await client.get("/payments/refunds?provider_payment_intent_id=pi_123")
    assert res.status_code == 200

    fake_adapter.list_refunds.assert_awaited_once_with(
        provider_payment_intent_id="pi_123", limit=50, cursor=None
    )


@pytest.mark.asyncio
async def test_get_refund(client, fake_adapter, mocker):
    """Test getting a specific refund"""
    fake_adapter.get_refund.return_value = mocker.Mock(
        id="re_1",
        provider="stripe",
        provider_refund_id="re_123",
        provider_payment_intent_id="pi_123",
        amount=1000,
        currency="USD",
        status="succeeded",
        reason="requested_by_customer",
        created_at="2024-01-01T00:00:00Z",
    )

    res = await client.get("/payments/refunds/re_123")
    assert res.status_code == 200
    body = res.json()
    assert body["provider_refund_id"] == "re_123"
    assert body["provider_payment_intent_id"] == "pi_123"
    assert body["amount"] == 1000
    assert body["currency"] == "USD"
    assert body["status"] == "succeeded"
    assert body["reason"] == "requested_by_customer"
    assert body["created_at"] == "2024-01-01T00:00:00Z"

    fake_adapter.get_refund.assert_awaited_once_with("re_123")


@pytest.mark.asyncio
async def test_list_refunds_empty(client, fake_adapter, mocker):
    """Test refund listing when no refunds exist"""
    fake_adapter.list_refunds.return_value = ([], None)

    res = await client.get("/payments/refunds")
    assert res.status_code == 200
    body = res.json()

    assert len(body["items"]) == 0
    assert body["next_cursor"] is None

    fake_adapter.list_refunds.assert_awaited_once()
