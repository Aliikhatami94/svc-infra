from __future__ import annotations

import asyncio
import inspect
import logging
from dataclasses import dataclass
from inspect import Parameter, signature
from typing import Any, Awaitable, Callable, Iterable, Optional, Tuple, Union

from cashews import cache as _cache

from svc_infra.cache.backend import alias as _alias
from svc_infra.cache.backend import setup_cache as _setup_cache
from svc_infra.cache.backend import wait_ready as _wait_ready

from . import backend
from .ttl import TTL_DEFAULT

log = logging.getLogger(__name__)


# ---------- init ----------
def init_cache(
    *, url: str | None = None, prefix: str | None = None, version: str | None = None
) -> None:
    _setup_cache(url=url, prefix=prefix, version=version)


async def init_cache_async(
    *, url: str | None = None, prefix: str | None = None, version: str | None = None
) -> None:
    _setup_cache(url=url, prefix=prefix, version=version)
    await _wait_ready()


# ---------- cache_read (reads) ----------
def cache_read(
    *,
    key: Union[str, tuple[str, ...]],
    ttl: Optional[int] = None,
    tags: Optional[Union[Iterable[str], Callable[..., Iterable[str]]]] = None,
    early_ttl: Optional[int] = None,
    refresh: Optional[bool] = None,
):
    """
    Version-resilient wrapper over cashews @cache:
      - Tuple keys become a template string WITHOUT formatting placeholders.
      - Prefer passing prefix=alias(); fall back to embedding alias in key.
      - Pass (ttl, key) positionally; all else by keyword to avoid 'condition' arg.
      - Publishes __svc_key_variants__(**kwargs) on the wrapped function so writers
        can delete the exact physical key(s) before recaching.
    """
    ttl_val = TTL_DEFAULT if ttl is None else ttl

    def _base_template() -> str:
        if isinstance(key, tuple):
            parts = [p for p in key if p]
            return ":".join(p.strip(":") for p in parts)
        return str(key)

    def _make_tags_fn(tags_param):
        if tags_param is None:

            def _no_tags(*_a, **_kw):
                return []

            return _no_tags
        if callable(tags_param):

            def _call_tags(*args, **kwargs):
                out = tags_param(*args, **kwargs)
                return list(out) if out is not None else []

            return _call_tags
        static = list(tags_param)

        def _static(*_a, **_kw):
            return static

        return _static

    def _build_renderer(tmpl: str) -> Callable[..., list[str]]:
        """
        Build a function that, given getter kwargs, returns all plausible
        physical keys for this entry (with and without alias prefix).
        """
        ns = _alias() or ""

        def _variants(**kw) -> list[str]:
            try:
                rendered = tmpl.format(**kw)
            except KeyError:
                return []
            with_ns = f"{ns}:{rendered}" if ns and not rendered.startswith(f"{ns}:") else rendered
            without_ns = rendered if not rendered.startswith(f"{ns}:") else rendered[len(ns) + 1 :]
            out: list[str] = []
            for k in (with_ns, without_ns):
                if k and k not in out:
                    out.append(k)
            return out

        return _variants

    def _decorator(fn: Callable[..., Awaitable[Any]]):
        tmpl = _base_template()
        ns = _alias() or ""
        tags_fn = _make_tags_fn(tags)

        # Prefer router-friendly call with prefix; fall back if unsupported.
        try:
            wrapped = _cache.cache(
                ttl_val, tmpl, tags=tags_fn, prefix=ns, early_ttl=early_ttl, refresh=refresh
            )(fn)
        except TypeError:
            try:
                wrapped = _cache.cache(ttl_val, tmpl, tags=tags_fn, prefix=ns)(fn)
            except TypeError:
                key_with_ns = f"{ns}:{tmpl}" if ns and not tmpl.startswith(f"{ns}:") else tmpl
                try:
                    wrapped = _cache.cache(
                        ttl_val, key_with_ns, tags=tags_fn, early_ttl=early_ttl, refresh=refresh
                    )(fn)
                except TypeError:
                    try:
                        wrapped = _cache.cache(ttl_val, key_with_ns, tags=tags_fn)(fn)
                    except TypeError:
                        wrapped = _cache.cache(ttl_val, key_with_ns)(fn)

        # 👉 Publish a renderer so writers can delete the exact key(s)
        setattr(wrapped, "__svc_key_variants__", _build_renderer(tmpl))

        return wrapped

    return _decorator


