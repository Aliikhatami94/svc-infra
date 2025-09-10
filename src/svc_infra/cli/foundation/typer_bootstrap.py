from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from svc_infra.app.env import find_env_file, load_env_if_present
from svc_infra.app.root import resolve_project_root


def pre_cli(app: typer.Typer) -> None:
    @app.callback()
    def _bootstrap(
        env_file: Optional[Path] = typer.Option(
            None,
            "--env-file",
            dir_okay=False,
            exists=False,
            resolve_path=True,
            help="Path to .env (defaults to auto-discovery from CWD upward).",
        ),
        no_env: bool = typer.Option(False, "--no-env", help="Skip auto-loading .env"),
        override_env: bool = typer.Option(
            False, "--override-env", help="Allow .env to override existing vars"
        ),
    ):
        if no_env:
            return
        root = resolve_project_root()
        path = env_file or find_env_file(start=root)
        load_env_if_present(path, override=override_env)
