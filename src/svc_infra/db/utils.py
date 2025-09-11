import importlib.resources as pkg
from pathlib import Path
from string import Template as _T
from typing import Any, Dict, Sequence, Tuple, Union

KeySpec = Union[str, Sequence[str]]


def as_tuple(spec: KeySpec) -> Tuple[str, ...]:
    return (spec,) if isinstance(spec, str) else tuple(spec)


def normalize_dir(p: Path | str) -> Path:
    p = Path(p)
    return p if p.is_absolute() else (Path.cwd() / p).resolve()


def render_template(tmpl_dir: str, name: str, subs: dict[str, Any]) -> str:
    txt = pkg.files(tmpl_dir).joinpath(name).read_text(encoding="utf-8")
    return _T(txt).substitute(subs)


def snake(name: str) -> str:
    import re

    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return re.sub(r"[^a-zA-Z0-9_]+", "_", s2).lower().strip("_")


def pascal(name: str) -> str:
    return "".join(p.capitalize() for p in snake(name).split("_") if p) or "Item"


def plural_snake(entity_pascal: str) -> str:
    base = snake(entity_pascal)
    return base if base.endswith("s") else base + "s"


def write(dest: Path, content: str, overwrite: bool) -> Dict[str, Any]:
    dest = dest.resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not overwrite:
        return {"path": str(dest), "action": "skipped", "reason": "exists"}
    dest.write_text(content, encoding="utf-8")
    return {"path": str(dest), "action": "wrote"}


def ensure_init_py(dir_path: Path, overwrite: bool, paired: bool, content: str) -> Dict[str, Any]:
    """Create __init__.py; paired=True writes models/schemas re-exports, otherwise minimal."""
    return write(dir_path / "__init__.py", content, overwrite)
