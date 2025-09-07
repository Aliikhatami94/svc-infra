from __future__ import annotations
from pathlib import Path
import os
from typing import Optional

from dotenv import load_dotenv
import typer

def find_env_file(start: Optional[Path] = None) -> Optional[Path]:
    """
    Look for an .env file in this order:
      1) SVC_INFRA_ENV_FILE (explicit path)
      2) <start>/.env
      3) Walk up parent dirs from <start> until filesystem root and pick first .env
    """
    # 1) explicit env var wins
    env_file = os.getenv("SVC_INFRA_ENV_FILE")
    if env_file:
        p = Path(env_file).expanduser()
        return p if p.exists() else None

    # 2) start (or cwd) and walk upward
    cur = (start or Path.cwd()).resolve()
    for p in [cur, *cur.parents]:
        candidate = p / ".env"
        if candidate.exists():
            return candidate
    return None

def load_env_if_present(path: Optional[Path], *, override: bool = False) -> list[str]:
    """
    Load .env variables into process env. Returns the list of keys set/updated.
    """
    if not path:
        return []
    before = set(os.environ.keys())
    load_dotenv(dotenv_path=path, override=override)
    after = set(os.environ.keys())
    # Rough approximation of what was added/changed:
    changed = sorted(k for k in after if k not in before or os.environ.get(k) != os.environ.get(k))
    return changed


def _bootstrap(
        env_file: Optional[Path] = typer.Option(
            None,
            "--env-file",
            help="Path to a .env to load before running the command (defaults to auto-discovery).",
            dir_okay=False,
            exists=False,
            resolve_path=True,
        ),
        no_env: bool = typer.Option(
            False,
            "--no-env",
            help="Skip auto-loading any .env file.",
        ),
        override: bool = typer.Option(
            False,
            "--override-env",
            help="When loading .env, allow values to override existing environment variables.",
        ),
):
    """
    Global bootstrap: load .env (if found) before any subcommand executes.
    """
    if no_env:
        return
    path = env_file or find_env_file()
    load_env_if_present(path, override=override)


def pre(app: typer.Typer) -> None:
    app.callback()(_bootstrap)