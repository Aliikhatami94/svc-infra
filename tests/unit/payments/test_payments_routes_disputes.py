import pytest


@pytest.mark.asyncio
async def test_list_disputes(client, fake_adapter, mocker):
    """Test dispute listing with pagination"""
    fake_adapter.list_disputes.return_value = (
        [
            mocker.Mock(
                id="dp_1",
                provider="stripe",
                provider_dispute_id="dp_123",
                amount=1000,
                currency="USD",
                reason="fraudulent",
                status="needs_response",
                evidence_due_by="2024-12-31T23:59:59Z",
                created_at="2024-01-01T00:00:00Z",
            ),
            mocker.Mock(
                id="dp_2",
                provider="stripe",
                provider_dispute_id="dp_456",
                amount=2000,
                currency="USD",
                reason="subscription_canceled",
                status="under_review",
                evidence_due_by="2024-11-30T23:59:59Z",
                created_at="2024-01-02T00:00:00Z",
            ),
        ],
        "cursor_next",
    )

    res = await client.get("/payments/disputes")
    assert res.status_code == 200
    body = res.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"] == "cursor_next"
    assert body["items"][0]["provider_dispute_id"] == "dp_123"
    assert body["items"][0]["amount"] == 1000
    assert body["items"][0]["reason"] == "fraudulent"

    fake_adapter.list_disputes.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_disputes_with_status_filter(client, fake_adapter, mocker):
    """Test dispute listing with status filter"""
    fake_adapter.list_disputes.return_value = ([], None)

    res = await client.get("/payments/disputes?status=needs_response")
    assert res.status_code == 200

    fake_adapter.list_disputes.assert_awaited_once_with(
        status="needs_response", limit=50, cursor=None
    )


@pytest.mark.asyncio
async def test_get_dispute(client, fake_adapter, mocker):
    """Test getting a specific dispute"""
    fake_adapter.get_dispute.return_value = mocker.Mock(
        id="dp_1",
        provider="stripe",
        provider_dispute_id="dp_123",
        amount=1000,
        currency="USD",
        reason="fraudulent",
        status="needs_response",
        evidence_due_by="2024-12-31T23:59:59Z",
        created_at="2024-01-01T00:00:00Z",
    )

    res = await client.get("/payments/disputes/dp_123")
    assert res.status_code == 200
    body = res.json()
    assert body["provider_dispute_id"] == "dp_123"
    assert body["amount"] == 1000
    assert body["reason"] == "fraudulent"
    assert body["status"] == "needs_response"
    assert body["evidence_due_by"] == "2024-12-31T23:59:59Z"

    fake_adapter.get_dispute.assert_awaited_once_with("dp_123")


@pytest.mark.asyncio
async def test_submit_dispute_evidence(client, fake_adapter, mocker):
    """Test submitting dispute evidence"""
    fake_adapter.submit_dispute_evidence.return_value = mocker.Mock(
        id="dp_1",
        provider="stripe",
        provider_dispute_id="dp_123",
        amount=1000,
        currency="USD",
        reason="fraudulent",
        status="under_review",
        evidence_due_by="2024-12-31T23:59:59Z",
        created_at="2024-01-01T00:00:00Z",
    )

    evidence_data = {
        "uncategorized_text": "This was a legitimate transaction",
        "product_description": "Digital service subscription",
        "customer_name": "John Doe",
        "customer_email": "john@example.com",
    }

    res = await client.post(
        "/payments/disputes/dp_123/submit_evidence",
        json={"evidence": evidence_data},
        headers={"Idempotency-Key": "dispute-evidence-1"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["provider_dispute_id"] == "dp_123"
    assert body["status"] == "under_review"

    fake_adapter.submit_dispute_evidence.assert_awaited_once_with("dp_123", evidence_data)


@pytest.mark.asyncio
async def test_submit_dispute_evidence_minimal(client, fake_adapter, mocker):
    """Test submitting minimal dispute evidence"""
    fake_adapter.submit_dispute_evidence.return_value = mocker.Mock(
        id="dp_1",
        provider="stripe",
        provider_dispute_id="dp_123",
        amount=1000,
        currency="USD",
        reason="fraudulent",
        status="under_review",
        evidence_due_by="2024-12-31T23:59:59Z",
        created_at="2024-01-01T00:00:00Z",
    )

    evidence_data = {"uncategorized_text": "This was a legitimate transaction"}

    res = await client.post(
        "/payments/disputes/dp_123/submit_evidence",
        json={"evidence": evidence_data},
        headers={"Idempotency-Key": "dispute-evidence-2"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["provider_dispute_id"] == "dp_123"
    assert body["status"] == "under_review"

    fake_adapter.submit_dispute_evidence.assert_awaited_once_with("dp_123", evidence_data)
