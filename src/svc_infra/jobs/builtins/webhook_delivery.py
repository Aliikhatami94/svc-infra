from __future__ import annotations

import hashlib
import hmac
import json
from typing import Dict

import httpx

from svc_infra.db.inbox import InboxStore
from svc_infra.db.outbox import OutboxStore
from svc_infra.jobs.queue import Job


def _compute_signature(secret: str, payload: Dict) -> str:
    body = json.dumps(payload, separators=(",", ":")).encode()
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


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
        # dedupe by outbox_id via inbox
        key = f"webhook:{outbox_id}"
        if not inbox.mark_if_new(key, ttl_seconds=24 * 3600):
            # already delivered
            outbox.mark_processed(int(outbox_id))
            return
        url = get_webhook_url_for_topic(topic)
        secret = get_secret_for_topic(topic)
        sig = _compute_signature(secret, payload)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload, headers={header_name: sig})
            if 200 <= resp.status_code < 300:
                outbox.mark_processed(int(outbox_id))
                return
            # allow retry on non-2xx: raise to trigger fail/backoff
            raise RuntimeError(f"webhook delivery failed: {resp.status_code}")

    return _handler
