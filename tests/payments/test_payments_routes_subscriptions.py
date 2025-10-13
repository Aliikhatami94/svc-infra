import pytest

IDEMP = {"Idempotency-Key": "subscription-test-1"}


@pytest.mark.asyncio
async def test_create_subscription(client, fake_adapter, mocker):
    """Test subscription creation"""
    fake_adapter.create_subscription.return_value = mocker.Mock(
        id="sub_1",
        provider="stripe",
        provider_subscription_id="sub_123",
        provider_price_id="price_123",
        status="active",
        quantity=1,
        cancel_at_period_end=False,
        current_period_end="2024-12-31T23:59:59Z",
    )

    res = await client.post(
        "/payments/subscriptions",
        json={
            "customer_provider_id": "cus_123",
            "price_provider_id": "price_123",
            "quantity": 1,
            "trial_days": 7,
            "proration_behavior": "create_prorations",
        },
        headers=IDEMP,
    )

    assert res.status_code == 201
    body = res.json()
    assert body["provider_subscription_id"] == "sub_123"
    assert body["provider_price_id"] == "price_123"
    assert body["status"] == "active"
    assert body["quantity"] == 1
    assert body["cancel_at_period_end"] is False

    fake_adapter.create_subscription.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_subscription(client, fake_adapter, mocker):
    """Test getting a specific subscription"""
    fake_adapter.get_subscription.return_value = mocker.Mock(
        id="sub_1",
        provider="stripe",
        provider_subscription_id="sub_123",
        provider_price_id="price_123",
        status="active",
        quantity=1,
        cancel_at_period_end=False,
        current_period_end="2024-12-31T23:59:59Z",
    )

    res = await client.get("/payments/subscriptions/sub_123")
    assert res.status_code == 200
    body = res.json()
    assert body["provider_subscription_id"] == "sub_123"
    assert body["status"] == "active"
    assert body["quantity"] == 1

    fake_adapter.get_subscription.assert_awaited_once_with("sub_123")


@pytest.mark.asyncio
async def test_list_subscriptions(client, fake_adapter, mocker):
    """Test subscription listing with pagination"""
    fake_adapter.list_subscriptions.return_value = (
        [
            mocker.Mock(
                id="sub_1",
                provider="stripe",
                provider_subscription_id="sub_123",
                provider_price_id="price_123",
                status="active",
                quantity=1,
                cancel_at_period_end=False,
                current_period_end="2024-12-31T23:59:59Z",
            ),
            mocker.Mock(
                id="sub_2",
                provider="stripe",
                provider_subscription_id="sub_456",
                provider_price_id="price_456",
                status="trialing",
                quantity=2,
                cancel_at_period_end=True,
                current_period_end="2024-11-30T23:59:59Z",
            ),
        ],
        "cursor_next",
    )

    res = await client.get("/payments/subscriptions")
    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"] == "cursor_next"
    assert body["items"][0]["provider_subscription_id"] == "sub_123"

    fake_adapter.list_subscriptions.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_subscriptions_with_filters(client, fake_adapter, mocker):
    """Test subscription listing with filters"""
    fake_adapter.list_subscriptions.return_value = ([], None)

    res = await client.get("/payments/subscriptions?customer_provider_id=cus_123&status=active")
    assert res.status_code == 200

    fake_adapter.list_subscriptions.assert_awaited_once_with(
        customer_provider_id="cus_123", status="active", limit=50, cursor=None
    )


@pytest.mark.asyncio
async def test_update_subscription(client, fake_adapter, mocker):
    """Test subscription update"""
    fake_adapter.update_subscription.return_value = mocker.Mock(
        id="sub_1",
        provider="stripe",
        provider_subscription_id="sub_123",
        provider_price_id="price_456",
        status="active",
        quantity=2,
        cancel_at_period_end=True,
        current_period_end="2024-12-31T23:59:59Z",
    )

    res = await client.post(
        "/payments/subscriptions/sub_123",
        json={
            "price_provider_id": "price_456",
            "quantity": 2,
            "cancel_at_period_end": True,
            "proration_behavior": "create_prorations",
        },
        headers=IDEMP,
    )

    assert res.status_code == 200
    body = res.json()
    assert body["provider_price_id"] == "price_456"
    assert body["quantity"] == 2
    assert body["cancel_at_period_end"] is True

    fake_adapter.update_subscription.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancel_subscription(client, fake_adapter, mocker):
    """Test subscription cancellation"""
    fake_adapter.cancel_subscription.return_value = mocker.Mock(
        id="sub_1",
        provider="stripe",
        provider_subscription_id="sub_123",
        provider_price_id="price_123",
        status="canceled",
        quantity=1,
        cancel_at_period_end=True,
        current_period_end="2024-12-31T23:59:59Z",
    )

    res = await client.post(
        "/payments/subscriptions/sub_123/cancel", json={"at_period_end": True}, headers=IDEMP
    )

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "canceled"
    assert body["cancel_at_period_end"] is True

    fake_adapter.cancel_subscription.assert_awaited_once_with("sub_123", True)


@pytest.mark.asyncio
async def test_cancel_subscription_immediate(client, fake_adapter, mocker):
    """Test immediate subscription cancellation"""
    fake_adapter.cancel_subscription.return_value = mocker.Mock(
        id="sub_1",
        provider="stripe",
        provider_subscription_id="sub_123",
        provider_price_id="price_123",
        status="canceled",
        quantity=1,
        cancel_at_period_end=False,
        current_period_end="2024-12-31T23:59:59Z",
    )

    res = await client.post(
        "/payments/subscriptions/sub_123/cancel?at_period_end=false", headers=IDEMP
    )

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "canceled"
    assert body["cancel_at_period_end"] is False

    fake_adapter.cancel_subscription.assert_awaited_once_with("sub_123", False)
