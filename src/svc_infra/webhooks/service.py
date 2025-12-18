from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from svc_infra.db.outbox import OutboxStore
from svc_infra.webhooks.encryption import encrypt_secret


@dataclass
class WebhookSubscription:
    topic: str
    url: str
    secret: str
    id: str = field(default_factory=lambda: uuid4().hex)


class InMemoryWebhookSubscriptions:
    def __init__(self):
        self._subs: dict[str, list[WebhookSubscription]] = {}

    def add(self, topic: str, url: str, secret: str) -> None:
        # Upsert semantics per (topic, url): if a subscription already exists
        # for this topic and URL, rotate its secret instead of adding a new row.
        # This mirrors typical real-world secret rotation flows where the
        # endpoint remains the same but the signing secret changes.
        lst = self._subs.setdefault(topic, [])
        for sub in lst:
            if sub.url == url:
                sub.secret = secret
                return
        lst.append(WebhookSubscription(topic, url, secret))

    def get_for_topic(self, topic: str) -> list[WebhookSubscription]:
        return list(self._subs.get(topic, []))


class WebhookService:
    def __init__(self, outbox: OutboxStore, subs: InMemoryWebhookSubscriptions):
        self._outbox = outbox
        self._subs = subs

    def publish(self, topic: str, payload: dict, *, version: int = 1) -> int:
        created_at = datetime.now(UTC).isoformat()
        base_event = {
            "topic": topic,
            "payload": payload,
            "version": version,
            "created_at": created_at,
        }
        # For each subscription, enqueue an outbox message with subscriber identity
        last_id = 0
        for sub in self._subs.get_for_topic(topic):
            event = dict(base_event)
            # Encrypt secret before storing in outbox for security
            encrypted_secret = encrypt_secret(sub.secret)
            msg_payload = {
                "event": event,
                "subscription": {
                    "id": sub.id,
                    "topic": sub.topic,
                    "url": sub.url,
                    "secret": encrypted_secret,
                },
            }
            msg = self._outbox.enqueue(topic, msg_payload)
            last_id = msg.id
        return last_id
