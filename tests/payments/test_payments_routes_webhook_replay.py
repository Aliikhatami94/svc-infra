import pytest

IDEMP = {"Idempotency-Key": "webhook-replay-test-1"}


@pytest.mark.asyncio
async def test_replay_webhooks_by_event_ids(client, fake_adapter, mocker):
    """Test webhook replay by specific event IDs"""
    fake_adapter.replay_webhooks.return_value = 3

    res = await client.post(
        "/payments/webhooks/replay",
        json={"event_ids": ["evt_123", "evt_456", "evt_789"]},
        headers=IDEMP,
    )

    assert res.status_code == 200
    body = res.json()
    assert body["replayed"] == 3

    fake_adapter.replay_webhooks.assert_awaited_once_with(
        None, None, ["evt_123", "evt_456", "evt_789"]
    )


@pytest.mark.asyncio
async def test_replay_webhooks_by_date_range(client, fake_adapter, mocker):
    """Test webhook replay by date range"""
    fake_adapter.replay_webhooks.return_value = 5

    res = await client.post(
        "/payments/webhooks/replay?since=2024-01-01T00:00:00Z&until=2024-01-31T23:59:59Z",
        json={},
        headers=IDEMP,
    )

    assert res.status_code == 200
    body = res.json()
    assert body["replayed"] == 5

    fake_adapter.replay_webhooks.assert_awaited_once_with(
        "2024-01-01T00:00:00Z", "2024-01-31T23:59:59Z", []
    )


@pytest.mark.asyncio
async def test_replay_webhooks_since_only(client, fake_adapter, mocker):
    """Test webhook replay with only since date"""
    fake_adapter.replay_webhooks.return_value = 2

    res = await client.post(
        "/payments/webhooks/replay?since=2024-01-01T00:00:00Z", json={}, headers=IDEMP
    )

    assert res.status_code == 200
    body = res.json()
    assert body["replayed"] == 2

    fake_adapter.replay_webhooks.assert_awaited_once_with("2024-01-01T00:00:00Z", None, [])


@pytest.mark.asyncio
async def test_replay_webhooks_until_only(client, fake_adapter, mocker):
    """Test webhook replay with only until date"""
    fake_adapter.replay_webhooks.return_value = 1

    res = await client.post(
        "/payments/webhooks/replay?until=2024-01-31T23:59:59Z", json={}, headers=IDEMP
    )

    assert res.status_code == 200
    body = res.json()
    assert body["replayed"] == 1

    fake_adapter.replay_webhooks.assert_awaited_once_with(None, "2024-01-31T23:59:59Z", [])


@pytest.mark.asyncio
async def test_replay_webhooks_no_events(client, fake_adapter, mocker):
    """Test webhook replay when no events match criteria"""
    fake_adapter.replay_webhooks.return_value = 0

    res = await client.post(
        "/payments/webhooks/replay?since=2024-12-01T00:00:00Z&until=2024-12-31T23:59:59Z",
        json={},
        headers=IDEMP,
    )

    assert res.status_code == 200
    body = res.json()
    assert body["replayed"] == 0

    fake_adapter.replay_webhooks.assert_awaited_once_with(
        "2024-12-01T00:00:00Z", "2024-12-31T23:59:59Z", []
    )


@pytest.mark.asyncio
async def test_replay_webhooks_empty_request(client, fake_adapter, mocker):
    """Test webhook replay with empty request body"""
    fake_adapter.replay_webhooks.return_value = 0

    res = await client.post("/payments/webhooks/replay", json={}, headers=IDEMP)

    assert res.status_code == 200
    body = res.json()
    assert body["replayed"] == 0

    fake_adapter.replay_webhooks.assert_awaited_once_with(None, None, [])
