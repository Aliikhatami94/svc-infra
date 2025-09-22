#!/usr/bin/env python3
"""
Demo playground for svc-infra 🚀 caching.

Run:
    export REDIS_URL="redis://localhost:6379/0"  # or your connection
    python demo_cache_playground.py

What it does (high level):
  - Boots cache backend and probes readiness
  - Simulates a 'DB' layer with counters
  - Exercises Resource decorators (cache_read/cache_write/recache)
  - Shows tag invalidation & namespace version bump behavior
  - Simulates burst/stampede with concurrent reads
  - Prints clear step-by-step results for quick eyeballing
"""

from __future__ import annotations

import asyncio
import os
import random
import time
from typing import Any, Dict

# ---- Import svc_infra cache pieces (be tolerant if some symbols aren't present yet)
try:
    # expected package paths
    from svc_infra.cache import backend, decorators
    from svc_infra.cache.ttl import TTL_DEFAULT, TTL_LONG
except Exception:
    # Fallback for running this file side-by-side with uploaded modules (dev sandbox)
    import importlib.util
    import pathlib
    import sys

    base = pathlib.Path(__file__).resolve().parent
    for name in ("backend", "decorators", "ttl"):
        mod_path = base / f"{name}.py"
        if mod_path.exists():
            spec = importlib.util.spec_from_file_location(f"svc_infra.cache.{name}", str(mod_path))
            mod = importlib.util.module_from_spec(spec)
            sys.modules[f"svc_infra.cache.{name}"] = mod
            spec.loader.exec_module(mod)  # type: ignore
    from svc_infra.cache import backend, decorators

try:
    from cashews import cache as _cache
except ImportError as e:
    raise SystemExit(
        "Cashews is required. Install with:\n\n    pip install cashews[redis]\n"
    ) from e


# =====================================================================================
# Utilities: pretty printing
# =====================================================================================

DEFAULT_USERS = {
    "u1": {"user_id": "u1", "name": "Ada", "age": 32},
    "u2": {"user_id": "u2", "name": "Grace", "age": 29},
}


def reset_db():
    """Restore the in-memory DB to its default state."""
    _USERS.clear()
    _USERS.update({k: dict(v) for k, v in DEFAULT_USERS.items()})


async def purge_namespace_safely():
    """
    Best-effort: clear all keys in the *current* namespace so demo starts cold.
    Handles sync/async cashews builds.
    """
    dm = getattr(_cache, "delete_match", None)
    if callable(dm):
        res = dm("*")
        if asyncio.iscoroutine(res):
            await res


def hrule(title: str) -> None:
    width = 80
    print("\n" + "=" * width)
    print(title)
    print("=" * width)


def sub(rule: str) -> None:
    print(f"\n--- {rule} ---")


def kv(obj: Dict[str, Any]) -> str:
    return "{" + ", ".join(f"{k!s}: {v!r}" for k, v in obj.items()) + "}"


# =====================================================================================
# Simulated "DB" layer with hit counters
# =====================================================================================

HITS: Dict[str, int] = {}


def _hit(name: str) -> None:
    HITS[name] = HITS.get(name, 0) + 1


def reset_hits() -> None:
    HITS.clear()


def snapshot_hits() -> Dict[str, int]:
    return dict(HITS)


# "DB"
_USERS: Dict[str, Dict[str, Any]] = {
    "u1": {"user_id": "u1", "name": "Ada", "age": 32},
    "u2": {"user_id": "u2", "name": "Grace", "age": 29},
}

_ORG_MEMBERS: Dict[str, list[str]] = {
    "orgA": ["u1", "u2"],
}


async def db_get_user(user_id: str) -> Dict[str, Any]:
    _hit("get_user_profile")
    # simulate IO latency
    await asyncio.sleep(0.02)
    return dict(_USERS[user_id])


async def db_update_user(user_id: str, **patch: Any) -> Dict[str, Any]:
    _hit("update_user_profile")
    await asyncio.sleep(0.02)
    _USERS[user_id].update(patch)
    return dict(_USERS[user_id])


async def db_get_user_compact(user_id: str) -> Dict[str, Any]:
    _hit("get_user_profile_view")
    await asyncio.sleep(0.01)
    u = _USERS[user_id]
    return {"user_id": u["user_id"], "name": u["name"]}


async def db_get_org_members(org_id: str) -> list[str]:
    _hit("get_org_members")
    await asyncio.sleep(0.02)
    return list(_ORG_MEMBERS[org_id])


# =====================================================================================
# Resource wiring using your decorators (if available)
# =====================================================================================

# Your decorators API (best-effort based on the code name hints):
#   - decorators.resource(name: str, id_field: str) -> Resource
#   - Resource.cache_read(...), cache_write(...), invalidate(...), recache adapter specs, tags, etc.
#
# The demo will try to use these; if missing, it'll fall back to vanilla cashews calls.

Resource = None
try:
    Resource = decorators.resource  # type: ignore[attr-defined]
except Exception:
    pass

