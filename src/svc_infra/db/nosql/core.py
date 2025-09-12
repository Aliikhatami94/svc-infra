from __future__ import annotations

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
_REG_DB = "__infra_registry__"
_REG_COLL = "db_locks"


async def assert_db_locked(
    db, expected_db_name: str, *, service_id: str, allow_rebind: bool = False
):
    """
    Enforce one-DB-per-service lock across the cluster by storing the lock
    in a fixed registry database, not the app database.
    """
    registry = db.client.get_database(_REG_DB)
    # make sure we can upsert safely
    await registry[_REG_COLL].create_index("service_id", unique=True)

    doc = await registry[_REG_COLL].find_one({"service_id": service_id}, projection={"db_name": 1})
    if doc is None:
        await registry[_REG_COLL].insert_one(
            {"service_id": service_id, "db_name": expected_db_name}
        )
        return

    locked = doc.get("db_name")
    if locked != expected_db_name and not allow_rebind:
        raise RuntimeError(
            f"Service '{service_id}' locked to Mongo DB '{locked}', "
            f"but current target is '{expected_db_name}'. "
            f"Use allow_rebind=True (or CLI flag) if you intend to move."
        )

    if allow_rebind and locked != expected_db_name:
        await registry[_REG_COLL].update_one(
            {"service_id": service_id},
            {"$set": {"db_name": expected_db_name}},
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
    service_id: str,
    allow_rebind: bool = False,
) -> PrepareResult:
    """
    Ensure Mongo is reachable, collections exist, and indexes are applied.
    This is the async entrypoint, assuming env is resolved and client is init.
    We also enforce a cluster-wide lock on the chosen DB name for this service.
    """
    db = await anext(get_db())
    await _ping(db)

    expected_db = get_mongo_dbname_from_env(required=True)
    if db.name != expected_db:
        raise RuntimeError(f"Connected to Mongo DB '{db.name}', but env says '{expected_db}'.")

    # cluster-scope lock (in __infra_registry__)
    await assert_db_locked(db, expected_db, service_id=service_id, allow_rebind=allow_rebind)

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
    service_id: str,
    allow_rebind: bool = False,
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
            result = await prepare_mongo(
                resources=resources,
                index_builders=index_builders,
                service_id=service_id,
                allow_rebind=allow_rebind,
            )
            return {
                "ok": result.ok,
                "project_root": str(root),
                "created_collections": result.created_collections,
                "created_indexes": result.created_indexes,
            }
        finally:
            await close_mongo()

    import asyncio

    return asyncio.run(_run())
