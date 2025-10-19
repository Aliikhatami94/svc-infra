from __future__ import annotations

import importlib.util
import os
import sys
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from typing import Dict, List

import click
import typer
from typer.core import TyperGroup


def _norm(name: str) -> str:
    """Normalize a topic name for stable CLI commands.

    - Lowercase
    - Replace spaces and underscores with hyphens
    - Strip leading/trailing whitespace
    """
    return name.strip().lower().replace(" ", "-").replace("_", "-")


def _discover_fs_topics(docs_dir: Path) -> Dict[str, Path]:
    topics: Dict[str, Path] = {}
    if docs_dir.exists() and docs_dir.is_dir():
        for p in sorted(docs_dir.glob("*.md")):
            if p.is_file():
                topics[_norm(p.stem)] = p
    return topics


def _discover_pkg_topics() -> Dict[str, Path]:
    """Discover docs packaged under 'docs/' in the installed distribution.

    Works in external projects without a local docs/ by inspecting the wheel
    metadata and, as a fallback, searching for a top-level docs/ next to the
    installed package directory in site-packages.
    """
    topics: Dict[str, Path] = {}

    # 1) Prefer distribution metadata (RECORD) for both hyphen/underscore names
    dist = None
    for name in ("svc-infra", "svc_infra"):
        try:
            dist = distribution(name)
            break
        except PackageNotFoundError:
            dist = None

    if dist is not None:
        files = getattr(dist, "files", None) or []
        for f in files:
            s = str(f)
            if not s.startswith("docs/") or not s.endswith(".md"):
                continue
            topic_name = _norm(Path(s).stem)
            try:
                abs_path = Path(dist.locate_file(f))
                if abs_path.exists() and abs_path.is_file():
                    topics[topic_name] = abs_path
            except Exception:
                # Best effort; continue to next
                continue

    # 2) Fallback: site-packages sibling 'docs/' directory (and repo-root docs in editable installs)
    try:
        spec = importlib.util.find_spec("svc_infra")
        if spec and spec.submodule_search_locations:
            pkg_dir = Path(next(iter(spec.submodule_search_locations)))
            candidates = [
                pkg_dir.parent / "docs",  # site-packages/docs OR src/docs
                pkg_dir / "docs",  # site-packages/svc_infra/docs OR src/svc_infra/docs
                pkg_dir.parent.parent
                / "docs",  # repo-root/docs when running editable from repo (src/svc_infra → ../../docs)
            ]
            for candidate in candidates:
                if candidate.exists() and candidate.is_dir():
                    for p in sorted(candidate.glob("*.md")):
                        if p.is_file():
                            topics.setdefault(_norm(p.stem), p)
                    # If one candidate had docs, that's sufficient
                    if any(k for k in topics):
                        break
    except Exception:
        # Optional fallback only
        pass

    # 3) Last-resort: scan sys.path entries that look like site-/dist-packages for a top-level docs/
    #    directory containing markdown files. This covers non-standard installs/editable modes.
    try:
        if not topics:
            for entry in sys.path:
                try:
                    if not entry or ("site-packages" not in entry and "dist-packages" not in entry):
                        continue
                    docs_dir = Path(entry) / "docs"
                    if docs_dir.exists() and docs_dir.is_dir():
                        found = _discover_fs_topics(docs_dir)
                        if found:
                            # Merge but do not override anything already found
                            for k, v in found.items():
                                topics.setdefault(k, v)
                            # If we found one valid docs dir, it's enough
                            break
                except Exception:
                    continue
    except Exception:
        pass

    # 4) Parse dist-info/RECORD or egg-info/SOURCES.txt to enumerate docs if available
    try:
        if not topics:
            spec = importlib.util.find_spec("svc_infra")
            base_dir: Path | None = None
            if spec and spec.submodule_search_locations:
                base_dir = Path(next(iter(spec.submodule_search_locations))).parent
            # Fallback to first site-packages on sys.path
            if base_dir is None:
                for entry in sys.path:
                    if entry and "site-packages" in entry:
                        base_dir = Path(entry)
                        break
            if base_dir and base_dir.exists():
                # Check for both hyphen and underscore dist-info names
                candidates = list(base_dir.glob("svc_infra-*.dist-info")) + list(
                    base_dir.glob("svc-infra-*.dist-info")
                )
                for di in candidates:
                    record = di / "RECORD"
                    if record.exists():
                        try:
                            for line in record.read_text(
                                encoding="utf-8", errors="ignore"
                            ).splitlines():
                                rel = line.split(",", 1)[0]
                                if rel.startswith("docs/") and rel.endswith(".md"):
                                    abs_p = base_dir / rel
                                    if abs_p.exists() and abs_p.is_file():
                                        topics.setdefault(_norm(Path(rel).stem), abs_p)
                        except Exception:
                            continue
                # egg-info fallback
                if not topics:
                    egg_candidates = list(base_dir.glob("svc_infra-*.egg-info")) + list(
                        base_dir.glob("svc-infra-*.egg-info")
                    )
                    for ei in egg_candidates:
                        sources = ei / "SOURCES.txt"
                        if sources.exists():
                            try:
                                for rel in sources.read_text(
                                    encoding="utf-8", errors="ignore"
                                ).splitlines():
                                    rel = rel.strip()
                                    if rel.startswith("docs/") and rel.endswith(".md"):
                                        abs_p = base_dir / rel
                                        if abs_p.exists() and abs_p.is_file():
                                            topics.setdefault(_norm(Path(rel).stem), abs_p)
                            except Exception:
                                continue
    except Exception:
        pass

    # 5) Deep fallback: recursively search site-packages/dist-packages for any 'docs' folder
    #    containing markdown files (limited depth to keep overhead reasonable).
    try:
        if not topics:
            for entry in sys.path:
                if not entry or ("site-packages" not in entry and "dist-packages" not in entry):
                    continue
                base = Path(entry)
                if not base.exists() or not base.is_dir():
                    continue
                base_parts = len(base.parts)
                for root, dirs, files in os.walk(base):
                    root_path = Path(root)
                    # Limit search depth to avoid expensive scans
                    if len(root_path.parts) - base_parts > 4:
                        # prune
                        dirs[:] = []
                        continue
                    if root_path.name == "docs":
                        for p in sorted(root_path.glob("*.md")):
                            if p.is_file():
                                topics.setdefault(_norm(p.stem), p)
                        # do not break; there might be multiple doc dirs
    except Exception:
        pass

    return topics


