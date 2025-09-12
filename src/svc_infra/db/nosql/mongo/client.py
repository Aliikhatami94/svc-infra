from __future__ import annotations

from typing import AsyncGenerator

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
        _db = _client[cfg.db_name]  # prefer explicit db name from settings
    return _db


async def get_db() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    if _db is None:
        # call our own init (no FastAPI import)
        await init_mongo()
    assert _db is not None
    yield _db


async def close_mongo() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None
