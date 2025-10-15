from __future__ import annotations

"""FastAPI integration helpers for the webhooks router.

The :func:`add_webhooks` helper wires the public router into an app and makes
sure dependency overrides share a single set of stores instead of the in-file
defaults that create a new in-memory object per request.  Callers can:

* rely on the in-memory defaults (suitable for tests / local usage);
* configure persistent stores through environment variables; or
* provide concrete instances / factories explicitly via keyword arguments.

When queue / scheduler objects are provided the helper also wires up the
standard outbox tick task and webhook delivery job handler so the caller only
needs to start their existing worker loop.
"""

import json
import logging
import os
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any, Protocol, TypeVar, overload

from fastapi import FastAPI

from svc_infra.db.inbox import InboxStore, InMemoryInboxStore
from svc_infra.db.outbox import InMemoryOutboxStore, OutboxMessage, OutboxStore
from svc_infra.jobs.builtins.outbox_processor import make_outbox_tick
from svc_infra.jobs.builtins.webhook_delivery import make_webhook_handler
from svc_infra.jobs.queue import JobQueue
from svc_infra.jobs.scheduler import InMemoryScheduler

from . import router as router_module
from .service import InMemoryWebhookSubscriptions

try:  # Optional dependency – only required when redis backends are selected.
    from redis import Redis
except Exception:  # pragma: no cover - redis is optional in most test runs.
    Redis = None  # type: ignore

logger = logging.getLogger(__name__)


T = TypeVar("T")


class _Factory(Protocol[T]):
    def __call__(self) -> T:
        ...


class RedisOutboxStore(OutboxStore):
    """Minimal Redis-backed outbox implementation used by :func:`add_webhooks`.

    The implementation is intentionally lightweight – it keeps message payloads
    in Redis hashes and a FIFO list of message identifiers.  It fulfils the
    contract expected by :func:`make_outbox_tick` while remaining simple enough
    for environments where a fully fledged SQL implementation is unavailable.
    """

    def __init__(self, client: "Redis", *, prefix: str = "webhooks:outbox"):
        if Redis is None:  # pragma: no cover - defensive guard
            raise RuntimeError("redis-py is required for RedisOutboxStore")
        self._client = client
        self._prefix = prefix.rstrip(":")

    # Redis key helpers -------------------------------------------------
    @property
    def _seq_key(self) -> str:
        return f"{self._prefix}:seq"

    @property
    def _queue_key(self) -> str:
        return f"{self._prefix}:queue"

    def _msg_key(self, msg_id: int) -> str:
        return f"{self._prefix}:msg:{msg_id}"

    # Protocol methods --------------------------------------------------
    def enqueue(self, topic: str, payload: dict[str, Any]) -> OutboxMessage:
        msg_id = int(self._client.incr(self._seq_key))
        created_at = datetime.now(timezone.utc)
        record = {
            "id": msg_id,
            "topic": topic,
            "payload": json.dumps(payload),
            "created_at": created_at.isoformat(),
            "attempts": 0,
            "processed_at": "",
        }
        self._client.hset(self._msg_key(msg_id), mapping=record)
        self._client.rpush(self._queue_key, msg_id)
        return OutboxMessage(id=msg_id, topic=topic, payload=payload, created_at=created_at)

    def fetch_next(
        self, *, topics: list[str] | tuple[str, ...] | set[str] | None = None
    ) -> OutboxMessage | None:
        allowed = set(topics) if topics else None
        ids = self._client.lrange(self._queue_key, 0, -1)
        for raw_id in ids:
            msg_id = int(raw_id)
            msg = self._client.hgetall(self._msg_key(msg_id))
            if not msg:
                continue
            topic = msg.get(b"topic")
            if topic is None:
                continue
            topic_str = topic.decode()
            if allowed is not None and topic_str not in allowed:
                continue
            attempts = int(msg.get(b"attempts", 0))
            processed_raw = msg.get(b"processed_at") or b""
            if processed_raw:
                continue
            if attempts > 0:
                continue
            payload_raw = msg.get(b"payload") or b"{}"
            payload = json.loads(payload_raw.decode())
            created_raw = msg.get(b"created_at") or ""
            created_at = (
                datetime.fromisoformat(created_raw.decode()) if created_raw else datetime.now(timezone.utc)
            )
            return OutboxMessage(
                id=msg_id,
                topic=topic_str,
                payload=payload,
                created_at=created_at,
                attempts=attempts,
            )
        return None

    def mark_processed(self, msg_id: int) -> None:
        key = self._msg_key(msg_id)
        if not self._client.exists(key):
            return
        self._client.hset(key, "processed_at", datetime.now(timezone.utc).isoformat())

    def mark_failed(self, msg_id: int) -> None:
        key = self._msg_key(msg_id)
        self._client.hincrby(key, "attempts", 1)