# If Resource is available, set up "user" and "org" resources with decorator helpers.
if Resource:
    user = Resource("user", "user_id")
    org = Resource("org", "org_id")

    # === Cached getters ===
    try:

        @user.cache_read(suffix="profile", ttl=TTL_LONG)
        async def get_user_profile(*, user_id: str) -> Dict[str, Any]:
            return await db_get_user(user_id)

    except Exception:
        # Fallback signature if your decorator expects positional id
        @user.cache_read(suffix="profile", ttl=TTL_LONG)  # type: ignore
        async def get_user_profile(user_id: str) -> Dict[str, Any]:
            return await db_get_user(user_id)

    @user.cache_read(suffix="profile_view", ttl=TTL_DEFAULT)
    async def get_user_profile_view(*, user_id: str) -> Dict[str, Any]:
        # simulate that the "view" is derived from the real profile "db" call
        # (your recache adapter demo will transform it properly)
        return await db_get_user_compact(user_id)

    @org.cache_read(suffix="members", ttl=TTL_DEFAULT)
    async def get_org_members(*, org_id: str) -> list[str]:
        return await db_get_org_members(org_id)

    # === Writer that should invalidate + recache ===
    # We’ll tell it to:
    #  - write through to DB
    #  - invalidate user:profile + user:profile_view
    #  - optionally trigger recache of both
    #
    # The exact API for recache spec may differ in your build —
    # the demo guards with try/except so runs even if unsupported.
    try:

        @user.cache_write(
            recache=[
                (get_user_profile, lambda *_, **kw: {"user_id": kw["user_id"]}),
                (get_user_profile_view, lambda *_, **kw: {"user_id": kw["user_id"]}),
            ],
            recache_max_concurrency=5,
        )
        async def update_user_profile(*, user_id: str, **patch: Any) -> dict:
            return await db_update_user(user_id, **patch)

    except Exception:

        async def update_user_profile(*, user_id: str, **patch: Any) -> Dict[str, Any]:
            # Fallback: write DB and do manual invalidation of likely keys
            res = await db_update_user(user_id, **patch)
            # Try best-effort tag/key invalidation through cashews
            # Note: your Resource likely has better helpers; this is a safe generic path.
            try:
                # Tag-based invalidation if you use tags like "user:u1"
                await _cache.invalidate(
                    "user", user_id
                )  # cashews supports patterns/tags in some configs
            except Exception:
                pass
            return res

else:
    # No Resource API; provide vanilla cashews versions so the demo still runs
    async def get_user_profile(*, user_id: str) -> Dict[str, Any]:
        key = f"user:profile:{user_id}"
        data = await _cache.get(key)
        if data is None:
            data = await db_get_user(user_id)
            await _cache.set(key, data, expire=TTL_LONG)
        return data

    async def get_user_profile_view(*, user_id: str) -> Dict[str, Any]:
        key = f"user:profile_view:{user_id}"
        data = await _cache.get(key)
        if data is None:
            data = await db_get_user_compact(user_id)
            await _cache.set(key, data, expire=TTL_DEFAULT)
        return data

    async def get_org_members(*, org_id: str) -> list[str]:
        key = f"org:members:{org_id}"
        data = await _cache.get(key)
        if data is None:
            data = await db_get_org_members(org_id)
            await _cache.set(key, data, expire=TTL_DEFAULT)
        return data

    async def update_user_profile(*, user_id: str, **patch: Any) -> Dict[str, Any]:
        res = await db_update_user(user_id, **patch)
        # naive invalidation of both keys
        await _cache.delete(f"user:profile:{user_id}")
        await _cache.delete(f"user:profile_view:{user_id}")
        return res


# =====================================================================================
# Scenarios
# =====================================================================================


async def scenario_1_basic_read_update_recache() -> None:
    hrule("SCENARIO 1: user profile read → cache → write → invalidate+recache → read")
    reset_hits()

    u1_1 = await get_user_profile(user_id="u1")
    print("get_user_profile #1:", u1_1)
    print("DB HIT COUNTERS:", snapshot_hits())

    u1_2 = await get_user_profile(user_id="u1")
    print("get_user_profile #2 (cached):", u1_2)
    print("DB HIT COUNTERS:", snapshot_hits())

    # Update name → should invalidate/recache downstream
    updated = await update_user_profile(user_id="u1", name="Grace")
    print("update_user_profile:", updated)

    u1_3 = await get_user_profile(user_id="u1")
    print("get_user_profile after update (recached):", u1_3)
    print("DB HIT COUNTERS:", snapshot_hits())


