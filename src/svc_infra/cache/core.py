from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Optional

from svc_infra.cache.env import get_cache_url_from_env
from svc_infra.cache.redis.client import acquire_redis, close_redis, init_redis


def _current_env() -> str:
    return (os.getenv("APP_ENV") or os.getenv("ENV") or "local").lower()


async def ping() -> dict:
    """Connectivity check."""
    await init_redis(get_cache_url_from_env(required=True))
    try:
        r = await acquire_redis()
        pong = await r.ping()
        return {"ok": bool(pong)}
    finally:
        await close_redis()


@dataclass(frozen=True)
class DoctorReport:
    ok: bool
    role: str | None
    redis_version: str | None
    mode: str | None
    connected_clients: int | None
    used_memory_human: str | None
    maxmemory_human: str | None
    maxmemory_policy: str | None
    aof_enabled: int | None
    rdb_bgsave_in_progress: int | None
    latency_ms: float | None
    warnings: list[str]


async def doctor() -> DoctorReport:
    """
    Gather a concise health/config snapshot and provide guardrail warnings.
    """
    await init_redis(get_cache_url_from_env(required=True))
    try:
        r = await acquire_redis()

        t0 = time.perf_counter()
        await r.ping()
        latency_ms = (time.perf_counter() - t0) * 1000

        info = await r.info()
        conf = {}
        try:
            for k in ("maxmemory", "maxmemory-policy"):
                v = await r.config_get(k)
                conf.update(v or {})
        except Exception:
            pass  # CONFIG may be disabled

        warnings: list[str] = []
        env = _current_env()

        # TLS/auth hints (best-effort; depends on deployment)
        # redis-py doesn't expose obvious TLS flags; we nudge based on URL scheme
        url = os.getenv("REDIS_URL", "")
        if env not in {"local", "dev", "development"}:
            if url and url.startswith("redis://"):
                warnings.append("Non-TLS redis:// in non-local environment.")
            if not (os.getenv("REDIS_PASSWORD") or ("@" in url and "://" in url)):
                # heuristic: passwordless if neither env nor URL contains creds
                warnings.append("No password detected for Redis in non-local environment.")

        role = info.get("role") if isinstance(info.get("role"), str) else str(info.get("role"))
        maxmem = int(conf.get("maxmemory") or 0)
        if maxmem == 0 and env not in {"local", "dev", "development"}:
            warnings.append("maxmemory is 0 (unbounded). Set a limit and an eviction policy.")

        policy = conf.get("maxmemory-policy") or info.get("maxmemory_policy")
        if policy in {None, "noeviction"} and env not in {"local", "dev", "development"}:
            warnings.append(
                "Eviction policy is 'noeviction' or unset. Consider 'allkeys-lru' or similar."
            )

        return DoctorReport(
            ok=True,
            role=role,
            redis_version=str(info.get("redis_version")),
            mode=str(info.get("redis_mode")),
            connected_clients=int(info.get("connected_clients", 0)),
            used_memory_human=str(info.get("used_memory_human")),
            maxmemory_human=str(info.get("maxmemory_human")),
            maxmemory_policy=str(policy),
            aof_enabled=int(info.get("aof_enabled", 0)),
            rdb_bgsave_in_progress=int(info.get("rdb_bgsave_in_progress", 0)),
            latency_ms=latency_ms,
            warnings=warnings,
        )
    finally:
        await close_redis()


async def check_roundtrip(prefix: str = "svc", ttl: int = 5) -> dict:
    """
    Smoke test: set/get with TTL under a namespaced key.
    """
    await init_redis(get_cache_url_from_env(required=True))
    try:
        r = await acquire_redis()
        key = f"{prefix}:_check:{int(time.time())}"
        val = b"ok"
        await r.set(key, val, ex=ttl)
        got = await r.get(key)
        return {"ok": got == val, "key": key, "ttl": ttl}
    finally:
        await close_redis()


async def scan_keys(prefix: str, count: int = 100) -> dict:
    """
    Non-blocking SCAN for a few keys under a prefix.
    """
    await init_redis(get_cache_url_from_env(required=True))
    try:
        r = await acquire_redis()
        pattern = f"{prefix}*"
        cursor = 0
        found: list[str] = []
        while True:
            cursor, chunk = await r.scan(cursor=cursor, match=pattern, count=count)
            found.extend(
                [k.decode() if isinstance(k, (bytes, bytearray)) else str(k) for k in chunk]
            )
            if cursor == 0 or len(found) >= count:
                break
        return {
            "ok": True,
            "prefix": prefix,
            "sample": found[:count],
            "returned": len(found[:count]),
        }
    finally:
        await close_redis()


async def delete_by_prefix(prefix: str, *, limit: Optional[int] = None) -> dict:
    """
    Delete keys by prefix using SCAN; limit controls max deletions this run.
    """
    await init_redis(get_cache_url_from_env(required=True))
    try:
        r = await acquire_redis()
        pattern = f"{prefix}*"
        cursor = 0
        total = 0
        while True:
            cursor, chunk = await r.scan(cursor=cursor, match=pattern, count=1000)
            if not chunk:
                if cursor == 0:
                    break
                continue
            # delete in batches
            batch: list[bytes] = []
            for k in chunk:
                batch.append(k)
                if limit and (total + len(batch)) >= limit:
                    break
            if batch:
                total += int(await r.delete(*batch))
            if limit and total >= limit:
                break
            if cursor == 0:
                break
        return {"ok": True, "deleted": total, "prefix": prefix}
    finally:
        await close_redis()


async def flush_all(*, force: bool = False) -> dict:
    """
    Flush DB (dangerous). Guard by environment and 'force'.
    """
    env = _current_env()
    if env not in {"local", "dev", "development"} and not force:
        raise RuntimeError("Refusing to FLUSHALL outside local/dev without --force.")
    await init_redis(get_cache_url_from_env(required=True))
    try:
        r = await acquire_redis()
        await r.flushdb()  # safer than FLUSHALL (only current DB)
        return {"ok": True, "action": "flushdb", "env": env}
    finally:
        await close_redis()


async def run_warmup(callable_path: str) -> dict:
    """
    Import and run a project-provided warmup function: 'pkg.mod:warmup'.
    The callable can be sync or async.
    """
    import importlib

    mod_path, _, attr = callable_path.partition(":")
    if not attr:
        # also allow dotted form pkg.mod.func
        mod_path, _, attr = callable_path.rpartition(".")
    if not mod_path or not attr:
        raise ValueError(f"Invalid callable path: {callable_path}")

    mod = importlib.import_module(mod_path)
    fn = getattr(mod, attr, None)
    if not callable(fn):
        raise ValueError(f"{callable_path!r} is not a callable")

    await init_redis(get_cache_url_from_env(required=True))
    try:
        r = await acquire_redis()
        res: Any
        try:
            maybe = fn(r)  # pass raw Redis for flexibility (or your own service if preferred)
            if hasattr(maybe, "__await__"):
                res = await maybe  # type: ignore[func-returns-value]
            else:
                res = maybe
        finally:
            # nothing else
            pass
        return {"ok": True, "result": str(res)[:500]}
    finally:
        await close_redis()
