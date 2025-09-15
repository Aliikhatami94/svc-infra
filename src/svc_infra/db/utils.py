from pathlib import Path
from typing import Sequence, Tuple, Union

KeySpec = Union[str, Sequence[str]]


def as_tuple(spec: KeySpec) -> Tuple[str, ...]:
    return (spec,) if isinstance(spec, str) else tuple(spec)


def normalize_dir(p: Path | str) -> Path:
    p = Path(p)
    return p if p.is_absolute() else (Path.cwd() / p).resolve()


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
