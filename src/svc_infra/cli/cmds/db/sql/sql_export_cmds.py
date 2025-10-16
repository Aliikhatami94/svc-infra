from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

import typer

from svc_infra.db.sql.utils import build_engine

app = typer.Typer(help="SQL data export commands")


@app.command("export-tenant")
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
    # Sync connection is sufficient for export (sync engine for async URL will raise RuntimeError).
    # build_engine returns proper engine for URL type.
    rows: list[dict] = []
    query = f"SELECT * FROM {table} WHERE {tenant_field} = :tenant_id"
    if limit and limit > 0:
        query += " LIMIT :limit"

    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            params = {"tenant_id": tenant_id}
            if limit and limit > 0:
                params["limit"] = int(limit)
            res = conn.execute(
                # sqlalchemy text may not be available across sync/async variants here; use raw execute
                # This keeps dependencies light for a basic export.
                conn.execution_options(stream_results=True).execute(query, params)  # type: ignore
            )
            # However, some DBAPI/SQLAlchemy versions require text() for parameters; fallback simple path
    except Exception:
        # Fallback using simple text compile for most SQLAlchemy installs
        from sqlalchemy import text

        with engine.connect() as conn:  # type: ignore[attr-defined]
            q = text(query)
            params = {"tenant_id": tenant_id}
            if limit and limit > 0:
                params["limit"] = int(limit)
            res = conn.execute(q, params)

    # Iterate over result rows
    for row in res.mappings():  # type: ignore[name-defined]
        rows.append(dict(row))

    data = json.dumps(rows, indent=2)
    if output:
        output.write_text(data)
        typer.echo(str(output))
    else:
        sys.stdout.write(data)


def register(app_root: typer.Typer) -> None:
    app_root.add_typer(app, name="sql")
