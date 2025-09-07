from __future__ import annotations

from pathlib import Path
from typing import List, Optional
import shutil

from ai_infra.llm.tools.custom import run_cli

def _has_poetry(root: Path) -> bool:
    return (root / "pyproject.toml").exists() and bool(shutil.which("poetry"))

def _candidate_commands(root: Path, argv: List[str]) -> List[str]:
    """
    Build command lines (without 'cd') to try in order:
      1) poetry run svc-infra ...
      2) svc-infra ...
      3) python -m svc_infra.cli_shim ...
    """
    args = " ".join(argv)
    cmds: List[str] = []

    if _has_poetry(root):
        cmds.append(f"poetry run svc-infra {args}".strip())

    if shutil.which("svc-infra"):
        cmds.append(f"svc-infra {args}".strip())

    py = shutil.which("python3") or shutil.which("python") or "python"
    # Use cli_shim module (works even if svc_infra.__main__ is not present)
    cmds.append(f"{py} -m svc_infra.cli_shim {args}".strip())

    return cmds

async def _run_from_root(root: Path, argv: List[str]) -> str:
    """
    Try each candidate runner from the resolved project root.
    """
    last_err: Optional[Exception] = None
    for cmd in _candidate_commands(root, argv):
        try:
            return await run_cli(f"cd {root} && {cmd}")
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(
        f"All runners failed in {root} for: {' '.join(argv)}"
    ) from last_err
