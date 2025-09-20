from __future__ import annotations

import asyncio
from dataclasses import dataclass
from inspect import signature
from typing import Any, Awaitable, Callable, Iterable, Optional, Union

from cashews import cache as _cache

from .ttl import TTL_DEFAULT
from .utils import format_tuple_key, stable_hash


# ---------- init ----------
def init_cache(
    url: Optional[str] = None,
    *,
    prefix: Optional[str] = None,
    version: Optional[str] = None,
) -> None:
    from .backend import setup_cache

    setup_cache(url=url, prefix=prefix, version=version)


# ---------- cache_read (reads) ----------
KeyType = Union[str, tuple[str, ...], None]


def cache_read(
    key: KeyType = None,
    *,
    ttl: Optional[int] = None,
    tags: Optional[Union[Iterable[str], Callable[..., Iterable[str]]]] = None,
    early_ttl: Optional[int] = None,
    refresh: bool = False,
):
    """
    Cache reads.

    key:
      - "user:{user_id}:profile"    (str template)
      - ("user", "{user_id}", "profile")  (tuple parts)
      - None -> auto-hash args
    """
    ttl = TTL_DEFAULT if ttl is None else ttl

    def _build_key(fn_name: str, *args, **kwargs) -> str:
        alias = _cache.get_alias() or "svc"
        if isinstance(key, tuple):
            try:
                body = format_tuple_key(key, **kwargs)
            except Exception:
                body = f"{fn_name}:{stable_hash(*args, **kwargs)}"
        elif isinstance(key, str):
            try:
                body = key.format(**kwargs)
            except Exception:
                body = f"{fn_name}:{stable_hash(*args, **kwargs)}"
        else:
            body = f"{fn_name}:{stable_hash(*args, **kwargs)}"
        return f"{alias}:{body}"

    def _build_tags(*args, **kwargs) -> list[str] | None:
        if tags is None:
            return None
        if callable(tags):
            try:
                return list(tags(*args, **kwargs))
            except Exception:
                return None
        return list(tags)

    def _decorator(fn: Callable[..., Awaitable[Any]]):
        deco = _cache.cache(
            key=lambda *a, **kw: _build_key(fn.__name__, *a, **kw),
            expire=ttl,
            tags=_build_tags,
            early_ttl=early_ttl,
            refresh=refresh,
        )
        return deco(fn)

    return _decorator


# Back-compat alias
cached = cache_read


# ---------- Recache plan & builder ----------
@dataclass(frozen=True)
class RecachePlan:
    getter: Callable[..., Awaitable[Any]]
    include: Optional[Iterable[str]] = None  # keep only these mutation kwargs
    rename: Optional[dict[str, str]] = None  # map mutation kw -> getter kw
    extra: Optional[dict[str, Any]] = None  # add fixed kwargs


def recache(
    getter: Callable[..., Awaitable[Any]],
    *,
    include: Optional[Iterable[str]] = None,
    rename: Optional[dict[str, str]] = None,
    extra: Optional[dict[str, Any]] = None,
) -> RecachePlan:
    """Build a readable adapter describing how to call `getter` after a write."""
    return RecachePlan(getter=getter, include=include, rename=rename, extra=extra)


# Support three `recache` spec styles:
#   1) getter function only (auto-filter by signature)
#   2) RecachePlan (preferred)
#   3) Legacy tuple: (getter, kw_builder)

RecacheSpec = Union[
    Callable[..., Awaitable[Any]],
    RecachePlan,
    tuple[Callable[..., Awaitable[Any]], Callable[..., dict[str, Any]]],
]


async def invalidate_tags(*tags: str) -> int:
    if not tags:
        return 0
    return await _cache.invalidate(tags=list(tags))


