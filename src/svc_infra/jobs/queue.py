from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Protocol


@dataclass
class Job:
    id: str
    name: str
    payload: Dict[str, Any]
    available_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    attempts: int = 0
    max_attempts: int = 5
    backoff_seconds: int = 60  # base backoff for retry
    last_error: Optional[str] = None


class JobQueue(Protocol):
    def enqueue(self, name: str, payload: Dict[str, Any], *, delay_seconds: int = 0) -> Job:
        pass

    def reserve_next(self) -> Optional[Job]:
        pass

    def ack(self, job_id: str) -> None:
        pass

    def fail(self, job_id: str, *, error: str | None = None) -> None:
        pass


class InMemoryJobQueue:
    """Simple in-memory queue for tests and local runs.

    Single-threaded reserve/ack/fail semantics. Not suitable for production.
    """

    def __init__(self):
        self._seq = 0
        self._jobs: list[Job] = []

    def _next_id(self) -> str:
        self._seq += 1
        return str(self._seq)

    def enqueue(self, name: str, payload: Dict[str, Any], *, delay_seconds: int = 0) -> Job:
        when = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        job = Job(id=self._next_id(), name=name, payload=dict(payload), available_at=when)
        self._jobs.append(job)
        return job

    def reserve_next(self) -> Optional[Job]:
        now = datetime.now(timezone.utc)
        for job in self._jobs:
            if job.available_at <= now and job.attempts >= 0 and job.attempts < job.max_attempts:
                job.attempts += 1
                return job
        return None

    def ack(self, job_id: str) -> None:
        self._jobs = [j for j in self._jobs if j.id != job_id]

    def fail(self, job_id: str, *, error: str | None = None) -> None:
        now = datetime.now(timezone.utc)
        for job in self._jobs:
            if job.id == job_id:
                job.last_error = error
                # Exponential backoff: base * attempts
                delay = job.backoff_seconds * max(1, job.attempts)
                if delay > 0:
                    # Add a tiny fudge so an immediate subsequent poll in ultra-fast
                    # environments (like our acceptance API) doesn't re-reserve the job.
                    # This keeps tests deterministic without impacting semantics.
                    job.available_at = now + timedelta(seconds=delay, milliseconds=250)
                else:
                    # When backoff is explicitly zero (e.g., unit tests forcing
                    # immediate retry), make the job available right away.
                    job.available_at = now
                return
