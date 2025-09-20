from __future__ import annotations

import time

from .backend import instance


async def ping() -> dict:
    # roundtrip set/get
    key = "svc:_health:ping"
    await instance().set(key, "ok", expire=5)
    v = await instance().get(key)
    return {"ok": v == "ok"}


async def roundtrip(prefix: str = "svc", ttl: int = 5) -> dict:
    k = f"{prefix}:_check:{int(time.time())}"
    await instance().set(k, "ok", expire=ttl)
    v = await instance().get(k)
    return {"ok": v == "ok", "key": k, "ttl": ttl}
