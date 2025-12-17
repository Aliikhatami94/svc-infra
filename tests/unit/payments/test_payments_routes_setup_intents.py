import pytest

IDEMP = {"Idempotency-Key": "setup-intent-test-1"}


@pytest.mark.asyncio
async def test_create_setup_intent(client, fake_adapter, mocker):
    """Test setup intent creation for 3DS/SCA"""
    fake_adapter.create_setup_intent.return_value = mocker.Mock(
        id="seti_1",
        provider="stripe",
        provider_setup_intent_id="seti_123",
        status="requires_payment_method",
        client_secret="seti_123_secret_abc",
        next_action=None,
    )

    res = await client.post(
        "/payments/setup_intents",
        json={"payment_method_types": ["card"]},
        headers=IDEMP,
    )

    assert res.status_code == 201
    body = res.json()
    assert body["provider_setup_intent_id"] == "seti_123"
    assert body["status"] == "requires_payment_method"
    assert body["client_secret"] == "seti_123_secret_abc"

    fake_adapter.create_setup_intent.assert_awaited_once()


@pytest.mark.asyncio
async def test_confirm_setup_intent(client, fake_adapter, mocker):
    """Test setup intent confirmation"""
    fake_adapter.confirm_setup_intent.return_value = mocker.Mock(
        id="seti_1",
        provider="stripe",
        provider_setup_intent_id="seti_123",
        status="succeeded",
        client_secret="seti_123_secret_abc",
        next_action=None,
    )

    res = await client.post("/payments/setup_intents/seti_123/confirm", headers=IDEMP)
    assert res.status_code == 200
    body = res.json()
    assert body["provider_setup_intent_id"] == "seti_123"
    assert body["status"] == "succeeded"

    fake_adapter.confirm_setup_intent.assert_awaited_once_with("seti_123")


@pytest.mark.asyncio
async def test_get_setup_intent(client, fake_adapter, mocker):
    """Test getting a specific setup intent"""
    fake_adapter.get_setup_intent.return_value = mocker.Mock(
        id="seti_1",
        provider="stripe",
        provider_setup_intent_id="seti_123",
        status="requires_action",
        client_secret="seti_123_secret_abc",
        next_action=mocker.Mock(type="use_stripe_sdk", data={"type": "three_d_secure_redirect"}),
    )

    res = await client.get("/payments/setup_intents/seti_123")
    assert res.status_code == 200
    body = res.json()
    assert body["provider_setup_intent_id"] == "seti_123"
    assert body["status"] == "requires_action"
    assert body["client_secret"] == "seti_123_secret_abc"

    fake_adapter.get_setup_intent.assert_awaited_once_with("seti_123")


@pytest.mark.asyncio
async def test_setup_intent_with_3ds_action(client, fake_adapter, mocker):
    """Test setup intent that requires 3DS authentication"""
    # Mock the next_action object properly
    next_action_mock = mocker.Mock()
    next_action_mock.type = "use_stripe_sdk"
    next_action_mock.data = {"type": "three_d_secure_redirect"}

    fake_adapter.create_setup_intent.return_value = mocker.Mock(
        id="seti_1",
        provider="stripe",
        provider_setup_intent_id="seti_123",
        status="requires_action",
        client_secret="seti_123_secret_abc",
        next_action=next_action_mock,
    )

    res = await client.post(
        "/payments/setup_intents",
        json={"payment_method_types": ["card"]},
        headers=IDEMP,
    )

    assert res.status_code == 201
    body = res.json()
    assert body["provider_setup_intent_id"] == "seti_123"
    assert body["status"] == "requires_action"
    assert body["next_action"]["type"] == "use_stripe_sdk"
    assert body["next_action"]["data"]["type"] == "three_d_secure_redirect"

    fake_adapter.create_setup_intent.assert_awaited_once()


@pytest.mark.asyncio
async def test_resume_intent_after_action(client, fake_adapter, mocker):
    """Test resuming payment intent after 3DS/SCA action"""
    fake_adapter.resume_intent_after_action.return_value = mocker.Mock(
        id="pi_1",
        provider="stripe",
        provider_intent_id="pi_123",
        status="succeeded",
        amount=1000,
        currency="USD",
        client_secret="pi_123_secret_abc",
        next_action=None,
    )

    res = await client.post("/payments/intents/pi_123/resume", headers=IDEMP)
    assert res.status_code == 200
    body = res.json()
    assert body["provider_intent_id"] == "pi_123"
    assert body["status"] == "succeeded"
    assert body["amount"] == 1000

    fake_adapter.resume_intent_after_action.assert_awaited_once_with("pi_123")
