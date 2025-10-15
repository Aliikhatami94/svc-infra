from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Protocol


@dataclass
class OutboxMessage:
    id: int
    topic: str
    payload: Dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    attempts: int = 0
    processed_at: Optional[datetime] = None


class OutboxStore(Protocol):
    def enqueue(self, topic: str, payload: Dict[str, Any]) -> OutboxMessage:
        pass

    def fetch_next(self, *, topics: Optional[Iterable[str]] = None) -> Optional[OutboxMessage]:
        """Return the next unprocessed message (FIFO per-topic), or None if none available."""
        pass

    def mark_processed(self, msg_id: int) -> None:
        pass

    def mark_failed(self, msg_id: int) -> None:
        pass


class InMemoryOutboxStore:
    """Simple in-memory outbox for tests and local runs."""

    def __init__(self):
        self._seq = 0
        self._messages: List[OutboxMessage] = []

    def enqueue(self, topic: str, payload: Dict[str, Any]) -> OutboxMessage:
        self._seq += 1
        msg = OutboxMessage(id=self._seq, topic=topic, payload=dict(payload))
        self._messages.append(msg)
        return msg

    def fetch_next(self, *, topics: Optional[Iterable[str]] = None) -> Optional[OutboxMessage]:
        allowed = set(topics) if topics else None
        for msg in self._messages:
            if msg.processed_at is not None:
                continue
            if allowed is not None and msg.topic not in allowed:
                continue
            return msg
        return None

    def mark_processed(self, msg_id: int) -> None:
        for msg in self._messages:
            if msg.id == msg_id:
                msg.processed_at = datetime.now(timezone.utc)
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
        self, topic: str, payload: Dict[str, Any]
    ) -> OutboxMessage:  # pragma: no cover - skeleton
        raise NotImplementedError

    def fetch_next(
        self, *, topics: Optional[Iterable[str]] = None
    ) -> Optional[OutboxMessage]:  # pragma: no cover - skeleton
        raise NotImplementedError

    def mark_processed(self, msg_id: int) -> None:  # pragma: no cover - skeleton
        raise NotImplementedError

    def mark_failed(self, msg_id: int) -> None:  # pragma: no cover - skeleton
        raise NotImplementedError
