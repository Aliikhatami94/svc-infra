from __future__ import annotations


def namespaced(prefix: str, *parts: str | int) -> str:
    safe = [str(p).strip().replace(" ", "_") for p in parts if p is not None]
    return ":".join([prefix, *safe])


def join(*parts: str | int) -> str:
    return ":".join(str(p) for p in parts)
