from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List

from svc_infra.db.outbox import OutboxStore


@dataclass
class WebhookSubscription:
    topic: str
    url: str
    secret: str


class InMemoryWebhookSubscriptions:
    def __init__(self):
        self._subs: Dict[str, List[WebhookSubscription]] = {}

    def add(self, topic: str, url: str, secret: str) -> None:
        self._subs.setdefault(topic, []).append(WebhookSubscription(topic, url, secret))

    def get_for_topic(self, topic: str) -> List[WebhookSubscription]:
        return list(self._subs.get(topic, []))


class WebhookService:
    def __init__(self, outbox: OutboxStore, subs: InMemoryWebhookSubscriptions):
        self._outbox = outbox
        self._subs = subs

    def publish(self, topic: str, payload: Dict, *, version: int = 1) -> int:
        event = {
            "topic": topic,
            "payload": payload,
            "version": version,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        # For each subscription, enqueue an outbox message
        last_id = 0
        for _ in self._subs.get_for_topic(topic):
            msg = self._outbox.enqueue(topic, event)
            last_id = msg.id
        return last_id
