from __future__ import annotations

import os

from svc_infra.db.inbox import InboxStore
from svc_infra.db.outbox import OutboxStore
from svc_infra.http import get_default_timeout_seconds, new_async_httpx_client
from svc_infra.jobs.queue import Job
from svc_infra.webhooks.signing import sign


def make_webhook_handler(
    *,
    outbox: OutboxStore,
    inbox: InboxStore,
    get_webhook_url_for_topic,
    get_secret_for_topic,
    header_name: str = "X-Signature",
):
    """Return an async job handler to deliver webhooks.

    Expected job payload shape:
    {"outbox_id": int, "topic": str, "payload": {...}}
    """

    async def _handler(job: Job) -> None:
        data = job.payload or {}
        outbox_id = data.get("outbox_id")
        topic = data.get("topic")
        payload = data.get("payload") or {}
        if not outbox_id or not topic:
            # Nothing we can do; ack to avoid poison loop
            return
        # dedupe marker key (marked after successful delivery)
        key = f"webhook:{outbox_id}"
        if inbox.is_marked(key):
            # already delivered
            outbox.mark_processed(int(outbox_id))
            return
        event = payload.get("event") if isinstance(payload, dict) else None
        subscription = payload.get("subscription") if isinstance(payload, dict) else None
        if event is not None and subscription is not None:
            delivery_payload = event
            url = subscription.get("url") or get_webhook_url_for_topic(topic)
            secret = subscription.get("secret") or get_secret_for_topic(topic)
            subscription_id = subscription.get("id")
        else:
            delivery_payload = payload
            url = get_webhook_url_for_topic(topic)
            secret = get_secret_for_topic(topic)
            subscription_id = None
        sig = sign(secret, delivery_payload)
        headers = {
            header_name: sig,
            "X-Event-Id": str(outbox_id),
            "X-Topic": str(topic),
            "X-Attempt": str(job.attempts or 1),
            "X-Signature-Alg": "hmac-sha256",
            "X-Signature-Version": "v1",
        }
        if subscription_id:
            headers["X-Webhook-Subscription"] = str(subscription_id)
        # include event payload version if present
        version = None
        if isinstance(delivery_payload, dict):
            version = delivery_payload.get("version")
        if version is not None:
            headers["X-Payload-Version"] = str(version)
        # Derive timeout: dedicated WEBHOOK_DELIVERY_TIMEOUT_SECONDS or default HTTP client timeout
        timeout_seconds = None
        env_timeout = os.getenv("WEBHOOK_DELIVERY_TIMEOUT_SECONDS")
        if env_timeout:
            try:
                timeout_seconds = float(env_timeout)
            except ValueError:
                timeout_seconds = get_default_timeout_seconds()
        else:
            timeout_seconds = get_default_timeout_seconds()

        async with new_async_httpx_client(timeout_seconds=timeout_seconds) as client:
            resp = await client.post(url, json=delivery_payload, headers=headers)
            if 200 <= resp.status_code < 300:
                # record delivery and mark processed
                inbox.mark_if_new(key, ttl_seconds=24 * 3600)
                outbox.mark_processed(int(outbox_id))
                return
            # allow retry on non-2xx: raise to trigger fail/backoff
            raise RuntimeError(f"webhook delivery failed: {resp.status_code}")

    return _handler