async def scenario_2_view_adapter_and_tags() -> None:
    hrule("SCENARIO 2: compact view recache + tag invalidation")
    reset_hits()

    full = await get_user_profile(user_id="u2")
    view1 = await get_user_profile_view(user_id="u2")
    print("profile full #1:", full)
    print("profile view #1:", view1)
    print("DB HIT COUNTERS:", snapshot_hits())

    # change underlying user name; expect view to refresh next read
    await update_user_profile(user_id="u2", name="Katherine")
    view2 = await get_user_profile_view(user_id="u2")
    print("profile view after update:", view2)
    print("DB HIT COUNTERS:", snapshot_hits())

    # If your impl supports explicit tag invalidation, try it:
    try:
        if Resource:
            # Most Resource systems add tags like ("user", user_id) or similar
            sub("Explicit tag invalidation for 'user:u2' (if supported)")
            # This could be a method on Resource in your codebase; adjust if needed.
            await _cache.invalidate("user", "u2")  # best-effort; may no-op if unsupported
            _ = await get_user_profile_view(user_id="u2")
            print("profile view after tag invalidation (should be fresh):", _)
            print("DB HIT COUNTERS:", snapshot_hits())
    except Exception:
        pass


async def scenario_3_org_members_cache() -> None:
    hrule("SCENARIO 3: org members cache")
    reset_hits()
    m1 = await get_org_members(org_id="orgA")
    print("members #1:", m1)
    print("DB HIT COUNTERS:", snapshot_hits())

    m2 = await get_org_members(org_id="orgA")
    print("members #2 (cached):", m2)
    print("DB HIT COUNTERS:", snapshot_hits())


async def scenario_4_burst_stampede() -> None:
    hrule("SCENARIO 4: stampede check with 25 concurrent reads (same key)")
    reset_hits()

    async def worker(i: int) -> Dict[str, Any]:
        # add a tiny jitter so some tasks land together
        await asyncio.sleep(random.random() * 0.01)
        return await get_user_profile(user_id="u1")

    # blow away the key so the first wave tests cold-miss behavior
    try:
        await _cache.delete("user:profile:u1")
    except Exception:
        pass

    results = await asyncio.gather(*(worker(i) for i in range(25)))
    # sanity: results should be identical
    uniq = {tuple(sorted(r.items())) for r in results}
    print("unique results:", len(uniq))
    print("DB HIT COUNTERS:", snapshot_hits())


async def scenario_5_namespace_bump() -> None:
    hrule("SCENARIO 5: namespace/version bump invalidation")
    reset_hits()

    # Warm a read
    _ = await get_user_profile(user_id="u1")
    print("pre-bump read DB hits:", snapshot_hits())

    # Bump the namespace version if your backend exposes it
    bumped = False
    try:
        ns_before = getattr(backend, "alias", lambda: "")()
        print("namespace before:", ns_before)

        setup_cache = getattr(backend, "setup_cache", None)
        if setup_cache:
            await maybe_await(
                setup_cache(
                    prefix=os.getenv("CACHE_PREFIX", "svc"),
                    url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
                    version="v99-demo",
                )
            )
            bumped = True

        ns_after = getattr(backend, "alias", lambda: "")()
        print("namespace after:", ns_after)
    except Exception as e:
        print("namespace bump not supported in current backend build:", e)

    # Read again — on a new namespace, this should be a cold miss → DB hit increments
    await purge_namespace_safely()

    _ = await get_user_profile(user_id="u1")
    print("post-bump read DB hits:", snapshot_hits(), "; bumped:", bumped)


async def maybe_await(value):
    """Await coroutines/futures; return plain values untouched."""
    if asyncio.iscoroutine(value) or isinstance(value, asyncio.Future):
        return await value
    return value


async def main() -> None:
    hrule("BOOTSTRAP CACHE BACKEND")
    # Use your backend.setup_cache if present, else fall back to cashews directly
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    prefix = os.getenv("CACHE_PREFIX", "svc")
    version = os.getenv("CACHE_VERSION", "v1")

    setup_cache = getattr(backend, "setup_cache", None)
    wait_ready = getattr(backend, "wait_ready", None)
    alias = getattr(backend, "alias", None)

    if setup_cache:
        # Tolerate sync or async backends
        await maybe_await(setup_cache(url=url, prefix=prefix, version=version))
    else:
        # raw cashews setup as a fallback (cashews.setup is async)
        await maybe_await(_cache.setup(url))

    # Probe readiness (backend-provided or raw get/set probe)
    if wait_ready:
        await maybe_await(wait_ready(timeout=5.0))
    else:
        probe = f"{prefix}:{version}:__probe__:{int(time.time())}"
        await _cache.set(probe, "ok", expire=5)
        assert await _cache.get(probe) == "ok"

    # alias() may be sync; don’t await
    ns = alias() if callable(alias) else f"{prefix}:{version}"
    print("cache alias/namespace:", ns)

    # NEW: start cold and with default DB values for deterministic counters
    await purge_namespace_safely()
    reset_db()

    # Execute scenarios
    await scenario_1_basic_read_update_recache()
    await scenario_2_view_adapter_and_tags()
    await scenario_3_org_members_cache()
    await scenario_4_burst_stampede()
    await scenario_5_namespace_bump()

    # Graceful shutdown
    try:
        shutdown_cache = getattr(backend, "shutdown_cache", None)
        if shutdown_cache:
            await maybe_await(shutdown_cache())
        else:
            # cashews.close is async in newer versions; guard anyway
            await maybe_await(_cache.close())
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(main())
