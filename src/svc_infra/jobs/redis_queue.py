from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Dict, Optional

from redis import Redis

from .queue import Job, JobQueue


class RedisJobQueue(JobQueue):
    """Redis-backed job queue with visibility timeout and delayed retries.

    Keys (with optional prefix):
      - {p}:ready (LIST)        ready job ids
      - {p}:processing (LIST)   in-flight job ids
      - {p}:delayed (ZSET)      id -> available_at (epoch seconds)
      - {p}:seq (STRING)        INCR for job ids
      - {p}:job:{id} (HASH)     job fields (json payload)
      - {p}:dlq (LIST)          dead-letter job ids
    """

    def __init__(self, client: Redis, *, prefix: str = "jobs", visibility_timeout: int = 60):
        self._r = client
        self._p = prefix
        self._vt = visibility_timeout

    # Key helpers
    def _k(self, name: str) -> str:
        return f"{self._p}:{name}"

    def _job_key(self, job_id: str) -> str:
        return f"{self._p}:job:{job_id}"

    # Core ops
    def enqueue(self, name: str, payload: Dict, *, delay_seconds: int = 0) -> Job:
        now = datetime.now(timezone.utc)
        job_id = str(self._r.incr(self._k("seq")))
        job = Job(id=job_id, name=name, payload=dict(payload))
        # Persist job
        data = asdict(job)
        data["payload"] = json.dumps(data["payload"])  # store payload as JSON string
        # available_at stored as ISO format
        data["available_at"] = job.available_at.isoformat()
        self._r.hset(
            self._job_key(job_id), mapping={k: str(v) for k, v in data.items() if v is not None}
        )
        if delay_seconds and delay_seconds > 0:
            at = int(now.timestamp()) + int(delay_seconds)
            self._r.zadd(self._k("delayed"), {job_id: at})
        else:
            # push to ready
            self._r.lpush(self._k("ready"), job_id)
        return job

    def _move_due_delayed_to_ready(self) -> None:
        now_ts = int(datetime.now(timezone.utc).timestamp())
        ids = self._r.zrangebyscore(self._k("delayed"), "-inf", now_ts)
        if not ids:
            return
        pipe = self._r.pipeline()
        for jid in ids:
            jid_s = jid.decode() if isinstance(jid, (bytes, bytearray)) else str(jid)
            pipe.lpush(self._k("ready"), jid_s)
            pipe.zrem(self._k("delayed"), jid_s)
        pipe.execute()

    def reserve_next(self) -> Optional[Job]:
        # opportunistically move due delayed jobs
        self._move_due_delayed_to_ready()
        jid = self._r.rpoplpush(self._k("ready"), self._k("processing"))
        if not jid:
            return None
        job_id = jid.decode() if isinstance(jid, (bytes, bytearray)) else str(jid)
        key = self._job_key(job_id)
        data = self._r.hgetall(key)
        if not data:
            # corrupted entry; ack and skip
            self._r.lrem(self._k("processing"), 1, job_id)
            return None

        # Decode fields
        def _get(field: str, default: Optional[str] = None) -> Optional[str]:
            val = (
                data.get(field.encode())
                if isinstance(next(iter(data.keys())), bytes)
                else data.get(field)
            )
            if val is None:
                return default
            return val.decode() if isinstance(val, (bytes, bytearray)) else str(val)

        attempts = int(_get("attempts", "0")) + 1
        max_attempts = int(_get("max_attempts", "5"))
        backoff_seconds = int(_get("backoff_seconds", "60"))
        name = _get("name", "") or ""
        payload_json = _get("payload", "{}") or "{}"
        try:
            payload = json.loads(payload_json)
        except Exception:  # pragma: no cover
            payload = {}
        available_at_str = _get("available_at")
        available_at = (
            datetime.fromisoformat(available_at_str)
            if available_at_str
            else datetime.now(timezone.utc)
        )
        # If exceeded max_attempts → DLQ and skip
        if attempts > max_attempts:
            self._r.lrem(self._k("processing"), 1, job_id)
            self._r.lpush(self._k("dlq"), job_id)
            return None
        # Update attempts and visibility timeout
        visible_at = int(datetime.now(timezone.utc).timestamp()) + int(self._vt)
        self._r.hset(key, mapping={"attempts": attempts, "visible_at": visible_at})
        return Job(
            id=job_id,
            name=name,
            payload=payload,
            available_at=available_at,
            attempts=attempts,
            max_attempts=max_attempts,
            backoff_seconds=backoff_seconds,
        )

    def ack(self, job_id: str) -> None:
        self._r.lrem(self._k("processing"), 1, job_id)
        self._r.delete(self._job_key(job_id))

    def fail(self, job_id: str, *, error: str | None = None) -> None:
        key = self._job_key(job_id)
        data = self._r.hgetall(key)
        if not data:
            # nothing to do
            self._r.lrem(self._k("processing"), 1, job_id)
            return

        def _get(field: str, default: Optional[str] = None) -> Optional[str]:
            val = (
                data.get(field.encode())
                if isinstance(next(iter(data.keys())), bytes)
                else data.get(field)
            )
            if val is None:
                return default
            return val.decode() if isinstance(val, (bytes, bytearray)) else str(val)

        attempts = int(_get("attempts", "0"))
        max_attempts = int(_get("max_attempts", "5"))
        backoff_seconds = int(_get("backoff_seconds", "60"))
        now_ts = int(datetime.now(timezone.utc).timestamp())
        # DLQ if at or beyond max_attempts
        if attempts >= max_attempts:
            self._r.lrem(self._k("processing"), 1, job_id)
            self._r.lpush(self._k("dlq"), job_id)
            return
        delay = backoff_seconds * max(1, attempts)
        available_at_ts = now_ts + delay
        mapping = {
            "last_error": error or "",
            "available_at": datetime.fromtimestamp(available_at_ts, tz=timezone.utc).isoformat(),
        }
        self._r.hset(key, mapping=mapping)
        self._r.lrem(self._k("processing"), 1, job_id)
        self._r.zadd(self._k("delayed"), {job_id: available_at_ts})
