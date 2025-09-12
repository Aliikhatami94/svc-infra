from __future__ import annotations

from typing import AsyncGenerator, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from svc_infra.db.nosql.mongo.settings import MongoSettings

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


async def initialize_mongo(url: Optional[str] = None, db_name: Optional[str] = None) -> None:
    global _client, _db
    cfg = MongoSettings()
    if url:
        cfg.url = url
    if db_name:
        cfg.db_name = db_name

    _client = AsyncIOMotorClient(
        cfg.url,
        appname=cfg.appname,
        minPoolSize=cfg.min_pool_size,
        maxPoolSize=cfg.max_pool_size,
        uuidRepresentation="standard",
    )

    # Prefer explicit db_name; only fall back to URL default if db_name is absent
    if cfg.db_name:
        _db = _client[cfg.db_name]
    else:
        _db = _client.get_default_database()
        if _db is None:
            raise RuntimeError(
                "No Mongo DB selected: set MONGO_DB or include a database in MONGO_URL."
            )


async def dispose_mongo() -> None:
    global _client, _db
    if _client:
        _client.close()
    _client = None
    _db = None


async def get_db() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    if _db is None:
        await initialize_mongo()
    assert _db is not None
    yield _db
