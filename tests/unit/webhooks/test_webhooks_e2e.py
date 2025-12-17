import pytest

from svc_infra.db.inbox import InMemoryInboxStore
from svc_infra.db.outbox import InMemoryOutboxStore
from svc_infra.jobs.builtins.outbox_processor import make_outbox_tick
from svc_infra.jobs.builtins.webhook_delivery import make_webhook_handler
from svc_infra.jobs.queue import InMemoryJobQueue
from svc_infra.jobs.worker import process_one
from svc_infra.webhooks.encryption import decrypt_secret, is_encrypted
from svc_infra.webhooks.service import InMemoryWebhookSubscriptions, WebhookService

pytestmark = pytest.mark.webhooks


class FlakyServer:
    def __init__(self, ok_after: int = 1):
        self.calls = 0
        self.ok_after = ok_after
        self.url = "https://example.test/webhook"

    async def post(self, url, json=None, headers=None):
        self.calls += 1
        status = 200 if self.calls >= self.ok_after else 500

        class Resp:
            def __init__(self, status):
                self.status_code = status

        return Resp(status)


def test_publish_enqueues_subscription_identity():
    outbox = InMemoryOutboxStore()
    subs = InMemoryWebhookSubscriptions()
    subs.add("invoice.created", "https://example.test/a", "secret-a")
    subs.add("invoice.created", "https://example.test/b", "secret-b")
    svc = WebhookService(outbox=outbox, subs=subs)

    svc.publish("invoice.created", {"id": "inv_multi"})

    messages = [m for m in outbox._messages if m.topic == "invoice.created"]
    assert len(messages) == 2
    subscriptions = [m.payload["subscription"] for m in messages]
    urls = {s["url"] for s in subscriptions}
    encrypted_secrets = [s["secret"] for s in subscriptions]
    ids = {s["id"] for s in subscriptions}
    assert urls == {"https://example.test/a", "https://example.test/b"}
    # Secrets should be encrypted in the outbox
    for encrypted in encrypted_secrets:
        assert is_encrypted(encrypted), f"Secret should be encrypted: {encrypted}"
    # Decrypted secrets should match originals
    decrypted_secrets = {decrypt_secret(s) for s in encrypted_secrets}
    assert decrypted_secrets == {"secret-a", "secret-b"}
    assert len(ids) == 2
    for msg in messages:
        event = msg.payload["event"]
        assert event["topic"] == "invoice.created"
        assert event["payload"]["id"] == "inv_multi"


@pytest.mark.asyncio
async def test_webhooks_e2e_publish_to_delivery_retry(monkeypatch):
    # Setup
    outbox = InMemoryOutboxStore()
    inbox = InMemoryInboxStore()
    subs = InMemoryWebhookSubscriptions()
    subs.add("invoice.created", "https://example.test/webhook", "sekrit")
    svc = WebhookService(outbox=outbox, subs=subs)
    queue = InMemoryJobQueue()

    # Publish event → outbox
    outbox_id = svc.publish("invoice.created", {"id": "inv_X", "version": 2})

    # Outbox tick → enqueue job
    tick = make_outbox_tick(outbox, queue)
    await tick()

    # Prepare handler + fake HTTP
    flaky = FlakyServer(ok_after=2)

    async def fake_post(url, json=None, headers=None):
        return await flaky.post(url, json=json, headers=headers)

    import httpx

    class DummyClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            return await fake_post(url, json=json, headers=headers)

    monkeypatch.setattr(httpx, "AsyncClient", DummyClient)

    handler = make_webhook_handler(
        outbox=outbox,
        inbox=inbox,
        get_webhook_url_for_topic=lambda t: flaky.url,
        get_secret_for_topic=lambda t: "sekrit",
    )

    # lower backoff to immediate for test
    # mutate the queued job's backoff to 0 so retry happens immediately
    assert queue._jobs, "expected a queued job"
    queue._jobs[0].backoff_seconds = 0

    # First attempt fails (500), job is requeued immediately
    ok1 = await process_one(queue, handler)
    assert ok1 is True
    # Second attempt succeeds
    ok2 = await process_one(queue, handler)
    assert ok2 is True

    # Verify outbox processed
    msg = [m for m in outbox._messages if m.id == outbox_id][0]
    assert msg.processed_at is not None
    # Verify we had exactly two HTTP calls
    assert flaky.calls == 2
