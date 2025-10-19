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

from svc_infra.app.root import resolve_project_root

# ---------- small helpers ----------


def _norm(name: str) -> str:
    return name.strip().lower().replace(" ", "-").replace("_", "-")


def _md_topics_in(dirpath: Path) -> Dict[str, Path]:
    topics: Dict[str, Path] = {}
    if dirpath.exists() and dirpath.is_dir():
        for p in sorted(dirpath.glob("*.md")):
            if p.is_file():
                topics[_norm(p.stem)] = p
    return topics


# ---------- where could docs live after install? ----------


def _candidate_docs_dirs(ctx: click.Context) -> List[Path]:
    """
    Return likely directories that contain the shipped docs (*.md), ordered by priority.
    Covers:
      1) explicit --docs-dir / env var
      2) in-repo (editable install):   <repo>/docs  relative to src/svc_infra
      3) wheel installs:               <site-packages>/docs
      4) wheel .data area:             <site-packages>/{name}-{ver}.data/**/docs
    """
    out: List[Path] = []

    # 1) explicit override (--docs-dir or env)
    #    Walk up parent contexts to see Typer's group option.
    cur: click.Context | None = ctx
    while cur is not None:
        docs_dir_opt = (cur.params or {}).get("docs_dir")
        if docs_dir_opt:
            p = docs_dir_opt if isinstance(docs_dir_opt, Path) else Path(docs_dir_opt)
            p = p.expanduser()
            if p.exists():
                out.append(p)
                return out  # explicit override wins
        cur = cur.parent

    env_dir = os.getenv("SVC_INFRA_DOCS_DIR")
    if env_dir:
        p = Path(env_dir).expanduser()
        if p.exists():
            out.append(p)
            return out  # explicit override wins

    # locate installed package dir: .../site-packages/svc_infra
    pkg_dir: Path | None = None
    spec = importlib.util.find_spec("svc_infra")
    if spec and spec.submodule_search_locations:
        pkg_dir = Path(next(iter(spec.submodule_search_locations)))

    # 2) in-repo editable install: src/svc_infra -> ../../docs
    if pkg_dir:
        repo_root_docs = pkg_dir.parent.parent / "docs"
        if repo_root_docs.exists():
            out.append(repo_root_docs)

        # 3) wheel installs often end up with a top-level site-packages/docs
        top_level_docs = pkg_dir.parent / "docs"
        if top_level_docs.exists():
            out.append(top_level_docs)

    # 4) wheel .data layout: <site-packages>/{dist-name}-{version}.data/**/docs
    #    This catches Poetry's include=docs/**/* paths installed by pip.
    #    We compute sibling candidates off site-packages base.
    site_pkgs: Path | None = pkg_dir.parent if pkg_dir else None
    dist = None
    for name in ("svc-infra", "svc_infra"):
        try:
            dist = distribution(name)
            break
        except PackageNotFoundError:
            dist = None

    if site_pkgs and dist is not None:
        # normalized dist name (hyphen/underscore forms both happen in practice)
        dist_name = dist.metadata.get("Name", "svc-infra")
        dist_ver = dist.version
        data_candidates = [
            site_pkgs / f"{dist_name}-{dist_ver}.data",
            site_pkgs / f"{dist_name.replace('-', '_')}-{dist_ver}.data",
            site_pkgs / f"{dist_name.replace('_', '-')}-{dist_ver}.data",
        ]
        for data_dir in data_candidates:
            if not data_dir.exists():
                continue
            # common wheel data subfolders
            for sub in ("purelib", "platlib", "data"):
                d = data_dir / sub / "docs"
                if d.exists():
                    out.append(d)
            # fallback: search shallowly for any docs/ folder inside .data
            for root, dirs, _files in os.walk(data_dir):
                root_path = Path(root)
                # limit depth (cheap)
                if len(root_path.parts) - len(data_dir.parts) > 3:
                    dirs[:] = []
                    continue
                if root_path.name == "docs":
                    out.append(root_path)

    # 5) extremely defensive: scan sys.path entries that look like site-/dist-packages for top-level docs/
    for entry in sys.path:
        if not entry or ("site-packages" not in entry and "dist-packages" not in entry):
            continue
        p = Path(entry) / "docs"
        if p.exists():
            out.append(p)

    # de-dup while preserving order
    seen = set()
    uniq: List[Path] = []
    for p in out:
        if p.exists():
            key = str(p.resolve())
            if key not in seen:
                seen.add(key)
                uniq.append(p)
    return uniq


def _discover_topics(ctx: click.Context) -> Dict[str, Path]:
    topics: Dict[str, Path] = {}
    for d in _candidate_docs_dirs(ctx):
        found = _md_topics_in(d)
        # do not override earlier (higher-priority) sources
        for k, v in found.items():
            topics.setdefault(k, v)
        if topics:
            # one dir with content is enough for most setups
            # (comment out this break if you *want* deep merging)
            break
    return topics


# ---------- Typer group ----------


class DocsGroup(TyperGroup):
    def list_commands(self, ctx: click.Context) -> List[str]:
        topics = _discover_topics(ctx)
        return sorted(topics.keys())

    def get_command(self, ctx: click.Context, name: str) -> click.Command | None:
        cmd = super().get_command(ctx, name)
        if cmd is not None:
            return cmd

        key = _norm(name)
        topics = _discover_topics(ctx)
        if key in topics:
            file_path = topics[key]

            @click.command(name=name)
            def _show() -> None:
                click.echo(file_path.read_text(encoding="utf-8", errors="replace"))

            return _show

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
            topics = _discover_topics(click.get_current_context())
            if key in topics:
                typer.echo(topics[key].read_text(encoding="utf-8", errors="replace"))
                raise typer.Exit(code=0)
            raise typer.BadParameter(f"Unknown topic: {topic}")

    @docs_app.command("list", help="List available documentation topics")
    def list_topics() -> None:
        ctx = click.get_current_context()
        root = resolve_project_root()
        topics = _discover_topics(ctx)

        for name, path in topics.items():
            try:
                rel = path.relative_to(root)
                typer.echo(f"{name}\t{rel}")
            except Exception:
                typer.echo(f"{name}\t{path}")

    @docs_app.command("show", help="Show docs for a topic (alternative to dynamic subcommand)")
    def show(topic: str) -> None:
        key = _norm(topic)
        topics = _discover_topics(click.get_current_context())
        if key in topics:
            typer.echo(topics[key].read_text(encoding="utf-8", errors="replace"))
            return
        raise typer.BadParameter(f"Unknown topic: {topic}")

    app.add_typer(docs_app, name="docs")