# Back-compat alias
cached = cache_read


# ---------- recache support ----------
@dataclass(frozen=True)
class RecachePlan:
    getter: Callable[..., Awaitable[Any]]
    include: Optional[Iterable[str]] = None  # pass-through mutation kwarg names
    rename: Optional[dict[str, str]] = None  # mutation_kw -> getter_kw
    extra: Optional[dict[str, Any]] = None  # fixed kwargs
    key: Optional[Union[str, tuple[str, ...]]] = (
        None  # optional concrete key template for delete-before-warm
    )


def recache(
    getter: Callable[..., Awaitable[Any]],
    *,
    include: Optional[Iterable[str]] = None,
    rename: Optional[dict[str, str]] = None,
    extra: Optional[dict[str, Any]] = None,
    key: Optional[Union[str, tuple[str, ...]]] = None,
) -> RecachePlan:
    return RecachePlan(getter=getter, include=include, rename=rename, extra=extra, key=key)


RecacheSpec = Union[
    Callable[..., Awaitable[Any]],
    RecachePlan,
    tuple[Callable[..., Awaitable[Any]], Any],  # legacy (getter, mapping_or_builder)
]


async def invalidate_tags(*tags: str) -> int:
    """Best-effort tag invalidation across cashews variants."""
    if not tags:
        return 0
    # Newer: invalidate(tags=[...])
    try:
        res = await _cache.invalidate(tags=list(tags))  # type: ignore[call-arg]
        return int(res) if isinstance(res, int) else 0
    except TypeError:
        pass
    except Exception:
        pass
    # Older: invalidate(*tags)
    try:
        res = await _cache.invalidate(*tags)  # type: ignore[misc]
        return int(res) if isinstance(res, int) else 0
    except Exception:
        pass
    # Fallbacks
    count = 0
    for t in tags:
        for meth in ("delete_tag", "invalidate_tag", "tag_invalidate"):
            if hasattr(_cache, meth):
                try:
                    res = await getattr(_cache, meth)(t)  # type: ignore[call-arg]
                    count += int(res) if isinstance(res, int) else 1
                    break
                except Exception:
                    continue
        else:
            for meth in ("delete_match", "invalidate_match", "invalidate"):
                if hasattr(_cache, meth):
                    try:
                        res = await getattr(_cache, meth)(f"*{t}*")  # type: ignore[call-arg]
                        count += int(res) if isinstance(res, int) else 1
                        break
                    except Exception:
                        continue
    return count


def _key_variants(tmpl: Union[str, tuple[str, ...]], params: dict[str, Any]) -> list[str]:
    # 1) join tuple without formatting at decoration-time, but DO render now:
    if isinstance(tmpl, tuple):
        parts = [p for p in tmpl if p]
        template = ":".join(p.strip(":") for p in parts)
    else:
        template = str(tmpl)
    try:
        concrete = template.format(**params)  # render placeholders now
    except KeyError:
        return []
    ns = _alias() or ""
    with_ns = f"{ns}:{concrete}" if ns and not concrete.startswith(f"{ns}:") else concrete
    without_ns = concrete if not concrete.startswith(f"{ns}:") else concrete[len(ns) + 1 :]
    # return unique, keep order
    out = []
    for k in (with_ns, without_ns):
        if k and k not in out:
            out.append(k)
    return out


