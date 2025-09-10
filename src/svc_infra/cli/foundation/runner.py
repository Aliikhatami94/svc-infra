from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import List, Optional


def _has_poetry(root: Path) -> bool:
    return (root / "pyproject.toml").exists() and bool(shutil.which("poetry"))


def candidate_cmds(root: Path, prog: str, argv: List[str]) -> List[List[str]]:
    """
    Return argv lists to try in order:
      1) poetry run <prog> ...
      2) <prog> ...
      3) python -m <module> ...
    """
    cmds: List[List[str]] = []
    if _has_poetry(root):
        cmds.append(["poetry", "run", prog, *argv])

    if shutil.which(prog):
        cmds.append([prog, *argv])

    py = shutil.which("python3") or shutil.which("python") or "python"
    module = prog.replace("-", "_") + ".cli_shim"  # e.g., svc-infra -> svc_infra.cli_shim
    cmds.append([py, "-m", module, *argv])

    return cmds


async def run_from_root(root: Path, prog: str, argv: List[str]) -> str:
    """
    cd to project root and run the first working candidate command.
    Returns captured stdout+stderr text; raises on total failure.
    """
    last_exc: Optional[BaseException] = None
    for cmd in candidate_cmds(root, prog, argv):
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            out, _ = await proc.communicate()
            if proc.returncode == 0:
                return out.decode(errors="replace")
            last_exc = RuntimeError(
                f"Exit {proc.returncode}: {' '.join(cmd)}\n{out.decode(errors='replace')}"
            )
        except Exception as e:
            last_exc = e
            continue
    raise RuntimeError(f"All runners failed in {root} for: {prog} {' '.join(argv)}") from last_exc
