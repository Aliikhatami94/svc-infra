from __future__ import annotations

import importlib
import os
from typing import Any, Optional, Sequence

import typer

# Reuse core logic (all validation/locking happens there)
from svc_infra.db.nosql.core import prepare_mongo, setup_and_prepare

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


# -------------------- commands --------------------


def cmd_prepare(
    resources_path: str = typer.Option(
        ...,
        "--resources",
        help="Dotted path to NoSqlResource(s). e.g. 'app.db.mongo:RESOURCES'",
    ),
    mongo_url: Optional[str] = typer.Option(
        None, "--mongo-url", help="Overrides env MONGO_URL for this command."
    ),
    mongo_db: Optional[str] = typer.Option(
        None, "--mongo-db", help="Overrides env MONGO_DB for this command."
    ),
    service_id: Optional[str] = typer.Option(
        None,
        "--service-id",
        help="Stable ID for this service/app. Defaults to top-level module name.",
    ),
    allow_rebind: bool = typer.Option(
        False, "--allow-rebind", help="Permit moving to a different DB."
    ),
):
    """
    Ensure Mongo is reachable, collections exist, and indexes (from each NoSqlResource.indexes)
    are applied.

    This command is async (uses Motor). We set env overrides and bootstrap .env,
    open the client, then delegate validation/locking to core.prepare_mongo().
    """
    _apply_mongo_env(mongo_url, mongo_db)
    prepare_process_env(".")
    resources = _normalize_resources(_load_obj(resources_path))
    sid = service_id or _default_service_id_from_resources_path(resources_path)

    import asyncio

    async def _run():
        await init_mongo()
        try:
            result = await prepare_mongo(
                resources=resources,
                service_id=sid,
                allow_rebind=allow_rebind,
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


def _default_service_id_from_resources_path(resources_path: str) -> str:
    # e.g. "apiframeworks_api.mongo.resources:RESOURCES" -> "apiframeworks_api"
    mod = resources_path.split(":", 1)[0]
    top = mod.split(".", 1)[0]
    return top or "service"


def cmd_setup_and_prepare(
    resources_path: str = typer.Option(
        ...,
        "--resources",
        help="Dotted path to NoSqlResource(s). e.g. 'app.db.mongo:RESOURCES'",
    ),
    mongo_url: Optional[str] = typer.Option(
        None, "--mongo-url", help="Overrides env MONGO_URL for this command."
    ),
    mongo_db: Optional[str] = typer.Option(
        None, "--mongo-db", help="Overrides env MONGO_DB for this command."
    ),
    service_id: Optional[str] = typer.Option(
        None,
        "--service-id",
        help="Stable ID for this service/app. Defaults to top-level module name.",
    ),
    allow_rebind: bool = typer.Option(
        False, "--allow-rebind", help="Permit moving to a different DB."
    ),
):
    """
    Synchronous, end-to-end helper that delegates entirely to core.setup_and_prepare().
    All env resolution, validation, and DB locking are handled in core.
    """
    _apply_mongo_env(mongo_url, mongo_db)
    resources = _normalize_resources(_load_obj(resources_path))
    sid = service_id or _default_service_id_from_resources_path(resources_path)

    res = setup_and_prepare(
        resources=resources,
        service_id=sid,
        allow_rebind=allow_rebind,
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
    prepare_process_env(".")

    import asyncio

    from svc_infra.db.nosql.mongo.client import acquire_db  # local import to avoid side effects

    async def _run():
        await init_mongo()
        try:
            db = await acquire_db()
            res = await db.command("ping")
            return {"ok": (res or {}).get("ok") == 1}
        finally:
            await close_mongo()

    res = asyncio.run(_run())
    typer.echo(res)


def register(app: typer.Typer) -> None:
    # Attach to 'mongo' group app
    app.command("prepare")(cmd_prepare)
    app.command("setup-and-prepare")(cmd_setup_and_prepare)
    app.command("ping")(cmd_ping)
