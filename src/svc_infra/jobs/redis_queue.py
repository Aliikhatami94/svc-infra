from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, cast

from redis import Redis

from .queue import Job, JobQueue

logger = logging.getLogger(__name__)

# Lua script for atomic reserve: pop from ready, push to processing, set visibility timeout
# Returns job_id if successful, nil if queue is empty
_RESERVE_LUA = """
local ready_key = KEYS[1]
local processing_key = KEYS[2]
local processing_vt_key = KEYS[3]
local visible_at = ARGV[1]

local job_id = redis.call('RPOPLPUSH', ready_key, processing_key)
if job_id then
    redis.call('ZADD', processing_vt_key, visible_at, job_id)
end
return job_id
"""


class RedisJobQueue(JobQueue):
    """Redis-backed job queue with visibility timeout and delayed retries.

    Keys (with optional prefix):
      - {p}:ready (LIST)        ready job ids
      - {p}:processing (LIST)   in-flight job ids
      - {p}:processing_vt (ZSET) id -> visible_at (epoch seconds)
      - {p}:delayed (ZSET)      id -> available_at (epoch seconds)
      - {p}:seq (STRING)        INCR for job ids
      - {p}:job:{id} (HASH)     job fields (json payload)
      - {p}:dlq (LIST)          dead-letter job ids
    """

    def __init__(self, client: Redis, *, prefix: str = "jobs", visibility_timeout: int = 60):
        self._r = client
        self._p = prefix
        self._vt = visibility_timeout
        # Try to register Lua script for atomic reserve
        # Falls back to non-atomic if Lua scripting isn't available (e.g., fakeredis in tests)
        self._reserve_script = None
        try:
            self._reserve_script = client.register_script(_RESERVE_LUA)
        except Exception as e:
            logger.debug("Lua scripting not available, using non-atomic reserve: %s", e)

    # Key helpers
    def _k(self, name: str) -> str:
        return f"{self._p}:{name}"

    def _job_key(self, job_id: str) -> str:
        return f"{self._p}:job:{job_id}"

    # Core ops
    def enqueue(self, name: str, payload: dict, *, delay_seconds: int = 0) -> Job:
        now = datetime.now(UTC)
        job_id = str(self._r.incr(self._k("seq")))
        job = Job(id=job_id, name=name, payload=dict(payload))
        # Persist job
        data = asdict(job)
        data["payload"] = json.dumps(data["payload"])  # store payload as JSON string
        # available_at stored as ISO format
        data["available_at"] = job.available_at.isoformat()
        self._r.hset(
            self._job_key(job_id),
            mapping={k: str(v) for k, v in data.items() if v is not None},
        )
        if delay_seconds and delay_seconds > 0:
            at = int(now.timestamp()) + int(delay_seconds)
            self._r.zadd(self._k("delayed"), {job_id: at})
        else:
            # push to ready
            self._r.lpush(self._k("ready"), job_id)
        return job

    def _move_due_delayed_to_ready(self) -> None:
        now_ts = int(datetime.now(UTC).timestamp())
        ids = cast("list[Any]", self._r.zrangebyscore(self._k("delayed"), "-inf", now_ts))
        if not ids:
            return
        pipe = self._r.pipeline()
        for jid in ids:
            jid_s = jid.decode() if isinstance(jid, (bytes, bytearray)) else str(jid)
            pipe.lpush(self._k("ready"), jid_s)
            pipe.zrem(self._k("delayed"), jid_s)
        pipe.execute()

    def _requeue_timed_out_processing(self) -> None:
        now_ts = int(datetime.now(UTC).timestamp())
        ids = cast("list[Any]", self._r.zrangebyscore(self._k("processing_vt"), "-inf", now_ts))
        if not ids:
            return
        pipe = self._r.pipeline()
        for jid in ids:
            jid_s = jid.decode() if isinstance(jid, (bytes, bytearray)) else str(jid)
            pipe.lrem(self._k("processing"), 1, jid_s)
            pipe.lpush(self._k("ready"), jid_s)
            pipe.zrem(self._k("processing_vt"), jid_s)
            # clear stale visibility timestamp so next reservation can set a fresh one
            pipe.hdel(self._job_key(jid_s), "visible_at")
        pipe.execute()

    def reserve_next(self) -> Job | None:
        # opportunistically move due delayed jobs
        self._move_due_delayed_to_ready()
        # move timed-out processing jobs back to ready before reserving
        self._requeue_timed_out_processing()

        # Calculate visibility timeout BEFORE reserve to prevent race condition
        visible_at = int(datetime.now(UTC).timestamp()) + int(self._vt)

        # Try atomic reserve using Lua script if available
        # This prevents race condition where two workers could reserve the same job
        if self._reserve_script is not None:
            try:
                jid = self._reserve_script(
                    keys=[
                        self._k("ready"),
                        self._k("processing"),
                        self._k("processing_vt"),
                    ],
                    args=[visible_at],
                )
            except Exception as e:
                # Fall back to non-atomic if Lua fails at runtime
                logger.warning("Lua script failed, using non-atomic reserve: %s", e)
                jid = self._r.rpoplpush(self._k("ready"), self._k("processing"))
                if jid:
                    job_id_tmp = jid.decode() if isinstance(jid, (bytes, bytearray)) else str(jid)
                    self._r.zadd(self._k("processing_vt"), {job_id_tmp: visible_at})
        else:
            # Non-atomic fallback (for fakeredis in tests, or older Redis versions)
            jid = self._r.rpoplpush(self._k("ready"), self._k("processing"))
            if jid:
                job_id_tmp = jid.decode() if isinstance(jid, (bytes, bytearray)) else str(jid)
                self._r.zadd(self._k("processing_vt"), {job_id_tmp: visible_at})

        if not jid:
            return None
        job_id = jid.decode() if isinstance(jid, (bytes, bytearray)) else str(jid)
        key = self._job_key(job_id)
        data = cast("dict[Any, Any]", self._r.hgetall(key))
        if not data:
            # corrupted entry; ack and skip
            self._r.lrem(self._k("processing"), 1, job_id)
            self._r.zrem(self._k("processing_vt"), job_id)
            return None

        # Decode fields
        def _get(field: str, default: str | None = None) -> str | None:
            val = (
                data.get(field.encode())
                if isinstance(next(iter(data.keys())), bytes)
                else data.get(field)
            )
            if val is None:
                return default
            return val.decode() if isinstance(val, (bytes, bytearray)) else str(val)

        attempts = int(_get("attempts", "0") or "0") + 1
        max_attempts = int(_get("max_attempts", "5") or "5")
        backoff_seconds = int(_get("backoff_seconds", "60") or "60")
        name = _get("name", "") or ""
        payload_json = _get("payload", "{}") or "{}"
        try:
            payload = json.loads(payload_json)
        except Exception:  # pragma: no cover
            payload = {}
        available_at_str = _get("available_at")
        available_at = (
            datetime.fromisoformat(available_at_str) if available_at_str else datetime.now(UTC)
        )
        # If exceeded max_attempts → DLQ and skip
        if attempts > max_attempts:
            self._r.lrem(self._k("processing"), 1, job_id)
            self._r.zrem(self._k("processing_vt"), job_id)
            self._r.lpush(self._k("dlq"), job_id)
            return None
        # Update attempts count in job hash (visibility timeout already set atomically in Lua script)
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
        self._r.zrem(self._k("processing_vt"), job_id)
        self._r.delete(self._job_key(job_id))

    def fail(self, job_id: str, *, error: str | None = None) -> None:
        key = self._job_key(job_id)
        data = cast("dict[Any, Any]", self._r.hgetall(key))
        if not data:
            # nothing to do
            self._r.lrem(self._k("processing"), 1, job_id)
            return

        def _get(field: str, default: str | None = None) -> str | None:
            val = (
                data.get(field.encode())
                if isinstance(next(iter(data.keys())), bytes)
                else data.get(field)
            )
            if val is None:
                return default
            return val.decode() if isinstance(val, (bytes, bytearray)) else str(val)

        attempts = int(_get("attempts", "0") or "0")
        max_attempts = int(_get("max_attempts", "5") or "5")
        backoff_seconds = int(_get("backoff_seconds", "60") or "60")
        now_ts = int(datetime.now(UTC).timestamp())
        # DLQ if at or beyond max_attempts
        if attempts >= max_attempts:
            self._r.lrem(self._k("processing"), 1, job_id)
            self._r.zrem(self._k("processing_vt"), job_id)
            self._r.lpush(self._k("dlq"), job_id)
            return
        delay = backoff_seconds * max(1, attempts)
        available_at_ts = now_ts + delay
        mapping: dict[str, str] = {
            "last_error": error or "",
            "available_at": datetime.fromtimestamp(available_at_ts, tz=UTC).isoformat(),
        }
        self._r.hset(key, mapping=mapping)
        self._r.lrem(self._k("processing"), 1, job_id)
        self._r.zrem(self._k("processing_vt"), job_id)
        self._r.zadd(self._k("delayed"), {job_id: available_at_ts})
