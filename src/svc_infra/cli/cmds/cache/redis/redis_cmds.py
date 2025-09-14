from __future__ import annotations

import os

import typer

from svc_infra.cache.core import (
    check_roundtrip,
    delete_by_prefix,
    doctor,
    flush_all,
    ping,
    run_warmup,
    scan_keys,
)
from svc_infra.cache.env import get_cache_url_from_env


def _apply_cache_env(cache_url: str | None) -> None:
    if cache_url:
        os.environ["REDIS_URL"] = cache_url


def cmd_cache_ping(
    cache_url: str | None = typer.Option(
        None, "--cache-url", help="Override REDIS_URL for this run."
    ),
):
    """Ping the cache (Redis)."""
    _apply_cache_env(cache_url)

    import asyncio

    res = asyncio.run(ping())
    typer.echo(res)


def cmd_cache_doctor(
    cache_url: str | None = typer.Option(
        None, "--cache-url", help="Override REDIS_URL for this run."
    ),
):
    """Show a concise health/config snapshot with guardrail warnings."""
    _apply_cache_env(cache_url)

    import asyncio

    rep = asyncio.run(doctor())
    # print as dict for parity with other CLIs
    typer.echo(
        {
            "ok": rep.ok,
            "role": rep.role,
            "redis_version": rep.redis_version,
            "mode": rep.mode,
            "connected_clients": rep.connected_clients,
            "used_memory_human": rep.used_memory_human,
            "maxmemory_human": rep.maxmemory_human,
            "maxmemory_policy": rep.maxmemory_policy,
            "aof_enabled": rep.aof_enabled,
            "rdb_bgsave_in_progress": rep.rdb_bgsave_in_progress,
            "latency_ms": rep.latency_ms,
            "warnings": rep.warnings,
        }
    )


def cmd_cache_check(
    cache_url: str | None = typer.Option(None, "--cache-url", help="Override REDIS_URL."),
    prefix: str = typer.Option("svc", "--prefix"),
    ttl: int = typer.Option(5, "--ttl"),
):
    """Round-trip set/get with TTL under a prefix."""
    _apply_cache_env(cache_url)

    import asyncio

    res = asyncio.run(check_roundtrip(prefix=prefix, ttl=ttl))
    typer.echo(res)


def cmd_cache_keys(
    prefix: str = typer.Option(..., "--prefix", help="Prefix to scan (e.g., svc:users:)"),
    cache_url: str | None = typer.Option(None, "--cache-url", help="Override REDIS_URL."),
    count: int = typer.Option(200, "--count", help="Max sample keys to return."),
):
    """Sample keys by prefix using SCAN (non-blocking)."""
    _apply_cache_env(cache_url)

    import asyncio

    res = asyncio.run(scan_keys(prefix=prefix, count=count))
    typer.echo(res)


def cmd_cache_rm(
    prefix: str = typer.Option(..., "--prefix", help="Prefix to delete (e.g., svc:users:)"),
    limit: int | None = typer.Option(None, "--limit", help="Max keys to delete this run."),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation."),
    cache_url: str | None = typer.Option(None, "--cache-url", help="Override REDIS_URL."),
):
    """Delete keys by prefix with SCAN in batches."""
    _apply_cache_env(cache_url)
    if not yes:
        typer.confirm(f"Delete keys with prefix '{prefix}'?", abort=True)

    import asyncio

    res = asyncio.run(delete_by_prefix(prefix=prefix, limit=limit))
    typer.echo(res)


def cmd_cache_flush(
    cache_url: str | None = typer.Option(None, "--cache-url", help="Override REDIS_URL."),
    force: bool = typer.Option(False, "--force", help="Allow in non-local envs."),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation."),
):
    """Flush the current DB (DANGEROUS)."""
    _apply_cache_env(cache_url)
    if not yes:
        typer.confirm("This will FLUSH the current Redis DB. Continue?", abort=True)

    import asyncio

    res = asyncio.run(flush_all(force=force))
    typer.echo(res)


def cmd_cache_warm(
    callable_path: str = typer.Option(
        ..., "--callable", help="Project function to warm cache, e.g. 'app.cache:warmup'"
    ),
    cache_url: str | None = typer.Option(None, "--cache-url", help="Override REDIS_URL."),
):
    """Run a project-provided warmup callable (sync or async)."""
    _apply_cache_env(cache_url)

    import asyncio

    res = asyncio.run(run_warmup(callable_path))
    typer.echo(res)


def cmd_cache_setup(
    cache_url: str | None = typer.Option(None, "--cache-url", help="Resolve/validate REDIS_URL."),
):
    """
    Validate env resolution and connectivity like a one-liner 'setup'.
    """
    url = cache_url or get_cache_url_from_env(required=True)
    del url  # ensure no lints
    # piggy-back ping to ensure it actually works
    import asyncio

    res = asyncio.run(ping())
    typer.echo(res)


def register(app: typer.Typer) -> None:
    app.command("cache-ping")(cmd_cache_ping)
    app.command("cache-doctor")(cmd_cache_doctor)
    app.command("cache-check")(cmd_cache_check)
    app.command("cache-keys")(cmd_cache_keys)
    app.command("cache-rm")(cmd_cache_rm)
    app.command("cache-flush")(cmd_cache_flush)
    app.command("cache-warm")(cmd_cache_warm)
    app.command("cache-setup")(cmd_cache_setup)
