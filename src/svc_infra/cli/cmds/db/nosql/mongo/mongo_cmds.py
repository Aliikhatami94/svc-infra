from __future__ import annotations

import importlib
import os
from typing import Any, Mapping, Optional, Sequence

import typer
from pymongo import IndexModel

# Reuse core logic (all validation/locking happens there)
from svc_infra.db.nosql.core import prepare_mongo as core_prepare_mongo
from svc_infra.db.nosql.core import setup_and_prepare as core_setup_and_prepare

# Client lifecycle for the async command
from svc_infra.db.nosql.mongo.client import close_mongo, init_mongo
from svc_infra.db.nosql.resource import NoSqlResource
from svc_infra.db.nosql.utils import prepare_process_env

# -------------------- helpers --------------------


def _apply_mongo_env(mongo_url: Optional[str], mongo_db: Optional[str]) -> None:
    """If provided, set MONGO_URL / MONGO_DB for the current process."""
    if mongo_url:
        os.environ["MONGO_URL"] = mongo_url
    if mongo_db:
        os.environ["MONGO_DB"] = mongo_db


def _load_obj(dotted: str) -> Any:
    """
    Load an object from a dotted path like:
      - 'pkg.mod:NAME'  (preferred)
      - 'pkg.mod.NAME'  (also accepted)
    """
    if ":" in dotted:
        mod_path, attr = dotted.split(":", 1)
    else:
        mod_path, _, attr = dotted.rpartition(".")
        if not mod_path:
            raise ValueError(f"Invalid dotted path: {dotted}")
    mod = importlib.import_module(mod_path)
    try:
        return getattr(mod, attr)
    except AttributeError as e:
        raise ValueError(f"Object {attr!r} not found in module {mod_path!r}") from e


def _normalize_resources(obj: Any) -> Sequence[NoSqlResource]:
    if obj is None:
        raise ValueError("No resources provided.")
    if isinstance(obj, NoSqlResource):
        return [obj]
    if isinstance(obj, (list, tuple)):
        return obj  # best-effort
    raise TypeError("resources must be a NoSqlResource or a sequence of them")


def _normalize_index_builders(obj: Any) -> dict[str, Sequence[IndexModel]]:
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
    Ensure Mongo is reachable, collections exist, and indexes are applied.

    This command is async (uses Motor). We set env overrides and bootstrap .env,
    open the client, then delegate all validation/locking to core.prepare_mongo().
    """
    _apply_mongo_env(mongo_url, mongo_db)

    # Bootstrap .env and PYTHONPATH; leave *validation* to core.
    prepare_process_env("..")

    resources = _normalize_resources(_load_obj(resources_path))
    index_builders = None
    if indexes_path:
        index_builders = _normalize_index_builders(_load_obj(indexes_path))

    import asyncio

    async def _run():
        await init_mongo()
        try:
            result = await core_prepare_mongo(
                resources=resources,
                index_builders=index_builders,
            )
            return {
                "ok": result.ok,
                "created_collections": result.created_collections,
                "created_indexes": result.created_indexes,
            }
        finally:
            await close_mongo()

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
    Synchronous, end-to-end helper that delegates entirely to core.setup_and_prepare().
    All env resolution, validation, and DB locking are handled in core.
    """
    _apply_mongo_env(mongo_url, mongo_db)

    resources = _normalize_resources(_load_obj(resources_path))
    index_builders = None
    if indexes_path:
        index_builders = _normalize_index_builders(_load_obj(indexes_path))

    res = core_setup_and_prepare(
        resources=resources,
        index_builders=index_builders,
    )
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
    Simple connectivity check (db.command('ping')).
    """
    _apply_mongo_env(mongo_url, mongo_db)

    # Keep ping lightweight; just ensure .env is loaded so MONGO_URL is available.
    prepare_process_env("..")

    import asyncio

    from svc_infra.db.nosql.mongo.client import get_db  # local import to avoid side effects

    async def _run():
        await init_mongo()
        try:
            db = await get_db()
            res = await db.command("ping")
            return {"ok": (res or {}).get("ok") == 1}
        finally:
            await close_mongo()

    res = asyncio.run(_run())
    typer.echo(res)


def register(app: typer.Typer) -> None:
    app.command("mongo-prepare")(cmd_prepare)
    app.command("mongo-setup-and-prepare")(cmd_setup_and_prepare)
    app.command("mongo-ping")(cmd_ping)
