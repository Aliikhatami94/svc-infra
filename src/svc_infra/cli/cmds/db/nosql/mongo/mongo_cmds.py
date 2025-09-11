from __future__ import annotations

import importlib
import os
from typing import Any, Mapping, Optional, Sequence

import typer
from pymongo import IndexModel

from svc_infra.db.nosql.core import prepare_mongo as core_prepare_mongo
from svc_infra.db.nosql.core import setup_and_prepare as core_setup_and_prepare
from svc_infra.db.nosql.mongo.client import close_mongo, get_db, init_mongo
from svc_infra.db.nosql.resource import NoSqlResource
from svc_infra.db.nosql.utils import (
    get_mongo_dbname_from_env,
    get_mongo_url_from_env,
    prepare_process_env,
)

# -------------------- helpers --------------------


def _apply_mongo_env(mongo_url: Optional[str], mongo_db: Optional[str]) -> None:
    """If provided, set MONGO_URL / MONGO_DB for the current process."""
    if mongo_url:
        os.environ["MONGO_URL"] = mongo_url
    if mongo_db:
        os.environ["MONGO_DB"] = mongo_db


def _load_obj(dotted: str) -> Any:
    """
    Load an object from a dotted path like 'pkg.mod:NAME' or 'pkg.mod.attr'.
    """
    if ":" in dotted:
        mod_path, attr = dotted.split(":", 1)
    else:
        # allow pkg.mod.NAME as well
        mod_path, _, attr = dotted.rpartition(".")
        if not mod_path:
            raise ValueError(f"Invalid dotted path: {dotted}")
    mod = importlib.import_module(mod_path)
    try:
        return getattr(mod, attr)
    except AttributeError as e:
        raise ValueError(f"Object {attr!r} not found in module {mod_path!r}") from e


def _normalize_resources(obj: Any) -> Sequence[NoSqlResource]:
    """
    Accept a single NoSqlResource or a sequence, return a sequence.
    """
    if obj is None:
        raise ValueError("No resources provided.")
    if isinstance(obj, NoSqlResource):
        return [obj]
    if isinstance(obj, (list, tuple)):
        # best-effort runtime check
        return obj  # type: ignore[return-value]
    raise TypeError("resources must be a NoSqlResource or a sequence of them")


def _normalize_index_builders(obj: Any) -> dict[str, Sequence[IndexModel]]:
    """
    Accept a mapping {collection_name: [IndexModel, ...]} or a callable returning it.
    """
    if obj is None:
        return {}
    if callable(obj):
        obj = obj()
    if isinstance(obj, Mapping):
        return dict(obj)  # type: ignore[return-value]
    raise TypeError("index_builders must be a mapping or a zero-arg callable returning a mapping")


# -------------------- commands --------------------


def cmd_prepare(
    resources_path: str = typer.Option(
        ...,
        "--resources",
        help="Dotted path to NoSqlResource(s). e.g. 'app.db.mongo:RESOURCES' or 'app.db.mongo:USER_RESOURCE'",
    ),
    indexes_path: Optional[str] = typer.Option(
        None,
        "--index-builders",
        help="Dotted path to a dict[str, list[IndexModel]] or a zero-arg callable returning it.",
    ),
    mongo_url: Optional[str] = typer.Option(
        None, "--mongo-url", help="Overrides env MONGO_URL for this command."
    ),
    mongo_db: Optional[str] = typer.Option(
        None, "--mongo-db", help="Overrides env MONGO_DB for this command."
    ),
):
    """
    Ensure Mongo is reachable, collections exist, and indexes are applied.
    """
    _apply_mongo_env(mongo_url, mongo_db)

    # Resolve env (dotenv, PYTHONPATH bootstrap)
    prepare_process_env("..")
    # Validate we can resolve URL/DB (optional DB name)
    get_mongo_url_from_env(required=True)
    get_mongo_dbname_from_env(required=False)

    resources_obj = _load_obj(resources_path)
    resources = _normalize_resources(resources_obj)

    index_builders = None
    if indexes_path:
        index_builders_obj = _load_obj(indexes_path)
        index_builders = _normalize_index_builders(index_builders_obj)

    # Run fully async but keep this command async-friendly
    async def _run():
        await init_mongo()
        try:
            result = await core_prepare_mongo(resources=resources, index_builders=index_builders)
            return {
                "ok": result.ok,
                "created_collections": result.created_collections,
                "created_indexes": result.created_indexes,
            }
        finally:
            await close_mongo()

    import asyncio

    res = asyncio.run(_run())
    typer.echo(res)


def cmd_setup_and_prepare(
    resources_path: str = typer.Option(
        ...,
        "--resources",
        help="Dotted path to NoSqlResource(s). e.g. 'app.db.mongo:RESOURCES'",
    ),
    indexes_path: Optional[str] = typer.Option(
        None,
        "--index-builders",
        help="Dotted path to a dict[str, list[IndexModel]] or a zero-arg callable returning it.",
    ),
    mongo_url: Optional[str] = typer.Option(
        None, "--mongo-url", help="Overrides env MONGO_URL for this command."
    ),
    mongo_db: Optional[str] = typer.Option(
        None, "--mongo-db", help="Overrides env MONGO_DB for this command."
    ),
):
    """
    Synchronous end-to-end helper:
      • resolve env
      • init client
      • ensure collections and indexes
      • close client
    """
    _apply_mongo_env(mongo_url, mongo_db)
    resources = _normalize_resources(_load_obj(resources_path))
    index_builders = None
    if indexes_path:
        index_builders = _normalize_index_builders(_load_obj(indexes_path))

    res = core_setup_and_prepare(resources=resources, index_builders=index_builders)
    typer.echo(res)


def cmd_ping(
    mongo_url: Optional[str] = typer.Option(
        None, "--mongo-url", help="Overrides env MONGO_URL for this command."
    ),
    mongo_db: Optional[str] = typer.Option(
        None, "--mongo-db", help="Overrides env MONGO_DB for this command."
    ),
):
    """
    Simple connectivity check to Mongo (runs db.command('ping')).
    """
    _apply_mongo_env(mongo_url, mongo_db)
    prepare_process_env("..")
    get_mongo_url_from_env(required=True)
    get_mongo_dbname_from_env(required=False)

    async def _run():
        await init_mongo()
        try:
            db = await get_db()
            res = await db.command("ping")
            return {"ok": (res or {}).get("ok") == 1}
        finally:
            await close_mongo()

    import asyncio

    res = asyncio.run(_run())
    typer.echo(res)


def register(app: typer.Typer) -> None:
    """
    Register Mongo CLI commands on the given Typer app.
    Commands:
      • mongo-prepare
      • mongo-setup-and-prepare
      • mongo-ping
    """
    app.command("mongo-prepare")(cmd_prepare)
    app.command("mongo-setup-and-prepare")(cmd_setup_and_prepare)
    app.command("mongo-ping")(cmd_ping)