def _resolve_docs_dir(ctx: click.Context) -> Path | None:
    # Deprecated: we no longer read docs from arbitrary paths or env.
    # All docs are sourced from the packaged svc-infra distribution only.
    return None


class DocsGroup(TyperGroup):
    def list_commands(self, ctx: click.Context) -> List[str]:
        names: List[str] = list(super().list_commands(ctx) or [])
        pkg = _discover_pkg_topics()
        names.extend([k for k in pkg.keys()])
        # Deduplicate and sort
        return sorted({*names})

    def get_command(self, ctx: click.Context, name: str) -> click.Command | None:
        # Built-ins first (e.g., list, show)
        cmd = super().get_command(ctx, name)
        if cmd is not None:
            return cmd

        # Packaged topics only
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
        topic: str | None = typer.Option(None, "--topic", help="Topic to show directly"),
    ) -> None:
        """Support --topic at group level (packaged docs only)."""
        if topic:
            pkg = _discover_pkg_topics()
            if topic in pkg:
                typer.echo(pkg[topic].read_text(encoding="utf-8", errors="replace"))
                raise typer.Exit(code=0)
            raise typer.BadParameter(f"Unknown topic: {topic}")

    @docs_app.command("list", help="List available documentation topics")
    def list_topics() -> None:
        pkg = _discover_pkg_topics()

        # Print packaged topics only
        def _print(name: str, path: Path) -> None:
            typer.echo(f"{name}\t{path}")

        for name, path in pkg.items():
            _print(name, path)

    # Also support a generic "show" command
    @docs_app.command("show", help="Show docs for a topic (alternative to dynamic subcommand)")
    def show(topic: str) -> None:
        pkg = _discover_pkg_topics()
        if topic in pkg:
            typer.echo(pkg[topic].read_text(encoding="utf-8", errors="replace"))
            return
        raise typer.BadParameter(f"Unknown topic: {topic}")

    app.add_typer(docs_app, name="docs")
