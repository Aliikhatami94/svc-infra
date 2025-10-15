from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from svc_infra.db.outbox import InMemoryOutboxStore, OutboxStore

from .service import InMemoryWebhookSubscriptions, WebhookService

router = APIRouter(prefix="/_webhooks", tags=["webhooks"])


def get_outbox() -> OutboxStore:
    # For now expose an in-memory default. Apps can override via DI.
    # In production, provide a proper store through dependency override.
    return InMemoryOutboxStore()


def get_subs() -> InMemoryWebhookSubscriptions:
    return InMemoryWebhookSubscriptions()


def get_service(
    outbox: OutboxStore = Depends(get_outbox),
    subs: InMemoryWebhookSubscriptions = Depends(get_subs),
) -> WebhookService:
    return WebhookService(outbox=outbox, subs=subs)


@router.post("/subscriptions")
def add_subscription(
    body: Dict[str, Any],
    subs: InMemoryWebhookSubscriptions = Depends(get_subs),
):
    topic = body.get("topic")
    url = body.get("url")
    secret = body.get("secret")
    if not topic or not url or not secret:
        raise HTTPException(status_code=400, detail="Missing topic/url/secret")
    subs.add(topic, url, secret)
    return {"ok": True}


@router.post("/test-fire")
def test_fire(
    body: Dict[str, Any],
    svc: WebhookService = Depends(get_service),
):
    topic = body.get("topic")
    payload = body.get("payload") or {}
    if not topic:
        raise HTTPException(status_code=400, detail="Missing topic")
    outbox_id = svc.publish(topic, payload)
    return {"ok": True, "outbox_id": outbox_id}
