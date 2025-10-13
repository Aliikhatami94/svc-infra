import pytest


@pytest.mark.asyncio
async def test_list_intents_pagination(client, fake_adapter, mocker):
    fake_adapter.list_intents.return_value = (
        [
            mocker.Mock(
                id="pi_1",
                provider="stripe",
                provider_intent_id="pi_1",
                status="succeeded",
                amount=100,
                currency="USD",
                client_secret="secret",
                next_action=None,
            )
        ],
        "cursor_2",
    )
    res = await client.get("/payments/intents")
    assert res.status_code == 200
    body = res.json()
    assert body["next_cursor"] == "cursor_2"
    assert len(body["items"]) == 1