# ---------- cache_write (writes) ----------
def cache_write(
    *,
    tags: Union[Iterable[str], Callable[..., Iterable[str]]],
    recache: Optional[Iterable[RecacheSpec]] = None,
    recache_max_concurrency: int = 5,
):
    """
    Decorator for POST/PUT/DELETE:
      1) invalidate tags
      2) optionally recache reads (delete exact key when provided to guarantee recompute)
    """

    def _resolve_tags(*args, **kwargs) -> list[str]:
        if callable(tags):
            return list(tags(*args, **kwargs))
        return list(tags)

    def _kwargs_for_getter(spec, mut_args, mut_kwargs):
        # Preferred: RecachePlan
        if isinstance(spec, RecachePlan):
            getter = spec.getter
            gparams = signature(getter).parameters
            call_kwargs: dict[str, Any] = {}

            source = dict(mut_kwargs)
            if spec.include:
                keep = set(spec.include)
                source = {k: v for k, v in source.items() if k in keep}

            if spec.rename:
                for src_k, dst_k in spec.rename.items():
                    if src_k in mut_kwargs and dst_k in gparams:
                        call_kwargs[dst_k] = mut_kwargs[src_k]

            for name in gparams.keys():
                if name not in call_kwargs and name in source:
                    call_kwargs[name] = source[name]

            if spec.extra:
                for k, v in spec.extra.items():
                    if k in gparams:
                        call_kwargs[k] = v

            call_kwargs = {k: v for k, v in call_kwargs.items() if k in gparams}
            for name, p in gparams.items():
                if p.default is Parameter.empty and name not in call_kwargs:
                    log.debug(
                        "recache missing required arg '%s' for %r",
                        name,
                        getattr(getter, "__name__", getter),
                    )
            return getter, call_kwargs

        # Legacy: (getter, mapping_or_builder)
        if isinstance(spec, tuple):
            getter, mapping_or_builder = spec
            gparams = signature(getter).parameters
            call_kwargs: dict[str, Any] = {}

            if callable(mapping_or_builder):
                produced = mapping_or_builder(*mut_args, **mut_kwargs) or {}
                if isinstance(produced, dict):
                    for k, v in produced.items():
                        if k in gparams:
                            call_kwargs[k] = v
            elif isinstance(mapping_or_builder, dict):
                for gk, source in mapping_or_builder.items():
                    if gk not in gparams:
                        continue
                    if callable(source):
                        try:
                            call_kwargs[gk] = source(*mut_args, **mut_kwargs)
                        except Exception:
                            continue
                    else:
                        if isinstance(source, str) and source in mut_kwargs:
                            call_kwargs[gk] = mut_kwargs[source]

            for name in gparams.keys():
                if name not in call_kwargs and name in mut_kwargs:
                    call_kwargs[name] = mut_kwargs[name]

            call_kwargs = {k: v for k, v in call_kwargs.items() if k in gparams}
            return getter, call_kwargs

        # Simple: spec is the getter
        getter = spec
        gparams = signature(getter).parameters
        return getter, {k: v for k, v in mut_kwargs.items() if k in gparams}

    def _render_key_template(
        tmpl: Union[str, tuple[str, ...]], params: dict[str, Any]
    ) -> Optional[str]:
        if isinstance(tmpl, tuple):
            parts = [p for p in tmpl if p]
            template = ":".join(p.strip(":") for p in parts)
        else:
            template = str(tmpl)
        try:
            concrete = template.format(**params)  # now we DO render
        except KeyError:
            return None
        ns = _alias() or ""
        return f"{ns}:{concrete}" if ns and not concrete.startswith(f"{ns}:") else concrete

    async def _do_recache(specs, *mut_args, **mut_kwargs):
        if not specs:
            return
        sem = asyncio.Semaphore(recache_max_concurrency)

        async def _run_one(spec):
            async with sem:
                getter, call_kwargs = _kwargs_for_getter(spec, mut_args, mut_kwargs)

                # If RecachePlan.key is provided, delete the exact cache key first.
                if isinstance(spec, RecachePlan) and spec.key is not None:
                    for k in _key_variants(spec.key, call_kwargs):
                        try:
                            await _cache.delete(k)
                        except Exception:
                            pass

                return await getter(**call_kwargs)

        await asyncio.gather(*(_run_one(s) for s in specs), return_exceptions=False)

    def _decorator(fn: Callable[..., Awaitable[Any]]):
        async def _wrapped(*args, **kwargs):
            result = await fn(*args, **kwargs)
            try:
                t = _resolve_tags(*args, **kwargs)
                if t:
                    await invalidate_tags(*t)
            finally:
                if recache:
                    await _do_recache(recache, *args, **kwargs)
            return result

        return _wrapped

    return _decorator


# Back-compat alias
mutates = cache_write