# ---------- cache_write (writes) ----------
def cache_write(
    *,
    tags: Union[Iterable[str], Callable[..., Iterable[str]]],
    recache: Optional[Iterable[RecacheSpec]] = None,
    recache_max_concurrency: int = 5,
):
    """
    Decorator for POST/PUT/DELETE:
      1) invalidate provided tags
      2) optionally recache reads

    `recache` can contain:
      - getter function -> auto-intersect by getter signature
      - recache(getter, include=..., rename=..., extra=...)
      - legacy (getter, kw_builder) pair
    """

    def _resolve_tags(*args, **kwargs) -> list[str]:
        if callable(tags):
            return list(tags(*args, **kwargs))
        return list(tags)

    def _kwargs_for_getter(spec: RecacheSpec, *, mut_args, mut_kwargs) -> tuple[Callable, dict]:
        # Legacy (getter, kw_builder)
        if isinstance(spec, tuple):
            getter, kw_builder = spec
            return getter, dict(kw_builder(*mut_args, **mut_kwargs))

        # RecachePlan
        if isinstance(spec, RecachePlan):
            getter = spec.getter
            out: dict[str, Any] = dict(mut_kwargs)

            if spec.include is not None:
                out = {k: out[k] if k in out else None for k in spec.include if k in out}

            if spec.rename:
                out = {spec.rename.get(k, k): v for k, v in out.items()}

            if spec.extra:
                out.update(spec.extra)

            # drop anything the getter doesn't accept
            g_params = set(signature(getter).parameters.keys())
            out = {k: v for k, v in out.items() if k in g_params}
            return getter, out

        # Simple: spec is a getter
        getter = spec
        g_params = set(signature(getter).parameters.keys())
        filtered = {k: v for k, v in mut_kwargs.items() if k in g_params}
        return getter, filtered

    async def _do_recache(specs: Iterable[RecacheSpec], *args, **kwargs) -> None:
        sem = asyncio.Semaphore(recache_max_concurrency)

        async def _run_one(spec: RecacheSpec):
            async with sem:
                getter, call_kwargs = _kwargs_for_getter(spec, mut_args=args, mut_kwargs=kwargs)
                await getter(**call_kwargs)

        tasks = [asyncio.create_task(_run_one(s)) for s in specs]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _decorator(fn: Callable[..., Awaitable[Any]]):
        async def _wrapped(*args, **kwargs):
            result = await fn(*args, **kwargs)
            t = _resolve_tags(*args, **kwargs)
            if t:
                await invalidate_tags(*t)
            if recache:
                await _do_recache(recache, *args, **kwargs)
            return result

        return _wrapped

    return _decorator


# Back-compat alias
mutates = cache_write


# ---------- Resource helper ----------
class Resource:
    """
    Standardizes keys & tags for a single-id resource.
    Requires the id be passed as a keyword arg with name `id_field`.
    """

    def __init__(self, name: str, id_field: str):
        self.name = name.strip().lower()
        self.id_field = id_field

    def _tags(self, **kwargs) -> list[str]:
        _id = kwargs[self.id_field]
        return [self.name, f"{self.name}:{_id}"]

    def _key_base(self) -> tuple[str, ...]:
        return (self.name, "{%s}" % self.id_field)

    def cache_read(
        self,
        *,
        suffix: Optional[Union[str, tuple[str, ...]]] = None,
        ttl: Optional[int] = None,
        early_ttl: Optional[int] = None,
        refresh: bool = False,
    ):
        parts: list[str] = list(self._key_base())
        if suffix:
            if isinstance(suffix, tuple):
                parts.extend(suffix)
            else:
                parts.append(str(suffix))
        return cache_read(
            key=tuple(parts),
            ttl=ttl,
            tags=lambda **kw: self._tags(**kw),
            early_ttl=early_ttl,
            refresh=refresh,
        )

    def cache_write(
        self,
        *,
        recache: Optional[Iterable[RecacheSpec]] = None,
        recache_max_concurrency: int = 5,
    ):
        return cache_write(
            tags=lambda **kw: self._tags(**kw),
            recache=recache,
            recache_max_concurrency=recache_max_concurrency,
        )


# Back-compat helper & aliases
def resource(name: str, id_field: str) -> Resource:
    return Resource(name, id_field)


def entity(name: str, id_param: str) -> Resource:  # legacy alias
    return Resource(name, id_param)
