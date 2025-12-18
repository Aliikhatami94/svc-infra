"""Database operations CLI commands.

Provides CLI commands for database administration:
- wait: Wait for database to be ready before proceeding
- kill-queries: Terminate queries blocking a specific table
"""

from __future__ import annotations

import asyncio
import os
import time

import typer


def cmd_wait(
    database_url: str | None = typer.Option(
        None,
        "--url",
        "-u",
        help="Database URL; overrides env SQL_URL.",
    ),
    timeout: int = typer.Option(
        60,
        "--timeout",
        "-t",
        help="Maximum time to wait in seconds.",
    ),
    interval: float = typer.Option(
        2.0,
        "--interval",
        "-i",
        help="Time between connection attempts in seconds.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress progress messages.",
    ),
) -> None:
    """
    Wait for database to be ready.

    Attempts to connect to the database repeatedly until successful
    or timeout is reached. Useful in container startup scripts.

    Exit codes:
        0: Database is ready
        1: Timeout reached, database not ready
    """
    url = database_url or os.getenv("SQL_URL") or os.getenv("DATABASE_URL")
    if not url:
        typer.secho(
            "ERROR: No database URL. Set --url, SQL_URL, or DATABASE_URL.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    async def _wait() -> bool:
        """Async wait loop."""
        from svc_infra.health import check_database

        check = check_database(url)
        deadline = time.monotonic() + timeout
        attempt = 0

        while time.monotonic() < deadline:
            attempt += 1
            if not quiet:
                typer.echo(f"Attempt {attempt}: Connecting to database...")

            result = await check()

            if result.status == "healthy":
                if not quiet:
                    typer.secho(
                        f"✓ Database ready ({result.latency_ms:.1f}ms)",
                        fg=typer.colors.GREEN,
                    )
                return True

            if not quiet:
                msg = result.message or "Connection failed"
                typer.echo(f"  → {msg}")

            remaining = deadline - time.monotonic()
            if remaining > 0:
                await asyncio.sleep(min(interval, remaining))

        return False

    success = asyncio.run(_wait())
    if not success:
        typer.secho(
            f"ERROR: Database not ready after {timeout}s",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)


def cmd_kill_queries(
    table: str = typer.Argument(
        ...,
        help="Table name to find blocking queries for.",
    ),
    database_url: str | None = typer.Option(
        None,
        "--url",
        "-u",
        help="Database URL; overrides env SQL_URL.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show queries that would be killed without actually killing them.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Terminate immediately (pg_terminate_backend) instead of cancel (pg_cancel_backend).",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress output except errors.",
    ),
) -> None:
    """
    Kill queries blocking operations on a table.

    Finds queries that hold locks on the specified table and attempts
    to cancel or terminate them. Useful when migrations are blocked.

    By default uses pg_cancel_backend (graceful). Use --force for
    pg_terminate_backend (immediate termination).

    Examples:
        svc-infra db kill-queries users
        svc-infra db kill-queries users --dry-run
        svc-infra db kill-queries users --force
    """
    url = database_url or os.getenv("SQL_URL") or os.getenv("DATABASE_URL")
    if not url:
        typer.secho(
            "ERROR: No database URL. Set --url, SQL_URL, or DATABASE_URL.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    async def _kill_queries() -> int:
        """Find and kill blocking queries. Returns count of killed queries."""
        try:
            import asyncpg
        except ImportError:
            typer.secho(
                "ERROR: asyncpg not installed. Run: pip install asyncpg",
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)

        # Normalize URL for asyncpg
        db_url = url
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        if "+asyncpg" in db_url:
            db_url = db_url.replace("+asyncpg", "")

        try:
            conn = await asyncpg.connect(db_url)
        except Exception as e:
            typer.secho(
                f"ERROR: Failed to connect to database: {e}",
                fg=typer.colors.RED,
            )
            raise typer.Exit(1)

        try:
            # Find queries with locks on the table
            # Uses pg_stat_activity joined with pg_locks to find blocking queries
            find_query = """
                SELECT DISTINCT
                    a.pid,
                    a.usename,
                    a.application_name,
                    a.state,
                    a.query,
                    a.query_start,
                    l.locktype,
                    l.mode
                FROM pg_stat_activity a
                JOIN pg_locks l ON a.pid = l.pid
                WHERE l.relation = $1::regclass
                  AND a.pid != pg_backend_pid()
                ORDER BY a.query_start
            """

            try:
                rows = await conn.fetch(find_query, table)
            except asyncpg.UndefinedTableError:
                typer.secho(
                    f"ERROR: Table '{table}' does not exist",
                    fg=typer.colors.RED,
                )
                raise typer.Exit(1)

            if not rows:
                if not quiet:
                    typer.echo(f"No active queries found on table '{table}'")
                return 0

            if not quiet:
                typer.echo(f"Found {len(rows)} query(ies) with locks on '{table}':\n")
                for row in rows:
                    query_preview = (row["query"] or "")[:80].replace("\n", " ")
                    if len(row["query"] or "") > 80:
                        query_preview += "..."
                    typer.echo(f"  PID {row['pid']}: {query_preview}")
                    typer.echo(f"    User: {row['usename']}, State: {row['state']}")
                    typer.echo(f"    Lock: {row['mode']} on {row['locktype']}")
                    typer.echo("")

            if dry_run:
                typer.echo("Dry run - no queries killed.")
                return 0

            # Kill the queries
            kill_fn = "pg_terminate_backend" if force else "pg_cancel_backend"
            killed = 0

            for row in rows:
                pid = row["pid"]
                try:
                    result = await conn.fetchval(f"SELECT {kill_fn}($1)", pid)
                    if result:
                        killed += 1
                        if not quiet:
                            action = "Terminated" if force else "Cancelled"
                            typer.secho(f"  {action} PID {pid}", fg=typer.colors.GREEN)
                    else:
                        if not quiet:
                            typer.echo(f"  PID {pid}: already finished or permission denied")
                except Exception as e:
                    if not quiet:
                        typer.secho(f"  PID {pid}: Error - {e}", fg=typer.colors.YELLOW)

            if not quiet:
                typer.echo(f"\n{killed}/{len(rows)} queries killed.")
            return killed

        finally:
            await conn.close()

    count = asyncio.run(_kill_queries())
    if count == 0 and not dry_run:
        # Exit with 0 even if no queries found - that's success
        pass


def register(app: typer.Typer) -> None:
    """Register database operations commands with the CLI app."""
    app.command("wait")(cmd_wait)
    app.command("kill-queries")(cmd_kill_queries)
