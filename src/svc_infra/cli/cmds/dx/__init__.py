from __future__ import annotations

import typer

from .dx_cmds import app as dx_app


def register_dx(root: typer.Typer) -> None:
    root.add_typer(dx_app, name="dx")


__all__ = ["register_dx"]
