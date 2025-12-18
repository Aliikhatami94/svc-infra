from __future__ import annotations

from typing import Any

try:
    from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

    HAS_MOTOR = True
except ImportError:  # pragma: no cover
    HAS_MOTOR = False
    AsyncIOMotorClient = Any  # type: ignore[assignment, misc]
    AsyncIOMotorDatabase = Any  # type: ignore[assignment, misc]

from .settings import MongoSettings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def _require_motor() -> None:
    """Raise ImportError if motor is not installed."""
    if not HAS_MOTOR:
        raise ImportError(
            "MongoDB support requires the 'motor' package. "
            "Install with: pip install svc-infra[mongodb]"
        )


def _client_opts(cfg: MongoSettings) -> dict:
    return {
        "appname": cfg.appname,
        "minPoolSize": cfg.min_pool_size,
        "maxPoolSize": cfg.max_pool_size,
        "uuidRepresentation": "standard",
    }


async def init_mongo(cfg: MongoSettings | None = None) -> AsyncIOMotorDatabase:
    _require_motor()
    global _client, _db
    cfg = cfg or MongoSettings()
    if _client is None:
        if not cfg.db_name:
            raise RuntimeError("MONGO_DB must be set.")
        _client = AsyncIOMotorClient(str(cfg.url), **_client_opts(cfg))
        _db = _client[cfg.db_name]
    assert _db is not None
    return _db


async def acquire_db() -> AsyncIOMotorDatabase:
    global _db
    if _db is None:
        await init_mongo()
    assert _db is not None
    return _db


async def ping_mongo() -> bool:
    db = await acquire_db()
    res = await db.command("ping")
    return bool(res and res.get("ok") == 1)


async def close_mongo() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None
