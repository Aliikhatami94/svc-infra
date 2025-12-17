import pytest

IDEMP = {"Idempotency-Key": "test-key-1"}


@pytest.mark.asyncio
async def test_create_intent(client, fake_adapter, mocker):
    # stub adapter return
    fake_adapter.create_intent.return_value = mocker.Mock(
        id="pi_1",
        provider="stripe",
        provider_intent_id="pi_1",
        status="requires_confirmation",
        amount=1234,
        currency="USD",
        client_secret="secret",
        next_action=None,
    )

    res = await client.post(
        "/payments/intents",
        json={
            "amount": 1234,
            "currency": "USD",
            "capture_method": "manual",
            "payment_method_types": [],
        },
        headers=IDEMP,
    )
    assert res.status_code == 201
    body = res.json()
    assert body["provider_intent_id"] == "pi_1"
    # Location header points to GET intent
    assert res.headers["Location"].endswith("/payments/intents/pi_1")

    fake_adapter.create_intent.assert_awaited_once()


@pytest.mark.asyncio
async def test_confirm_cancel_capture_flow(client, fake_adapter, mocker):
    fake_adapter.confirm_intent.return_value = mocker.Mock(
        id="pi_1",
        provider="stripe",
        provider_intent_id="pi_1",
        status="requires_capture",
        amount=1234,
        currency="USD",
        client_secret="secret",
        next_action=None,
    )
    fake_adapter.capture_intent.return_value = mocker.Mock(
        id="pi_1",
        provider="stripe",
        provider_intent_id="pi_1",
        status="succeeded",
        amount=1234,
        currency="USD",
        client_secret="secret",
        next_action=None,
    )

    res = await client.post("/payments/intents/pi_1/confirm", headers=IDEMP)
    assert res.status_code == 200
    assert res.json()["status"] == "requires_capture"

    res = await client.post(
        "/payments/intents/pi_1/capture", json={"amount": 1234}, headers=IDEMP
    )
    assert res.status_code == 200
    assert res.json()["status"] == "succeeded"

    fake_adapter.confirm_intent.assert_awaited_once_with("pi_1")
    fake_adapter.capture_intent.assert_awaited_once()
