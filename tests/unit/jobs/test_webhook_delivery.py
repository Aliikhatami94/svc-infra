import pytest

from svc_infra.db.inbox import InMemoryInboxStore
from svc_infra.db.outbox import InMemoryOutboxStore
from svc_infra.jobs.builtins.webhook_delivery import make_webhook_handler
from svc_infra.jobs.queue import InMemoryJobQueue
from svc_infra.jobs.worker import process_one
from svc_infra.webhooks.signing import sign

pytestmark = pytest.mark.jobs


class FakeServer:
    def __init__(self):
        self.calls = []
        self.status = 200
        self.url = "https://example.test/webhook"

    async def post(self, url, json=None, headers=None):
        self.calls.append((url, json, headers))

        class Resp:
            def __init__(self, status):
                self.status_code = status

        return Resp(self.status)


@pytest.mark.asyncio
async def test_webhook_delivery_success(monkeypatch):
    outbox = InMemoryOutboxStore()
    inbox = InMemoryInboxStore()
    msg = outbox.enqueue("invoice.created", {"id": "inv_1"})
    job_payload = {"outbox_id": msg.id, "topic": msg.topic, "payload": msg.payload}
    queue = InMemoryJobQueue()
    queue.enqueue("outbox.invoice.created", job_payload)

    fake = FakeServer()

    async def fake_post(url, json=None, headers=None):
        return await fake.post(url, json=json, headers=headers)

    # patch httpx.AsyncClient.post
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
        get_webhook_url_for_topic=lambda t: fake.url,
        get_secret_for_topic=lambda t: "sekrit",
    )
    ok = await process_one(queue, handler)
    assert ok is True
    # delivered
    assert len(fake.calls) == 1
    _url, _body, headers = fake.calls[0]
    assert headers.get("X-Event-Id") == str(msg.id)
    assert headers.get("X-Topic") == msg.topic
    assert headers.get("X-Attempt") == "1"
    assert headers.get("X-Signature-Alg") == "hmac-sha256"
    assert headers.get("X-Signature-Version") == "v1"
    # subsequent dedupe
    queue.enqueue("outbox.invoice.created", job_payload)
    ok2 = await process_one(queue, handler)
    assert ok2 is True
    # no second call
    assert len(fake.calls) == 1


@pytest.mark.asyncio
async def test_webhook_delivery_retry_on_non_2xx(monkeypatch):
    outbox = InMemoryOutboxStore()
    inbox = InMemoryInboxStore()
    msg = outbox.enqueue("invoice.created", {"id": "inv_2"})
    job_payload = {"outbox_id": msg.id, "topic": msg.topic, "payload": msg.payload}
    queue = InMemoryJobQueue()
    queue.enqueue("outbox.invoice.created", job_payload)

    fake = FakeServer()
    fake.status = 500

    async def fake_post(url, json=None, headers=None):
        return await fake.post(url, json=json, headers=headers)

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
        get_webhook_url_for_topic=lambda t: fake.url,
        get_secret_for_topic=lambda t: "sekrit",
    )
    ok = await process_one(queue, handler)
    assert ok is True
    # should have failed and been scheduled for retry (in memory queue)
    assert len(fake.calls) == 1
    # job remains in queue with backoff; reserve_next returns same job later
    assert queue.reserve_next() is None


@pytest.mark.asyncio
async def test_webhook_delivery_uses_subscription_envelope(monkeypatch):
    outbox = InMemoryOutboxStore()
    inbox = InMemoryInboxStore()
    fake = FakeServer()
    envelope = {
        "event": {
            "topic": "invoice.created",
            "payload": {"id": "inv_sub"},
            "version": 1,
            "created_at": "2024-01-01T00:00:00+00:00",
        },
        "subscription": {
            "id": "sub_123",
            "topic": "invoice.created",
            "url": fake.url,
            "secret": "sekrit",
        },
    }
    msg = outbox.enqueue("invoice.created", envelope)
    job_payload = {"outbox_id": msg.id, "topic": msg.topic, "payload": msg.payload}
    queue = InMemoryJobQueue()
    queue.enqueue("outbox.invoice.created", job_payload)

    async def fake_post(url, json=None, headers=None):
        return await fake.post(url, json=json, headers=headers)

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
        get_webhook_url_for_topic=lambda t: "https://fallback.example",
        get_secret_for_topic=lambda t: "fallback",
    )

    ok = await process_one(queue, handler)
    assert ok is True
    assert len(fake.calls) == 1
    url, body, headers = fake.calls[0]
    assert url == fake.url
    assert body == envelope["event"]
    assert headers.get("X-Webhook-Subscription") == "sub_123"
    assert headers.get("X-Event-Id") == str(msg.id)
    expected_sig = sign("sekrit", envelope["event"])
    assert headers.get("X-Signature") == expected_sig
