# Webhooks Framework

This module provides primitives to publish events to external consumers via webhooks, verify inbound signatures, and handle robust retries using the shared JobQueue and Outbox patterns.

> ℹ️ Webhook helper environment expectations live in [Environment Reference](environment.md).

## Quickstart

- Subscriptions and publishing:

```python
from svc_infra.webhooks.service import InMemoryWebhookSubscriptions, WebhookService
from svc_infra.db.outbox import InMemoryOutboxStore

subs = InMemoryWebhookSubscriptions()
subs.add("invoice.created", "https://example.com/webhook", "sekrit")
svc = WebhookService(outbox=InMemoryOutboxStore(), subs=subs)
svc.publish("invoice.created", {"id": "inv_1", "version": 1})
```

- Delivery worker and headers:

```python
from svc_infra.jobs.builtins.webhook_delivery import make_webhook_handler
from svc_infra.jobs.worker import process_one

handler = make_webhook_handler(
    outbox=..., inbox=..., get_webhook_url_for_topic=lambda t: url, get_secret_for_topic=lambda t: secret,
)
# process_one(queue, handler) will POST JSON with headers:
# X-Event-Id, X-Topic, X-Attempt, X-Signature (HMAC-SHA256), X-Signature-Alg, X-Signature-Version, X-Payload-Version
```

- Verification (FastAPI):

```python
from fastapi import Depends, FastAPI
from svc_infra.webhooks.fastapi import require_signature
from svc_infra.webhooks.signing import sign

app = FastAPI()
app.post("/webhook")(lambda body=Depends(require_signature(lambda: ["old","new"])): {"ok": True})
```

## Runner wiring

- One-call jobs setup and scheduler tick from env:

```python
from svc_infra.jobs.easy import easy_jobs
from svc_infra.jobs.builtins.outbox_processor import make_outbox_tick

queue, scheduler = easy_jobs()  # uses JOBS_DRIVER and REDIS_URL
scheduler.add_task("outbox", 1, make_outbox_tick(outbox_store, queue))
# Start runner: `svc-infra jobs run`
```

## Notes
- Retries/backoff are handled by the JobQueue; delivery marks Inbox after success to prevent duplicates.
- For production subscriptions and inbox/outbox, provide persistent implementations and override DI in your app.
- Signature rotation supported via `verify_any` and FastAPI dependency accepting multiple secrets.
