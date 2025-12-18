"""Database operations utilities for one-off administrative tasks.

This module provides synchronous database utilities for operations that
don't fit the normal async SQLAlchemy workflow, such as:
- Waiting for database readiness at startup
- Executing maintenance SQL
- Dropping tables with lock handling
- Terminating blocking queries

These utilities use psycopg2 directly for maximum reliability in
edge cases where the ORM might not be available or appropriate.

Example:
    >>> from svc_infra.db.ops import wait_for_database, run_sync_sql
    >>>
    >>> # Wait for database before app starts
    >>> wait_for_database(timeout=30)
    >>>
    >>> # Run maintenance query
    >>> run_sync_sql("VACUUM ANALYZE my_table")
"""

from __future__ import annotations

import logging
import sys
import time
from collections.abc import Sequence
from typing import Any, cast

from .sql.utils import get_database_url_from_env

logger = logging.getLogger(__name__)

# Timeout for individual database operations (seconds)
DEFAULT_STATEMENT_TIMEOUT = 30

# Default wait-for-database settings
DEFAULT_WAIT_TIMEOUT = 30
DEFAULT_WAIT_INTERVAL = 1.0


def _flush() -> None:
    """Force flush stdout/stderr for containerized log visibility."""
    sys.stdout.flush()
    sys.stderr.flush()


def _get_connection(url: str | None = None, connect_timeout: int = 10) -> Any:
    """
    Get a psycopg2 connection.

    Args:
        url: Database URL. If None, resolved from environment.
        connect_timeout: Connection timeout in seconds.

    Returns:
        psycopg2 connection object

    Raises:
        ImportError: If psycopg2 is not installed
        RuntimeError: If no database URL is available
    """
    try:
        import psycopg2
    except ImportError as e:
        raise ImportError(
            "psycopg2 is required for db.ops utilities. Install with: pip install psycopg2-binary"
        ) from e

    if url is None:
        url = get_database_url_from_env(required=True)

    # Add connect_timeout to connection options
    return psycopg2.connect(url, connect_timeout=connect_timeout)


def wait_for_database(
    url: str | None = None,
    timeout: float = DEFAULT_WAIT_TIMEOUT,
    interval: float = DEFAULT_WAIT_INTERVAL,
    verbose: bool = True,
) -> bool:
    """
    Wait for database to be ready, with retries.

    Useful for container startup scripts where the database may not
    be immediately available.

    Args:
        url: Database URL. If None, resolved from environment.
        timeout: Maximum time to wait in seconds (default: 30)
        interval: Time between retry attempts in seconds (default: 1.0)
        verbose: If True, log progress messages

    Returns:
        True if database is ready, False if timeout reached

    Example:
        >>> # In container startup script
        >>> if not wait_for_database(timeout=60):
        ...     sys.exit(1)
        >>> # Database is ready, continue with app startup
    """
    if url is None:
        url = get_database_url_from_env(required=True)

    start = time.monotonic()
    attempt = 0

    while True:
        attempt += 1
        elapsed = time.monotonic() - start

        if elapsed >= timeout:
            if verbose:
                logger.error(f"Database not ready after {timeout}s ({attempt} attempts)")
                _flush()
            return False

        try:
            conn = _get_connection(url, connect_timeout=min(5, int(timeout - elapsed)))
            conn.close()
            if verbose:
                logger.info(f"Database ready after {elapsed:.1f}s ({attempt} attempts)")
                _flush()
            return True
        except Exception as e:
            if verbose:
                remaining = timeout - elapsed
                logger.debug(f"Database not ready ({e}), retrying... ({remaining:.0f}s remaining)")
                _flush()
            time.sleep(interval)


def run_sync_sql(
    sql: str,
    params: Sequence[Any] | None = None,
    url: str | None = None,
    timeout: int = DEFAULT_STATEMENT_TIMEOUT,
    fetch: bool = False,
) -> list[tuple[Any, ...]] | None:
    """
    Execute SQL synchronously with a statement timeout.

    This is useful for one-off administrative queries that don't fit
    the normal async SQLAlchemy workflow.

    Args:
        sql: SQL statement to execute
        params: Optional parameters for parameterized queries
        url: Database URL. If None, resolved from environment.
        timeout: Statement timeout in seconds (default: 30)
        fetch: If True, return fetched rows; if False, return None

    Returns:
        List of tuples if fetch=True, otherwise None

    Raises:
        psycopg2.Error: On database errors
        TimeoutError: If statement exceeds timeout

    Example:
        >>> # Run a maintenance query
        >>> run_sync_sql("VACUUM ANALYZE users")
        >>>
        >>> # Fetch data with timeout
        >>> rows = run_sync_sql(
        ...     "SELECT id, name FROM users WHERE active = %s",
        ...     params=(True,),
        ...     fetch=True,
        ...     timeout=10
        ... )
    """
    conn = _get_connection(url)
    try:
        with conn.cursor() as cur:
            # Set statement timeout (PostgreSQL-specific)
            cur.execute(f"SET statement_timeout = '{timeout}s'")

            if params:
                cur.execute(sql, params)
            else:
                cur.execute(sql)

            if fetch:
                return cast("list[tuple[Any, ...]]", cur.fetchall())

            conn.commit()
            return None
    finally:
        conn.close()


