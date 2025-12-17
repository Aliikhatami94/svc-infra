import pytest


@pytest.mark.asyncio
async def test_webhook_ok(client, fake_adapter):
    fake_adapter.handle_webhook.return_value = {"ok": True}
    res = await client.post(
        "/payments/webhooks/stripe",
        content=b"{}",
        headers={"Stripe-Signature": "t=1,v1=abc"},
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True
    fake_adapter.handle_webhook.assert_awaited_once()
