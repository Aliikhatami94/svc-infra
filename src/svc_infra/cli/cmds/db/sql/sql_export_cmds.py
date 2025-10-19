from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

import typer
from sqlalchemy import text

from svc_infra.db.sql.utils import build_engine

try:  # SQLAlchemy async extras are optional
    from sqlalchemy.ext.asyncio import AsyncEngine
except Exception:  # pragma: no cover - fallback when async extras unavailable
    AsyncEngine = None  # type: ignore[assignment]


def export_tenant(
    table: str = typer.Argument(..., help="Qualified table name to export (e.g., public.items)"),
    tenant_id: str = typer.Option(..., "--tenant-id", help="Tenant id value to filter by."),
    tenant_field: str = typer.Option("tenant_id", help="Column name for tenant id filter."),
    output: Optional[Path] = typer.Option(
        None, "--output", help="Output file; defaults to stdout."
    ),
    limit: Optional[int] = typer.Option(None, help="Max rows to export."),
    database_url: Optional[str] = typer.Option(
        None, "--database-url", help="Overrides env SQL_URL for this command."
    ),
):
    """Export rows for a tenant from a given SQL table as JSON array."""
    if database_url:
        os.environ["SQL_URL"] = database_url

    url = os.getenv("SQL_URL")
    if not url:
        typer.echo("SQL_URL is required (or pass --database-url)", err=True)
        raise typer.Exit(code=2)

    engine = build_engine(url)
    rows: list[dict[str, Any]]
    query = f"SELECT * FROM {table} WHERE {tenant_field} = :tenant_id"
    if limit and limit > 0:
        query += " LIMIT :limit"

    params: dict[str, Any] = {"tenant_id": tenant_id}
    if limit and limit > 0:
        params["limit"] = int(limit)

    stmt = text(query)

    is_async_engine = AsyncEngine is not None and isinstance(engine, AsyncEngine)

    if is_async_engine:
        assert AsyncEngine is not None  # for type checkers

        async def _fetch() -> list[dict[str, Any]]:
            async with engine.connect() as conn:  # type: ignore[call-arg]
                result = await conn.execute(stmt, params)
                return [dict(row) for row in result.mappings()]

        rows = asyncio.run(_fetch())
    else:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            result = conn.execute(stmt, params)
            rows = [dict(row) for row in result.mappings()]

    data = json.dumps(rows, indent=2)
    if output:
        output.write_text(data)
        typer.echo(str(output))
    else:
        sys.stdout.write(data)


def register(app_root: typer.Typer) -> None:
    # Attach directly to the provided 'sql' group app
    app_root.command("export-tenant")(export_tenant)
