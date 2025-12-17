import pytest

IDEMP = {"Idempotency-Key": "k2"}


@pytest.mark.asyncio
async def test_attach_and_list_methods(client, fake_adapter, mocker):
    fake_adapter.attach_payment_method.return_value = mocker.Mock(
        id="pm_1",
        provider="stripe",
        provider_customer_id="cus_1",
        provider_method_id="pm_1",
        brand="visa",
        last4="4242",
        is_default=True,
        exp_month=12,
        exp_year=2025,
    )
    fake_adapter.list_payment_methods.return_value = [
        mocker.Mock(
            id="pm_1",
            provider="stripe",
            provider_customer_id="cus_1",
            provider_method_id="pm_1",
            brand="visa",
            last4="4242",
            is_default=True,
            exp_month=12,
            exp_year=2025,
        )
    ]

    res = await client.post(
        "/payments/methods/attach",
        json={
            "customer_provider_id": "cus_1",
            "payment_method_token": "pm_1",
            "make_default": True,
        },
        headers=IDEMP,
    )
    assert res.status_code == 201
    assert res.json()["provider_method_id"] == "pm_1"

    res = await client.get(
        "/payments/methods", params={"customer_provider_id": "cus_1"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["items"][0]["is_default"] is True
