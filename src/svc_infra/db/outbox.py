from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol


@dataclass
class OutboxMessage:
    id: int
    topic: str
    payload: dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    attempts: int = 0
    processed_at: datetime | None = None


class OutboxStore(Protocol):
    def enqueue(self, topic: str, payload: dict[str, Any]) -> OutboxMessage:
        pass

    def fetch_next(self, *, topics: Iterable[str] | None = None) -> OutboxMessage | None:
        """Return the next undispatched, unprocessed message (FIFO per-topic), or None.

        Notes:
        - Messages with attempts > 0 are considered "dispatched" to the job queue and won't be re-enqueued.
        - Delivery retries are handled by the job queue worker, not by re-reading the outbox.
        """
        pass

    def mark_processed(self, msg_id: int) -> None:
        pass

    def mark_failed(self, msg_id: int) -> None:
        pass


class InMemoryOutboxStore:
    """Simple in-memory outbox for tests and local runs."""

    def __init__(self):
        self._seq = 0
        self._messages: list[OutboxMessage] = []

    def enqueue(self, topic: str, payload: dict[str, Any]) -> OutboxMessage:
        self._seq += 1
        msg = OutboxMessage(id=self._seq, topic=topic, payload=dict(payload))
        self._messages.append(msg)
        return msg

    def fetch_next(self, *, topics: Iterable[str] | None = None) -> OutboxMessage | None:
        allowed = set(topics) if topics else None
        for msg in self._messages:
            if msg.processed_at is not None:
                continue
            # skip already dispatched messages (attempts>0)
            if msg.attempts > 0:
                continue
            if allowed is not None and msg.topic not in allowed:
                continue
            return msg
        return None

    def mark_processed(self, msg_id: int) -> None:
        for msg in self._messages:
            if msg.id == msg_id:
                msg.processed_at = datetime.now(UTC)
                return

    def mark_failed(self, msg_id: int) -> None:
        for msg in self._messages:
            if msg.id == msg_id:
                msg.attempts += 1
                return


class SqlOutboxStore:
    """Skeleton for a SQL-backed outbox store.

    Implementations should:
    - INSERT on enqueue
    - SELECT FOR UPDATE SKIP LOCKED (or equivalent) to fetch next
    - UPDATE processed_at (and attempts on failure)
    """

    def __init__(self, session_factory):
        self._session_factory = session_factory

    # Placeholders to outline the API; not implemented here.
    def enqueue(
        self, topic: str, payload: dict[str, Any]
    ) -> OutboxMessage:  # pragma: no cover - skeleton
        raise NotImplementedError

    def fetch_next(
        self, *, topics: Iterable[str] | None = None
    ) -> OutboxMessage | None:  # pragma: no cover - skeleton
        raise NotImplementedError

    def mark_processed(self, msg_id: int) -> None:  # pragma: no cover - skeleton
        raise NotImplementedError

    def mark_failed(self, msg_id: int) -> None:  # pragma: no cover - skeleton
        raise NotImplementedError
