from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import typer

from svc_infra.app.root import resolve_project_root


def _discover_docs(root: Path) -> List[Tuple[str, Path]]:
    """Return a list of (topic, file_path) for top-level Markdown files under docs/.

    Topic is the filename stem (e.g. security.md -> "security").
    """
    docs_dir = root / "docs"
    topics: List[Tuple[str, Path]] = []
    if not docs_dir.exists() or not docs_dir.is_dir():
        return topics
    for p in sorted(docs_dir.glob("*.md")):
        if p.is_file():
            topics.append((p.stem.replace(" ", "-"), p))
    return topics


def register(app: typer.Typer) -> None:
    """Register the `docs` command group and dynamic topic subcommands."""

    root = resolve_project_root()
    discovered = _discover_docs(root)

    # Build help text listing available topics
    if discovered:
        topic_names = ", ".join(name for name, _ in discovered)
        docs_help = (
            f"Show docs from the repository's docs/ directory.\n\nAvailable topics: {topic_names}"
        )
    else:
        docs_help = "Show docs from the repository's docs/ directory.\n\nNo topics discovered."

    docs_app = typer.Typer(no_args_is_help=True, help=docs_help, add_completion=False)

    @docs_app.command("list", help="List available documentation topics")
    def list_topics() -> None:
        for name, path in discovered:
            typer.echo(f"{name}\t{path.relative_to(root)}")

    # Freeze mapping for use in dynamic commands and generic fallback
    topic_map: Dict[str, Path] = {name: path for name, path in discovered}

    def _make_topic_cmd(topic: str, file_path: Path):
        @docs_app.command(name=topic, help=f"Show docs for topic: {topic}")
        def _show_topic() -> None:  # noqa: WPS430 (nested function OK for closure)
            content = file_path.read_text(encoding="utf-8", errors="replace")
            typer.echo(content)

    for name, path in discovered:
        _make_topic_cmd(name, path)

    # Optional generic fallback: allow `svc-infra docs --topic <name>`
    @docs_app.callback(invoke_without_command=True)
    def _maybe_show_topic(topic: str = typer.Option(None, "--topic", help="Topic to show")) -> None:  # type: ignore[no-redef]
        if topic:
            p = topic_map.get(topic)
            if not p:
                raise typer.BadParameter(f"Unknown topic: {topic}")
            typer.echo(p.read_text(encoding="utf-8", errors="replace"))

    app.add_typer(docs_app, name="docs")
