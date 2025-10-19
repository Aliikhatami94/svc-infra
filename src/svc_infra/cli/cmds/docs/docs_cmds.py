from __future__ import annotations

import os
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from typing import Dict, List

import click
import typer
from typer.core import TyperGroup

from svc_infra.app.root import resolve_project_root


def _discover_fs_topics(docs_dir: Path) -> Dict[str, Path]:
    topics: Dict[str, Path] = {}
    if docs_dir.exists() and docs_dir.is_dir():
        for p in sorted(docs_dir.glob("*.md")):
            if p.is_file():
                topics[p.stem.replace(" ", "-")] = p
    return topics


def _discover_pkg_topics() -> Dict[str, Path]:
    """Discover docs packaged under 'docs/' in the installed distribution.

    This lets 'svc-infra docs' work from external projects that don't have a
    local docs/ directory by falling back to files shipped in the wheel.
    """
    topics: Dict[str, Path] = {}
    try:
        dist = distribution("svc-infra")
    except PackageNotFoundError:
        return topics

    files = getattr(dist, "files", None) or []
    for f in files:
        # f is a PackagePath; string form like 'docs/topic.md'
        s = str(f)
        if not s.startswith("docs/") or not s.endswith(".md"):
            continue
        name = Path(s).stem.replace(" ", "-")
        try:
            abs_path = dist.locate_file(f)
            # Ensure it's a file before adding
            abs_p = Path(abs_path)
            if abs_p.exists() and abs_p.is_file():
                topics[name] = abs_p
        except Exception:
            # best-effort; skip unreadable entries
            continue
    return topics


def _resolve_docs_dir(ctx: click.Context) -> Path | None:
    # CLI option takes precedence; walk up parent contexts because Typer
    # executes subcommands in child contexts that do not inherit params.
    current: click.Context | None = ctx
    while current is not None:
        docs_dir = (current.params or {}).get("docs_dir")
        if docs_dir:
            path = docs_dir if isinstance(docs_dir, Path) else Path(docs_dir)
            path = path.expanduser()
            if path.exists():
                return path
        current = current.parent
    # Env var next
    env_dir = os.getenv("SVC_INFRA_DOCS_DIR")
    if env_dir:
        p = Path(env_dir).expanduser()
        if p.exists():
            return p
    # Project docs
    root = resolve_project_root()
    proj_docs = root / "docs"
    if proj_docs.exists():
        return proj_docs
    return None


class DocsGroup(TyperGroup):
    def list_commands(self, ctx: click.Context) -> List[str]:
        names: List[str] = list(super().list_commands(ctx) or [])
        dir_to_use = _resolve_docs_dir(ctx)
        fs = _discover_fs_topics(dir_to_use) if dir_to_use else {}
        pkg = _discover_pkg_topics()
        # FS topics win on conflicts; add both for visibility
        names.extend([k for k in fs.keys()])
        names.extend([k for k in pkg.keys() if k not in fs])
        # Deduplicate and sort
        uniq = sorted({*names})
        return uniq

    def get_command(self, ctx: click.Context, name: str) -> click.Command | None:
        # Built-ins first (e.g., list)
        cmd = super().get_command(ctx, name)
        if cmd is not None:
            return cmd

        # Dynamic topic resolution
        dir_to_use = _resolve_docs_dir(ctx)
        fs = _discover_fs_topics(dir_to_use) if dir_to_use else {}
        if name in fs:
            file_path = fs[name]

            @click.command(name=name)
            def _show_fs() -> None:
                click.echo(file_path.read_text(encoding="utf-8", errors="replace"))

            return _show_fs

        # Packaged fallback
        pkg = _discover_pkg_topics()
        if name in pkg:
            file_path = pkg[name]

            @click.command(name=name)
            def _show_pkg() -> None:
                click.echo(file_path.read_text(encoding="utf-8", errors="replace"))

            return _show_pkg

        return None


def register(app: typer.Typer) -> None:
    """Register the `docs` command group with dynamic topic subcommands."""

    docs_app = typer.Typer(no_args_is_help=True, add_completion=False, cls=DocsGroup)

    @docs_app.callback(invoke_without_command=True)
    def _docs_options(
        docs_dir: Path | None = typer.Option(
            None,
            "--docs-dir",
            help="Path to a docs directory to read from (overrides env/project root)",
        ),
        topic: str | None = typer.Option(None, "--topic", help="Topic to show directly"),
    ) -> None:
        """Support --docs-dir and --topic at group level."""
        if topic:
            ctx = click.get_current_context()
            dir_to_use = _resolve_docs_dir(ctx)
            fs = _discover_fs_topics(dir_to_use) if dir_to_use else {}
            if topic in fs:
                typer.echo(fs[topic].read_text(encoding="utf-8", errors="replace"))
                raise typer.Exit(code=0)
            raise typer.BadParameter(f"Unknown topic: {topic}")

    @docs_app.command("list", help="List available documentation topics")
    def list_topics() -> None:
        ctx = click.get_current_context()
        root = resolve_project_root()
        dir_to_use = _resolve_docs_dir(ctx)
        fs = _discover_fs_topics(dir_to_use) if dir_to_use else {}
        pkg = _discover_pkg_topics()

        # Print FS topics first (project/env/option), then packaged topics not shadowed by FS
        def _print(name: str, path: Path) -> None:
            try:
                rel = path.relative_to(root)
                typer.echo(f"{name}\t{rel}")
            except Exception:
                # For packaged topics, path will be site-packages absolute path
                typer.echo(f"{name}\t{path}")

        for name, path in fs.items():
            _print(name, path)
        for name, path in pkg.items():
            if name not in fs:
                _print(name, path)

    # Also support a generic "show" command
    @docs_app.command("show", help="Show docs for a topic (alternative to dynamic subcommand)")
    def show(topic: str) -> None:
        ctx = click.get_current_context()
        dir_to_use = _resolve_docs_dir(ctx)
        fs = _discover_fs_topics(dir_to_use) if dir_to_use else {}
        if topic in fs:
            typer.echo(fs[topic].read_text(encoding="utf-8", errors="replace"))
            return
        pkg = _discover_pkg_topics()
        if topic in pkg:
            typer.echo(pkg[topic].read_text(encoding="utf-8", errors="replace"))
            return
        raise typer.BadParameter(f"Unknown topic: {topic}")

    app.add_typer(docs_app, name="docs")
