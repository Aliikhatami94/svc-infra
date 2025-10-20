from __future__ import annotations

import os
from importlib.resources import as_file
from importlib.resources import files as pkg_files
from pathlib import Path
from typing import Dict, List

import click
import typer
from typer.core import TyperGroup

from svc_infra.app.root import resolve_project_root


def _norm(name: str) -> str:
    return name.strip().lower().replace(" ", "-").replace("_", "-")


def _discover_fs_topics(docs_dir: Path) -> Dict[str, Path]:
    topics: Dict[str, Path] = {}
    if docs_dir.exists() and docs_dir.is_dir():
        for p in sorted(docs_dir.glob("*.md")):
            if p.is_file():
                topics[_norm(p.stem)] = p
    return topics


def _discover_pkg_topics() -> Dict[str, Path]:
    """
    Discover docs shipped inside the installed package at svc_infra/docs/*,
    using importlib.resources so this works for wheels, sdists, and zipped wheels.
    """
    topics: Dict[str, Path] = {}
    try:
        docs_root = pkg_files("svc_infra").joinpath("docs")
        # docs_root is a Traversable; it may be inside a zip. Iterate safely.
        for entry in docs_root.iterdir():
            if entry.name.endswith(".md"):
                # materialize to a real tempfile path if needed
                with as_file(entry) as concrete:
                    p = Path(concrete)
                    if p.exists() and p.is_file():
                        topics[_norm(p.stem)] = p
    except Exception:
        # If the package has no docs directory, just return empty.
        pass
    return topics


def _resolve_docs_dir(ctx: click.Context) -> Path | None:
    """
    Optional override precedence:
      1) --docs-dir CLI option
      2) SVC_INFRA_DOCS_DIR env var
      3) *Only when working inside the svc-infra repo itself*: repo-root /docs
    """
    # 1) CLI option on this or parent contexts
    current: click.Context | None = ctx
    while current is not None:
        docs_dir_opt = (current.params or {}).get("docs_dir")
        if docs_dir_opt:
            path = docs_dir_opt if isinstance(docs_dir_opt, Path) else Path(docs_dir_opt)
            path = path.expanduser()
            if path.exists():
                return path
        current = current.parent

    # 2) Env var
    env_dir = os.getenv("SVC_INFRA_DOCS_DIR")
    if env_dir:
        p = Path(env_dir).expanduser()
        if p.exists():
            return p

    # 3) In-repo convenience (so `svc-infra docs` works inside this repo)
    try:
        root = resolve_project_root()
        proj_docs = root / "docs"
        if proj_docs.exists():
            return proj_docs
    except Exception:
        pass

    return None


class DocsGroup(TyperGroup):
    def list_commands(self, ctx: click.Context) -> List[str]:
        names: List[str] = list(super().list_commands(ctx) or [])
        dir_to_use = _resolve_docs_dir(ctx)
        fs = _discover_fs_topics(dir_to_use) if dir_to_use else {}
        pkg = _discover_pkg_topics()
        names.extend(fs.keys())
        names.extend([k for k in pkg.keys() if k not in fs])
        return sorted(set(names))

    def get_command(self, ctx: click.Context, name: str) -> click.Command | None:
        cmd = super().get_command(ctx, name)
        if cmd is not None:
            return cmd

        key = _norm(name)

        dir_to_use = _resolve_docs_dir(ctx)
        fs = _discover_fs_topics(dir_to_use) if dir_to_use else {}
        if key in fs:
            file_path = fs[key]

            @click.command(name=name)
            def _show_fs() -> None:
                click.echo(file_path.read_text(encoding="utf-8", errors="replace"))

            return _show_fs

        pkg = _discover_pkg_topics()
        if key in pkg:
            file_path = pkg[key]

            @click.command(name=name)
            def _show_pkg() -> None:
                click.echo(file_path.read_text(encoding="utf-8", errors="replace"))

            return _show_pkg

        return None


def register(app: typer.Typer) -> None:
    docs_app = typer.Typer(no_args_is_help=True, add_completion=False, cls=DocsGroup)

    @docs_app.callback(invoke_without_command=True)
    def _docs_options(
        docs_dir: Path | None = typer.Option(
            None,
            "--docs-dir",
            help="Path to a docs directory to read from (overrides packaged docs)",
        ),
        topic: str | None = typer.Option(None, "--topic", help="Topic to show directly"),
    ) -> None:
        if topic:
            key = _norm(topic)
            ctx = click.get_current_context()
            dir_to_use = _resolve_docs_dir(ctx)
            fs = _discover_fs_topics(dir_to_use) if dir_to_use else {}
            if key in fs:
                typer.echo(fs[key].read_text(encoding="utf-8", errors="replace"))
                raise typer.Exit(code=0)
            pkg = _discover_pkg_topics()
            if key in pkg:
                typer.echo(pkg[key].read_text(encoding="utf-8", errors="replace"))
                raise typer.Exit(code=0)
            raise typer.BadParameter(f"Unknown topic: {topic}")

    @docs_app.command("list", help="List available documentation topics")
    def list_topics() -> None:
        ctx = click.get_current_context()
        dir_to_use = _resolve_docs_dir(ctx)
        fs = _discover_fs_topics(dir_to_use) if dir_to_use else {}
        pkg = _discover_pkg_topics()

        def _print(name: str, path: Path) -> None:
            try:
                typer.echo(f"{name}\t{path}")
            except Exception:
                typer.echo(name)

        for name, path in fs.items():
            _print(name, path)
        for name, path in pkg.items():
            if name not in fs:
                _print(name, path)

    @docs_app.command("show", help="Show docs for a topic (alternative to dynamic subcommand)")
    def show(topic: str) -> None:
        key = _norm(topic)
        ctx = click.get_current_context()
        dir_to_use = _resolve_docs_dir(ctx)
        fs = _discover_fs_topics(dir_to_use) if dir_to_use else {}
        if key in fs:
            typer.echo(fs[key].read_text(encoding="utf-8", errors="replace"))
            return
        pkg = _discover_pkg_topics()
        if key in pkg:
            typer.echo(pkg[key].read_text(encoding="utf-8", errors="replace"))
            return
        raise typer.BadParameter(f"Unknown topic: {topic}")

    app.add_typer(docs_app, name="docs")
