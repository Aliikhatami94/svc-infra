"""Health check CLI commands.

Provides CLI commands for health checking:
- check: Check health of a URL endpoint
"""

from __future__ import annotations

import asyncio
import json

import typer


def cmd_check(
    url: str = typer.Argument(
        ...,
        help="URL of the health endpoint to check.",
    ),
    timeout: float = typer.Option(
        10.0,
        "--timeout",
        "-t",
        help="Request timeout in seconds.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output as JSON.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed response.",
    ),
) -> None:
    """
    Check health of a URL endpoint.

    Fetches the URL and reports the health status based on HTTP response.
    Expects the endpoint to return 200 for healthy status.

    Examples:
        svc-infra health check http://localhost:8000/health
        svc-infra health check http://api:8080/ready --timeout 5
        svc-infra health check http://localhost:8000/health --json

    Exit codes:
        0: Healthy (HTTP 2xx)
        1: Unhealthy or unreachable
    """

    async def _check() -> dict:
        """Perform the health check and return result."""
        from svc_infra.health import check_url

        # Create the check function with the given URL
        check_fn = check_url(url, timeout=timeout)

        # Run the check
        result = await check_fn()

        return result.to_dict()

    result = asyncio.run(_check())

    if json_output:
        typer.echo(json.dumps(result, indent=2))
    else:
        status = result["status"]
        latency = result["latency_ms"]

        if status == "healthy":
            typer.secho(f"✓ {url}", fg=typer.colors.GREEN)
            typer.echo(f"  Status: {status} ({latency:.1f}ms)")
        else:
            typer.secho(f"✗ {url}", fg=typer.colors.RED)
            typer.echo(f"  Status: {status}")
            if result.get("message"):
                typer.echo(f"  Message: {result['message']}")

        if verbose and result.get("details"):
            typer.echo("  Details:")
            for key, value in result["details"].items():
                typer.echo(f"    {key}: {value}")

    # Exit with error code if unhealthy
    if result["status"] != "healthy":
        raise typer.Exit(1)


def cmd_wait(
    url: str = typer.Argument(
        ...,
        help="URL of the health endpoint to wait for.",
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
        help="Time between checks in seconds.",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress progress messages.",
    ),
) -> None:
    """
    Wait for a health endpoint to become healthy.

    Repeatedly checks the URL until it returns a healthy response
    or timeout is reached.

    Examples:
        svc-infra health wait http://localhost:8000/health
        svc-infra health wait http://api:8080/ready --timeout 120

    Exit codes:
        0: Endpoint became healthy
        1: Timeout reached, endpoint not healthy
    """
    import time

    async def _wait() -> bool:
        """Wait loop."""
        from svc_infra.health import check_url

        check_fn = check_url(url, timeout=5.0)
        deadline = time.monotonic() + timeout
        attempt = 0

        while time.monotonic() < deadline:
            attempt += 1
            if not quiet:
                typer.echo(f"Attempt {attempt}: Checking {url}...")

            result = await check_fn()

            if result.status == "healthy":
                if not quiet:
                    typer.secho(
                        f"✓ Healthy ({result.latency_ms:.1f}ms)",
                        fg=typer.colors.GREEN,
                    )
                return True

            if not quiet:
                msg = result.message or "Unhealthy"
                typer.echo(f"  → {msg}")

            remaining = deadline - time.monotonic()
            if remaining > 0:
                await asyncio.sleep(min(interval, remaining))

        return False

    success = asyncio.run(_wait())
    if not success:
        typer.secho(
            f"ERROR: Endpoint not healthy after {timeout}s",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)


def register(app: typer.Typer) -> None:
    """Register health check commands with the CLI app."""
    app.command("check")(cmd_check)
    app.command("wait")(cmd_wait)