class RedisInboxStore(InboxStore):
    """Lightweight Redis dedupe store for webhook deliveries."""

    def __init__(self, client: "Redis", *, prefix: str = "webhooks:inbox"):
        if Redis is None:  # pragma: no cover - defensive guard
            raise RuntimeError("redis-py is required for RedisInboxStore")
        self._client = client
        self._prefix = prefix.rstrip(":")

    def _key(self, key: str) -> str:
        return f"{self._prefix}:{key}"

    def mark_if_new(self, key: str, ttl_seconds: int = 24 * 3600) -> bool:
        return bool(self._client.set(self._key(key), 1, nx=True, ex=ttl_seconds))

    def purge_expired(self) -> int:
        # Redis takes care of expirations. We return 0 to satisfy the interface.
        return 0

    def is_marked(self, key: str) -> bool:
        return bool(self._client.exists(self._key(key)))


def _is_factory(obj: Any) -> bool:
    return callable(obj) and not isinstance(obj, (str, bytes, bytearray))


def _resolve_value(value: T | _Factory[T] | None, default_factory: _Factory[T]) -> T:
    if value is None:
        return default_factory()
    if _is_factory(value):
        return value()  # type: ignore[return-value]
    return value  # type: ignore[return-value]


def _build_redis_client(env: Mapping[str, str]) -> "Redis" | None:
    if Redis is None:
        logger.warning("Redis backend requested but redis-py is not installed; falling back to in-memory stores")
        return None
    url = env.get("REDIS_URL", "redis://localhost:6379/0")
    return Redis.from_url(url)


def _default_outbox(env: Mapping[str, str]) -> OutboxStore:
    backend = (env.get("WEBHOOKS_OUTBOX") or "memory").lower()
    if backend == "redis":
        client = _build_redis_client(env)
        if client is not None:
            logger.info("Using Redis outbox store for webhooks")
            return RedisOutboxStore(client)
    elif backend == "sql":  # pragma: no cover - SQL backend is currently a placeholder
        logger.warning(
            "WEBHOOKS_OUTBOX=sql specified but SQL backend is not implemented; falling back to in-memory store"
        )
    return InMemoryOutboxStore()


def _default_inbox(env: Mapping[str, str]) -> InboxStore:
    backend = (env.get("WEBHOOKS_INBOX") or "memory").lower()
    if backend == "redis":
        client = _build_redis_client(env)
        if client is not None:
            logger.info("Using Redis inbox store for webhooks")
            return RedisInboxStore(client)
    return InMemoryInboxStore()


def _default_subscriptions() -> InMemoryWebhookSubscriptions:
    return InMemoryWebhookSubscriptions()


def _subscription_lookup(subs: InMemoryWebhookSubscriptions) -> tuple[Callable[[str], str], Callable[[str], str]]:
    def _get_url(topic: str) -> str:
        items = subs.get_for_topic(topic)
        if not items:
            raise LookupError(f"No webhook subscription for topic '{topic}'")
        return items[0].url

    def _get_secret(topic: str) -> str:
        items = subs.get_for_topic(topic)
        if not items:
            raise LookupError(f"No webhook subscription for topic '{topic}'")
        return items[0].secret

    return _get_url, _get_secret


