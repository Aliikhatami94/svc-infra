import pytest


@pytest.mark.asyncio
async def test_get_balance(client, fake_adapter, mocker):
    """Test getting balance snapshot"""
    fake_adapter.get_balance_snapshot.return_value = mocker.Mock(
        available=[
            mocker.Mock(currency="USD", amount=5000),
            mocker.Mock(currency="EUR", amount=3000),
        ],
        pending=[
            mocker.Mock(currency="USD", amount=1000),
            mocker.Mock(currency="GBP", amount=500),
        ],
    )

    res = await client.get("/payments/balance")
    assert res.status_code == 200
    body = res.json()

    # Check available balances
    assert len(body["available"]) == 2
    assert body["available"][0]["currency"] == "USD"
    assert body["available"][0]["amount"] == 5000
    assert body["available"][1]["currency"] == "EUR"
    assert body["available"][1]["amount"] == 3000

    # Check pending balances
    assert len(body["pending"]) == 2
    assert body["pending"][0]["currency"] == "USD"
    assert body["pending"][0]["amount"] == 1000
    assert body["pending"][1]["currency"] == "GBP"
    assert body["pending"][1]["amount"] == 500

    fake_adapter.get_balance_snapshot.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_payouts(client, fake_adapter, mocker):
    """Test payout listing with pagination"""
    fake_adapter.list_payouts.return_value = (
        [
            mocker.Mock(
                id="po_1",
                provider="stripe",
                provider_payout_id="po_123",
                amount=5000,
                currency="USD",
                status="paid",
                arrival_date="2024-01-15T00:00:00Z",
                type="bank_account",
            ),
            mocker.Mock(
                id="po_2",
                provider="stripe",
                provider_payout_id="po_456",
                amount=3000,
                currency="USD",
                status="pending",
                arrival_date="2024-01-20T00:00:00Z",
                type="bank_account",
            ),
        ],
        "cursor_next",
    )

    res = await client.get("/payments/payouts")
    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"] == "cursor_next"
    assert body["items"][0]["provider_payout_id"] == "po_123"
    assert body["items"][0]["amount"] == 5000
    assert body["items"][0]["status"] == "paid"
    assert body["items"][0]["type"] == "bank_account"

    fake_adapter.list_payouts.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_payout(client, fake_adapter, mocker):
    """Test getting a specific payout"""
    fake_adapter.get_payout.return_value = mocker.Mock(
        id="po_1",
        provider="stripe",
        provider_payout_id="po_123",
        amount=5000,
        currency="USD",
        status="paid",
        arrival_date="2024-01-15T00:00:00Z",
        type="bank_account",
    )

    res = await client.get("/payments/payouts/po_123")
    assert res.status_code == 200
    body = res.json()
    assert body["provider_payout_id"] == "po_123"
    assert body["amount"] == 5000
    assert body["currency"] == "USD"
    assert body["status"] == "paid"
    assert body["arrival_date"] == "2024-01-15T00:00:00Z"
    assert body["type"] == "bank_account"

    fake_adapter.get_payout.assert_awaited_once_with("po_123")


@pytest.mark.asyncio
async def test_get_balance_empty(client, fake_adapter, mocker):
    """Test getting balance when no funds available"""
    fake_adapter.get_balance_snapshot.return_value = mocker.Mock(available=[], pending=[])

    res = await client.get("/payments/balance")
    assert res.status_code == 200
    body = res.json()

    assert len(body["available"]) == 0
    assert len(body["pending"]) == 0

    fake_adapter.get_balance_snapshot.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_payouts_empty(client, fake_adapter, mocker):
    """Test payout listing when no payouts exist"""
    fake_adapter.list_payouts.return_value = ([], None)

    res = await client.get("/payments/payouts")
    assert res.status_code == 200
    body = res.json()

    assert len(body["items"]) == 0
    assert body["next_cursor"] is None

    fake_adapter.list_payouts.assert_awaited_once()
