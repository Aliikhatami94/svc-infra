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
    # Motor: returns list[str], must be awaited
    existing = set(await db.list_collection_names())
    for name in names:
        if name not in existing:
            # Mongo only creates a collection on first insert; we force creation
            await db.create_collection(name)


async def _apply_indexes(
    db: AsyncIOMotorDatabase, *, collection: str, indexes: Sequence[IndexModel] | None
) -> list[str]:
    if not indexes:
        return []
    return await db[collection].create_indexes(list(indexes))


# collection + doc used to "lock" the chosen DB name for this app
_META_COLL = "__infra_meta"
_DB_LOCK_ID = "db_lock"  # stable _id


async def assert_db_locked(
    db: AsyncIOMotorDatabase, expected_db_name: str, *, allow_rebind: bool = False
) -> None:
    """
    Ensure this app only uses a single Mongo database.
    On first run: write the lock doc.
    Thereafter: if the existing lock's db_name != expected_db_name, raise.
    Set allow_rebind=True only in a controlled migration.
    """
    current = await db[_META_COLL].find_one({"_id": _DB_LOCK_ID}, projection={"db_name": 1})
    if current is None:
        # first run in this database — write the lock
        await db[_META_COLL].insert_one({"_id": _DB_LOCK_ID, "db_name": expected_db_name})
        return

    locked = current.get("db_name")
    if locked != expected_db_name and not allow_rebind:
        raise RuntimeError(
            f"This service is locked to Mongo DB '{locked}', but your env points to '{expected_db_name}'. "
            "If you truly need to switch databases, run setup with an explicit override (allow_rebind=True) "
            "and perform a data migration, or start a separate service instance."
        )


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

    # --- enforce one-db-per-service guardrail ---
    expected_db = get_mongo_dbname_from_env(required=True)  # <— now required
    # db.name is the actual database we’re connected to
    if db.name != expected_db:
        # This catches mis-wiring of client construction vs env, before the lock
        raise RuntimeError(f"Connected to Mongo DB '{db.name}', but env says '{expected_db}'.")

    await assert_db_locked(db, expected_db)

    # 1) collections
    colls = [r.resolved_collection() for r in resources]
    await _ensure_collections(db, colls)
    created_colls = colls

    # 2) indexes
    created_idx: dict[str, list[str]] = {}
    for r in resources:
        coll = r.resolved_collection()
        idx_models = index_builders.get(coll) if index_builders else None
        if idx_models:
            names = await _apply_indexes(db, collection=coll, indexes=idx_models)
            created_idx[coll] = names

    return PrepareResult(ok=True, created_collections=created_colls, created_indexes=created_idx)


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
    get_mongo_dbname_from_env(required=True)

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
