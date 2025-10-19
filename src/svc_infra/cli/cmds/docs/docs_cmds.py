from __future__ import annotations

import os
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


def _discover_pkg_topics() -> Dict[str, object]:
    topics: Dict[str, object] = {}
    try:
        import importlib.resources as ir

        pkg_docs = ir.files("svc_infra.bundled_docs")
        for res in pkg_docs.iterdir():
            if res.name.endswith(".md"):
                topics[Path(res.name).stem.replace(" ", "-")] = res
    except Exception:
        pass
    return topics


def _resolve_docs_dir(ctx: click.Context) -> Path | None:
    # CLI option takes precedence
    docs_dir = ctx.params.get("docs_dir")
    if isinstance(docs_dir, Path) and docs_dir.exists():
        return docs_dir
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
        pkg = _discover_pkg_topics() if not fs else {}
        names.extend(fs.keys())
        names.extend(pkg.keys())
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

        if not fs:
            pkg = _discover_pkg_topics()
            if name in pkg:
                res = pkg[name]

                @click.command(name=name)
                def _show_pkg() -> None:
                    try:
                        import importlib.resources as ir

                        content = getattr(res, "read_text", None)
                        if callable(content):
                            text = content(encoding="utf-8", errors="replace")
                        else:
                            with ir.as_file(res) as p:
                                text = Path(p).read_text(encoding="utf-8", errors="replace")
                        click.echo(text)
                    except Exception as e:  # pragma: no cover
                        raise click.ClickException(f"Failed to load bundled doc: {e}")

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
            if not fs:
                pkg = _discover_pkg_topics()
                if topic in pkg:
                    try:
                        import importlib.resources as ir

                        res = pkg[topic]
                        content = getattr(res, "read_text", None)
                        if callable(content):
                            text = content(encoding="utf-8", errors="replace")
                        else:
                            with ir.as_file(res) as p:
                                text = Path(p).read_text(encoding="utf-8", errors="replace")
                        typer.echo(text)
                        raise typer.Exit(code=0)
                    except Exception as e:  # pragma: no cover
                        raise typer.BadParameter(f"Failed to load bundled topic '{topic}': {e}")
            raise typer.BadParameter(f"Unknown topic: {topic}")

    @docs_app.command("list", help="List available documentation topics")
    def list_topics() -> None:
        ctx = click.get_current_context()
        root = resolve_project_root()
        dir_to_use = _resolve_docs_dir(ctx)
        fs = _discover_fs_topics(dir_to_use) if dir_to_use else {}
        pkg = _discover_pkg_topics() if not fs else {}
        for name, path in fs.items():
            try:
                rel = path.relative_to(root)
                typer.echo(f"{name}\t{rel}")
            except Exception:
                typer.echo(f"{name}\t{path}")
        for name in sorted(pkg.keys()):
            typer.echo(f"{name}\t(bundled)")

    # Also support a generic "show" command
    @docs_app.command("show", help="Show docs for a topic (alternative to dynamic subcommand)")
    def show(topic: str) -> None:
        ctx = click.get_current_context()
        dir_to_use = _resolve_docs_dir(ctx)
        fs = _discover_fs_topics(dir_to_use) if dir_to_use else {}
        if topic in fs:
            typer.echo(fs[topic].read_text(encoding="utf-8", errors="replace"))
            return
        if not fs:
            pkg = _discover_pkg_topics()
            if topic in pkg:
                try:
                    import importlib.resources as ir

                    res = pkg[topic]
                    content = getattr(res, "read_text", None)
                    if callable(content):
                        text = content(encoding="utf-8", errors="replace")
                    else:
                        with ir.as_file(res) as p:
                            text = Path(p).read_text(encoding="utf-8", errors="replace")
                    typer.echo(text)
                    return
                except Exception as e:  # pragma: no cover
                    raise typer.BadParameter(f"Failed to load bundled topic '{topic}': {e}")
        raise typer.BadParameter(f"Unknown topic: {topic}")

    app.add_typer(docs_app, name="docs")
