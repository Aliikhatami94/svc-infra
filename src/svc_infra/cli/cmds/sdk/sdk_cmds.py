from __future__ import annotations

import subprocess

import typer

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Generate SDKs from OpenAPI.")


def _echo(cmd: list[str]):
    typer.echo("$ " + " ".join(cmd))


def _parse_bool(val: str | bool | None, default: bool = True) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return default
    s = str(val).strip().lower()
    if s in {"1", "true", "yes", "y"}:
        return True
    if s in {"0", "false", "no", "n"}:
        return False
    return default


@app.command("ts")
def sdk_ts(
    openapi: str = typer.Argument(..., help="Path to OpenAPI JSON"),
    outdir: str = typer.Option("sdk-ts", help="Output directory"),
    dry_run: str = typer.Option("true", help="Print commands instead of running (true/false)"),
):
    """Generate a TypeScript SDK (openapi-typescript-codegen as default)."""
    cmd = [
        "npx",
        "openapi-typescript-codegen",
        "--input",
        openapi,
        "--output",
        outdir,
    ]
    if _parse_bool(dry_run, True):
        _echo(cmd)
        return
    subprocess.check_call(cmd)
    typer.secho(f"TS SDK generated → {outdir}", fg=typer.colors.GREEN)


@app.command("py")
def sdk_py(
    openapi: str = typer.Argument(..., help="Path to OpenAPI JSON"),
    outdir: str = typer.Option("sdk-py", help="Output directory"),
    package_name: str = typer.Option("client_sdk", help="Python package name"),
    dry_run: str = typer.Option("true", help="Print commands instead of running (true/false)"),
):
    """Generate a Python SDK via openapi-generator-cli with "python" generator."""
    cmd = [
        "npx",
        "-y",
        "@openapitools/openapi-generator-cli",
        "generate",
        "-i",
        openapi,
        "-g",
        "python",
        "-o",
        outdir,
        "--additional-properties",
        f"packageName={package_name}",
    ]
    if _parse_bool(dry_run, True):
        _echo(cmd)
        return
    subprocess.check_call(cmd)
    typer.secho(f"Python SDK generated → {outdir}", fg=typer.colors.GREEN)


@app.command("postman")
def sdk_postman(
    openapi: str = typer.Argument(..., help="Path to OpenAPI JSON"),
    out: str = typer.Option("postman_collection.json", help="Output Postman collection"),
    dry_run: str = typer.Option("true", help="Print commands instead of running (true/false)"),
):
    """Convert OpenAPI to a Postman collection via openapi-to-postmanv2."""
    cmd = [
        "npx",
        "-y",
        "openapi-to-postmanv2",
        "-s",
        openapi,
        "-o",
        out,
    ]
    if _parse_bool(dry_run, True):
        _echo(cmd)
        return
    subprocess.check_call(cmd)
    typer.secho(f"Postman collection generated → {out}", fg=typer.colors.GREEN)


def register(root: typer.Typer):
    root.add_typer(app, name="sdk")