@overload
def add_webhooks(
    app: FastAPI,
    *,
    outbox: OutboxStore | _Factory[OutboxStore] | None = ...,
    inbox: InboxStore | _Factory[InboxStore] | None = ...,
    subscriptions: InMemoryWebhookSubscriptions | _Factory[InMemoryWebhookSubscriptions] | None = ...,
    queue: JobQueue | None = ...,
    scheduler: InMemoryScheduler | None = ...,
    schedule_tick: bool = ...,
    env: Mapping[str, str] = ...,
) -> None:
    ...


def add_webhooks(
    app: FastAPI,
    *,
    outbox: OutboxStore | _Factory[OutboxStore] | None = None,
    inbox: InboxStore | _Factory[InboxStore] | None = None,
    subscriptions: InMemoryWebhookSubscriptions | _Factory[InMemoryWebhookSubscriptions] | None = None,
    queue: JobQueue | None = None,
    scheduler: InMemoryScheduler | None = None,
    schedule_tick: bool = True,
    env: Mapping[str, str] = os.environ,
) -> None:
    """Attach the shared webhooks router and stores to a FastAPI app.

    Parameters
    ----------
    app:
        The FastAPI application to configure.
    outbox / inbox / subscriptions:
        Optional instances or callables returning instances to use.  When left
        as ``None`` the helper chooses sensible defaults: in-memory stores for
        local runs or Redis-backed stores when ``WEBHOOKS_OUTBOX`` /
        ``WEBHOOKS_INBOX`` are set to ``"redis"`` and ``REDIS_URL`` is
        available.
    queue / scheduler:
        Provide these when you want :func:`make_outbox_tick` and the webhook
        delivery handler registered for you.  The tick task is scheduled every
        second by default; disable that registration by passing
        ``schedule_tick=False``.
    env:
        Mapping used to resolve environment-driven defaults.  Defaults to
        :data:`os.environ` so standard environment variables Just Work.

    Side effects
    ------------
    * ``app.include_router`` is invoked for :mod:`svc_infra.webhooks.router`.
    * ``app.dependency_overrides`` is populated so router dependencies reuse the
      shared stores.
    * References are stored on ``app.state`` for further customisation:
      ``webhooks_outbox``, ``webhooks_inbox``, ``webhooks_subscriptions``,
      ``webhooks_outbox_tick`` (when a queue is present) and
      ``webhooks_delivery_handler`` (when queue+inbox are present).
    """

    resolved_outbox = _resolve_value(outbox, lambda: _default_outbox(env))
    resolved_inbox = _resolve_value(inbox, lambda: _default_inbox(env))
    resolved_subs = _resolve_value(subscriptions, _default_subscriptions)

    app.state.webhooks_outbox = resolved_outbox
    app.state.webhooks_inbox = resolved_inbox
    app.state.webhooks_subscriptions = resolved_subs

    app.include_router(router_module.router)

    app.dependency_overrides[router_module.get_outbox] = lambda: resolved_outbox
    app.dependency_overrides[router_module.get_subs] = lambda: resolved_subs

    outbox_tick = None
    if queue is not None:
        outbox_tick = make_outbox_tick(resolved_outbox, queue)
        app.state.webhooks_outbox_tick = outbox_tick
        if scheduler is not None and schedule_tick:
            scheduler.add_task("webhooks.outbox", 1, outbox_tick)

        url_lookup, secret_lookup = _subscription_lookup(resolved_subs)
        handler = make_webhook_handler(
            outbox=resolved_outbox,
            inbox=resolved_inbox,
            get_webhook_url_for_topic=url_lookup,
            get_secret_for_topic=secret_lookup,
        )
        app.state.webhooks_delivery_handler = handler
    elif scheduler is not None and schedule_tick:
        logger.warning("Scheduler provided without queue; skipping outbox tick registration")


__all__ = ["add_webhooks"]