def kill_blocking_queries(
    table_name: str,
    url: str | None = None,
    timeout: int = DEFAULT_STATEMENT_TIMEOUT,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """
    Terminate queries blocking operations on a specific table.

    This is useful before DROP TABLE or ALTER TABLE operations that
    might be blocked by long-running queries or idle transactions.

    Args:
        table_name: Name of the table (can include schema as 'schema.table')
        url: Database URL. If None, resolved from environment.
        timeout: Statement timeout in seconds (default: 30)
        dry_run: If True, only report blocking queries without terminating

    Returns:
        List of dicts with info about terminated (or found) queries:
        [{"pid": 123, "query": "SELECT...", "state": "active", "terminated": True}]

    Example:
        >>> # Check what would be terminated
        >>> blocking = kill_blocking_queries("embeddings", dry_run=True)
        >>> print(f"Found {len(blocking)} blocking queries")
        >>>
        >>> # Actually terminate them
        >>> kill_blocking_queries("embeddings")
    """
    # Query to find blocking queries on a table
    find_blocking_sql = """
        SELECT pid, state, query, age(clock_timestamp(), query_start) as duration
        FROM pg_stat_activity
        WHERE pid != pg_backend_pid()
          AND state != 'idle'
          AND (
              query ILIKE %s
              OR query ILIKE %s
              OR query ILIKE %s
          )
        ORDER BY query_start;
    """

    # Patterns to match queries involving the table
    patterns = (
        f"%{table_name}%",
        f"%{table_name.split('.')[-1]}%",  # Just table name without schema
        f"%{table_name.replace('.', '%')}%",  # Handle schema.table pattern
    )

    conn = _get_connection(url)
    terminated: list[dict[str, Any]] = []

    try:
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = '{timeout}s'")
            cur.execute(find_blocking_sql, patterns)
            rows = cur.fetchall()

            for pid, state, query, duration in rows:
                info = {
                    "pid": pid,
                    "state": state,
                    "query": query[:200] + "..." if len(query) > 200 else query,
                    "duration": str(duration),
                    "terminated": False,
                }

                if not dry_run:
                    try:
                        cur.execute("SELECT pg_terminate_backend(%s)", (pid,))
                        info["terminated"] = True
                        logger.info(f"Terminated query PID {pid}: {query[:100]}...")
                    except Exception as e:
                        logger.warning(f"Failed to terminate PID {pid}: {e}")
                        info["error"] = str(e)

                terminated.append(info)

            conn.commit()
    finally:
        conn.close()

    _flush()
    return terminated


def drop_table_safe(
    table_name: str,
    url: str | None = None,
    timeout: int = DEFAULT_STATEMENT_TIMEOUT,
    kill_blocking: bool = True,
    if_exists: bool = True,
    cascade: bool = False,
) -> bool:
    """
    Drop a table safely with lock handling.

    Handles common issues with DROP TABLE:
    - Terminates blocking queries first (optional)
    - Uses statement timeout to avoid hanging
    - Handles 'table does not exist' gracefully

    Args:
        table_name: Name of table to drop (can include schema)
        url: Database URL. If None, resolved from environment.
        timeout: Statement timeout in seconds (default: 30)
        kill_blocking: If True, terminate blocking queries first (default: True)
        if_exists: If True, don't error if table doesn't exist (default: True)
        cascade: If True, drop dependent objects (default: False)

    Returns:
        True if table was dropped (or didn't exist), False on error

    Example:
        >>> # Drop table, killing any blocking queries first
        >>> drop_table_safe("embeddings", cascade=True)
        True
        >>>
        >>> # Safe to call even if table doesn't exist
        >>> drop_table_safe("nonexistent_table")
        True
    """
    if url is None:
        url = get_database_url_from_env(required=True)

    # Kill blocking queries first if requested
    if kill_blocking:
        blocked = kill_blocking_queries(table_name, url=url, timeout=timeout)
        if blocked:
            logger.info(f"Terminated {len(blocked)} blocking queries before DROP")
            # Brief pause to let connections clean up
            time.sleep(0.5)

    # Build DROP statement
    drop_sql = "DROP TABLE"
    if if_exists:
        drop_sql += " IF EXISTS"
    drop_sql += f" {table_name}"
    if cascade:
        drop_sql += " CASCADE"

    try:
        run_sync_sql(drop_sql, url=url, timeout=timeout)
        logger.info(f"Dropped table: {table_name}")
        _flush()
        return True
    except Exception as e:
        logger.error(f"Failed to drop table {table_name}: {e}")
        _flush()
        return False


def get_database_url(
    required: bool = True,
    normalize: bool = True,
) -> str | None:
    """
    Convenience wrapper for get_database_url_from_env().

    This is the recommended way to get the database URL, as it
    handles all common environment variable names and normalizations.

    Args:
        required: If True, raise RuntimeError when no URL is found
        normalize: If True, convert postgres:// to postgresql://

    Returns:
        Database URL string, or None if not found and not required

    Example:
        >>> url = get_database_url()
        >>> print(url)
        'postgresql://user:pass@host:5432/db'
    """
    return get_database_url_from_env(required=required, normalize=normalize)


__all__ = [
    "wait_for_database",
    "run_sync_sql",
    "kill_blocking_queries",
    "drop_table_safe",
    "get_database_url",
]
