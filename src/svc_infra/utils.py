import importlib.resources as pkg
from pathlib import Path
from string import Template as _T
from typing import Any


def render_template(tmpl_dir: str, name: str, subs: dict[str, Any] | None = None) -> str:
    txt = pkg.files(tmpl_dir).joinpath(name).read_text(encoding="utf-8")
    return _T(txt).safe_substitute(subs or {})


def write(dest: Path, content: str, overwrite: bool = False) -> dict[str, Any]:
    dest = dest.resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not overwrite:
        return {"path": str(dest), "action": "skipped", "reason": "exists"}
    dest.write_text(content, encoding="utf-8")
    return {"path": str(dest), "action": "wrote"}


def ensure_init_py(dir_path: Path, overwrite: bool, paired: bool, content: str) -> dict[str, Any]:
    """Create __init__.py; paired=True writes models/schemas re-exports, otherwise minimal."""
    return write(dir_path / "__init__.py", content, overwrite)