# ---------- Resource helper ----------
class Resource:
    def __init__(self, name: str, id_field: str):
        self.name = name  # e.g., "user"
        self.id_field = id_field  # e.g., "user_id"

    def cache_read(
        self,
        *,
        suffix: str,
        ttl: int,
        key_template: Optional[str] = None,
        tags_template: Optional[Tuple[str, ...]] = None,
        lock: bool = True,
    ):
        """
        Decorator for async getters. Uses cashews directly with:
          - key: string template (e.g., "user:profile:{user_id}")
          - tags: string template(s) (e.g., ("user:{user_id}",))
          - lock: singleflight (avoid stampede)
        Namespace/versioning is applied globally via backend.setup_cache -> cache.set_prefix.
        """
        key_tpl = key_template or f"{self.name}:{suffix}:{{{self.id_field}}}"
        tags_tpl = tags_template or (f"{self.name}:{{{self.id_field}}}",)

        def _decorator(func: Callable):
            return _cache(ttl=ttl, key=key_tpl, tags=tags_tpl, lock=lock)(func)

        return _decorator

    def cache_write(
        self,
        *,
        recache: Optional[list[tuple[Callable, Callable]]] = None,
        recache_max_concurrency: int = 5,
    ):
        """
        Decorator for async mutators.

        After mutation:
          1) Invalidate per-entity tag (if available on this cashews build)
          2) Hard-delete concrete keys for this entity (namespaced and non-prefixed)
          3) Optionally eager recache provided getters
        """

        async def _maybe_await(value):
            if inspect.isawaitable(value):
                return await value
            return value

        async def _delete_keys_for_entity(entity_name: str, ident: str):
            # Resolve current namespace prefix ("apiframeworks-api:vdev:")
            ns = getattr(backend, "alias", lambda: "")()
            ns_prefix = f"{ns}:" if ns and not ns.endswith(":") else ns

            # Build candidate exact keys we want gone
            candidates = [
                # Namespaced, exact keys
                f"{ns_prefix}{entity_name}:profile:{ident}",
                f"{ns_prefix}{entity_name}:profile_view:{ident}",
                # Non-prefixed fallbacks (in case set_prefix isn't applied in this build)
                f"{entity_name}:profile:{ident}",
                f"{entity_name}:profile_view:{ident}",
            ]

            # Try precise deletes first (most reliable across backends)
            for key in candidates:
                deleter = getattr(_cache, "delete", None)
                if callable(deleter):
                    await _maybe_await(deleter(key))

            # Safety net: a wildcard sweep inside the current namespace
            dm = getattr(_cache, "delete_match", None)
            if callable(dm):
                # Namespaced wildcard
                if ns_prefix:
                    await _maybe_await(dm(f"{ns_prefix}{entity_name}:*:{ident}*"))
                # Non-prefixed wildcard (just in case)
                await _maybe_await(dm(f"{entity_name}:*:{ident}*"))

        async def _do_recache(specs, *m_args, **m_kwargs):
            if not specs:
                return
            sem = asyncio.Semaphore(recache_max_concurrency)

            async def _run_one(spec):
                getter, builder = spec
                call_kwargs = builder(*m_args, **m_kwargs) or {}
                async with sem:
                    # With keys deleted above, this recomputes and repopulates cache
                    await _maybe_await(getter(**call_kwargs))

            await asyncio.gather(*(_run_one(s) for s in specs), return_exceptions=False)

        def _decorator(mutator: Callable):
            async def wrapped(*args, **kwargs):
                result = await _maybe_await(mutator(*args, **kwargs))

                ident = kwargs.get(self.id_field)
                if ident is not None:
                    # 1) Tag invalidation (if supported by your cashews)
                    inv = getattr(_cache, "invalidate", None)
                    if callable(inv):
                        await _maybe_await(inv(f"{self.name}:{ident}"))

                    # 2) Bulletproof exact-key deletes (then wildcard safety net)
                    await _delete_keys_for_entity(self.name, ident)

                # 3) Eager recache of dependent getters
                if recache:
                    await _do_recache(recache, *args, **kwargs)

                return result

            return wrapped

        return _decorator


def resource(name: str, id_field: str) -> Resource:
    return Resource(name, id_field)


def entity(name: str, id_param: str) -> Resource:  # legacy alias
    return Resource(name, id_param)
