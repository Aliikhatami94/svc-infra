from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from .settings import MongoSettings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def _client_opts(cfg: MongoSettings) -> dict:
    return {
        "appname": cfg.appname,
        "minPoolSize": cfg.min_pool_size,
        "maxPoolSize": cfg.max_pool_size,
        "uuidRepresentation": "standard",
    }


async def init_mongo(cfg: MongoSettings | None = None) -> AsyncIOMotorDatabase:
    global _client, _db
    cfg = cfg or MongoSettings()
    if _client is None:
        _client = AsyncIOMotorClient(str(cfg.url), **_client_opts(cfg))
        _db = _client[cfg.db_name]
    return _db


async def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        await init_mongo()
    return _db  # type: ignore[return-value]


async def close_mongo():
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None
