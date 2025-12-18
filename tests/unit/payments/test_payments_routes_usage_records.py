import pytest

IDEMP = {"Idempotency-Key": "usage-record-test-1"}


@pytest.mark.asyncio
async def test_create_usage_record(client, fake_adapter, mocker):
    """Test usage record creation for metered billing"""
    fake_adapter.create_usage_record.return_value = mocker.Mock(
        id="ur_1",
        quantity=100,
        timestamp=1704067200,
        subscription_item="si_123",
        provider_price_id="price_123",
        action="increment",
    )

    res = await client.post(
        "/payments/usage_records",
        json={
            "subscription_item": "si_123",
            "provider_price_id": "price_123",
            "quantity": 100,
            "timestamp": 1704067200,
            "action": "increment",
        },
        headers=IDEMP,
    )

    assert res.status_code == 201
    body = res.json()
    assert body["id"] == "ur_1"
    assert body["quantity"] == 100
    assert body["timestamp"] == 1704067200
    assert body["subscription_item"] == "si_123"
    assert body["provider_price_id"] == "price_123"

    fake_adapter.create_usage_record.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_usage_record_with_set_action(client, fake_adapter, mocker):
    """Test usage record creation with set action"""
    fake_adapter.create_usage_record.return_value = mocker.Mock(
        id="ur_2",
        quantity=250,
        timestamp=1704067200,
        subscription_item="si_456",
        provider_price_id="price_456",
        action="set",
    )

    res = await client.post(
        "/payments/usage_records",
        json={
            "subscription_item": "si_456",
            "provider_price_id": "price_456",
            "quantity": 250,
            "timestamp": 1704067200,
            "action": "set",
        },
        headers=IDEMP,
    )

    assert res.status_code == 201
    body = res.json()
    assert body["id"] == "ur_2"
    assert body["quantity"] == 250
    assert body["action"] == "set"

    fake_adapter.create_usage_record.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_usage_records(client, fake_adapter, mocker):
    """Test usage record listing with pagination"""
    fake_adapter.list_usage_records.return_value = (
        [
            mocker.Mock(
                id="ur_1",
                quantity=100,
                timestamp=1704067200,
                subscription_item="si_123",
                provider_price_id="price_123",
                action="increment",
            ),
            mocker.Mock(
                id="ur_2",
                quantity=150,
                timestamp=1704153600,
                subscription_item="si_123",
                provider_price_id="price_123",
                action="increment",
            ),
            mocker.Mock(
                id="ur_3",
                quantity=200,
                timestamp=1704240000,
                subscription_item="si_456",
                provider_price_id="price_456",
                action="increment",
            ),
        ],
        "cursor_next",
    )

    res = await client.get("/payments/usage_records")
    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 3
    assert body["next_cursor"] == "cursor_next"
    assert body["items"][0]["id"] == "ur_1"
    assert body["items"][0]["quantity"] == 100
    assert body["items"][0]["subscription_item"] == "si_123"

    fake_adapter.list_usage_records.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_usage_records_with_subscription_item_filter(client, fake_adapter, mocker):
    """Test usage record listing filtered by subscription item"""
    fake_adapter.list_usage_records.return_value = ([], None)

    res = await client.get("/payments/usage_records?subscription_item=si_123")
    assert res.status_code == 200

    fake_adapter.list_usage_records.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_usage_records_with_provider_price_filter(client, fake_adapter, mocker):
    """Test usage record listing filtered by provider price"""
    fake_adapter.list_usage_records.return_value = ([], None)

    res = await client.get("/payments/usage_records?provider_price_id=price_123")
    assert res.status_code == 200

    fake_adapter.list_usage_records.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_usage_record(client, fake_adapter, mocker):
    """Test getting a specific usage record"""
    fake_adapter.get_usage_record.return_value = mocker.Mock(
        id="ur_1",
        quantity=100,
        timestamp=1704067200,
        subscription_item="si_123",
        provider_price_id="price_123",
        action="increment",
    )

    res = await client.get("/payments/usage_records/ur_1")
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == "ur_1"
    assert body["quantity"] == 100
    assert body["timestamp"] == 1704067200
    assert body["subscription_item"] == "si_123"
    assert body["provider_price_id"] == "price_123"

    fake_adapter.get_usage_record.assert_awaited_once_with("ur_1")


@pytest.mark.asyncio
async def test_list_usage_records_empty(client, fake_adapter, mocker):
    """Test usage record listing when no records exist"""
    fake_adapter.list_usage_records.return_value = ([], None)

    res = await client.get("/payments/usage_records")
    assert res.status_code == 200
    body = res.json()

    assert len(body["items"]) == 0
    assert body["next_cursor"] is None

    fake_adapter.list_usage_records.assert_awaited_once()
