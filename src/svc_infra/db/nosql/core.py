from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import IndexModel

from svc_infra.db.nosql.mongo.client import close_mongo, get_db, init_mongo
from svc_infra.db.nosql.resource import NoSqlResource
from svc_infra.db.nosql.utils import (
    get_mongo_dbname_from_env,
    get_mongo_url_from_env,
    prepare_process_env,
)


async def _ping(db: AsyncIOMotorDatabase) -> None:
    res = await db.command("ping")
    if not res or res.get("ok") != 1:
        raise RuntimeError("Mongo ping failed")


async def _ensure_collections(db: AsyncIOMotorDatabase, names: Iterable[str]) -> None:
    existing = {c["name"] async for c in db.list_collections()}
    for name in names:
        if name not in existing:
            await db.create_collection(
                name
            )  # created lazily in Mongo only on first insert, force it


async def _apply_indexes(
    db: AsyncIOMotorDatabase, *, collection: str, indexes: Sequence[IndexModel] | None
) -> list[str]:
    if not indexes:
        return []
    return await db[collection].create_indexes(list(indexes))


@dataclass(frozen=True)
class PrepareResult:
    ok: bool
    created_collections: list[str]
    created_indexes: dict[str, list[str]]


async def prepare_mongo(
    *,
    resources: Sequence[NoSqlResource],
    index_builders: Optional[dict[str, Sequence[IndexModel]]] = None,
) -> PrepareResult:
    """
    Ensure Mongo is reachable, collections exist, and indexes are applied.

    Args:
        resources: your NoSqlResource definitions.
        index_builders: optional precomputed IndexModel sequences keyed by collection name
                        (e.g., from make_mongo_unique_indexes).
    """
    db = await get_db()
    await _ping(db)

    # 1) collections
    colls = [r.collection for r in resources]
    await _ensure_collections(db, colls)
    created_colls = colls  # create_collection is idempotent; we treat as ensured

    # 2) indexes
    created_idx: dict[str, list[str]] = {}
    for r in resources:
        idx_models = None
        if index_builders and r.collection in index_builders:
            idx_models = index_builders[r.collection]
        if idx_models:
            names = await _apply_indexes(db, collection=r.collection, indexes=idx_models)
            created_idx[r.collection] = names

    return PrepareResult(ok=True, created_collections=created_colls, created_indexes=created_idx)


# -------- high-level convenience (parity with SQL "setup_and_migrate") --------


def setup_and_prepare(
    *,
    resources: Sequence[NoSqlResource],
    index_builders: Optional[dict[str, Sequence[IndexModel]]] = None,
) -> dict:
    """
    Synchronous entrypoint to:
      • resolve env
      • init client
      • ensure collections and indexes
      • close client
    """
    root = prepare_process_env(".")
    get_mongo_url_from_env(required=True)
    # optional db name consumption (init_mongo reads it from settings internally)
    get_mongo_dbname_from_env(required=False)

    async def _run():
        await init_mongo()
        try:
            result = await prepare_mongo(resources=resources, index_builders=index_builders)
            return {
                "ok": result.ok,
                "project_root": str(root),
                "created_collections": result.created_collections,
                "created_indexes": result.created_indexes,
            }
        finally:
            await close_mongo()

    return asyncio.run(_run())
