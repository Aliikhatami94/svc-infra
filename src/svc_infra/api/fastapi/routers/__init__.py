from __future__ import annotations

import importlib
import logging
import pkgutil
from types import ModuleType
from typing import Set, Optional
from fastapi import FastAPI
from svc_infra.app.core.env import get_env, Env

logger = logging.getLogger(__name__)


def _should_skip_module(module_name: str, exclude_segments: Set[str]) -> bool:
    """
    Returns True if the module should be skipped based on:
    - private/dunder final segment
    - excluded path segments (e.g., 'internal')
    """
    parts = module_name.split(".")
    last_segment = parts[-1]
    if last_segment.startswith("_"):
        return True
    return any(seg in exclude_segments for seg in parts)


def register_all_routers(
        app: FastAPI,
        *,
        base_package: Optional[str] = None,
        prefix: str = "",
        exclude: Optional[dict[Env | str, set[str]]] = None,
        env: Optional[Env | str] = None,
) -> None:
    """
    Recursively discover and register all FastAPI routers under a routers package.

    Args:
        app: FastAPI application instance.
        base_package: Import path to the root routers package (e.g., "myapp.api.routers").
            If omitted, derived from this module's package.
        prefix: API prefix for all routers (e.g., "/v0").
        exclude: Dict mapping Env (or str) to sets of path segments to exclude,
            e.g. {Env.PROD: {"internal"}, Env.TEST: {"experimental"}, "all": {"_deprecated"}}.
        env: The current environment (defaults to get_env()).

    Behavior:
        - Any module under the package with a top-level `router` variable is included.
        - Files/packages whose final segment starts with '_' are skipped.
        - Modules under excluded path segments are skipped only in the specified environments.
        - Import errors are logged and skipped.
        - Nested discovery requires `__init__.py` files in packages.
        - If a module defines ROUTER_PREFIX or ROUTER_TAGS, they are used for that router.
    """
    if base_package is None:
        if __package__ is None:
            raise RuntimeError("Cannot derive base_package; please pass base_package explicitly.")
        base_package = __package__

    try:
        package_module: ModuleType = importlib.import_module(base_package)
    except Exception as exc:
        raise RuntimeError(f"Could not import base_package '{base_package}': {exc}") from exc

    if not hasattr(package_module, "__path__"):
        raise RuntimeError(f"Provided base_package '{base_package}' is not a package (no __path__).")

    # Always normalize env to canonical Env type
    env = get_env() if env is None else (Env(env) if not isinstance(env, Env) else env)
    exclude = exclude or {}
    exclude_set: Set[str] = set()
    # Accept both Env and str keys in exclude, normalize to Env
    for key, segments in exclude.items():
        if key == "all":
            exclude_set.update(segments)
        else:
            key_env = Env(key) if not isinstance(key, Env) else key
            if key_env == env:
                exclude_set.update(segments)
    if exclude_set:
        logger.debug(
            "Router discovery exclusions active for env '%s': %s", env, sorted(exclude_set)
        )

    for _, module_name, _ in pkgutil.walk_packages(
            package_module.__path__, prefix=f"{base_package}."
    ):
        if _should_skip_module(module_name, exclude_set):
            logger.debug("Skipping router module due to exclusion/private: %s", module_name)
            continue
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            logger.exception("Failed to import router module %s: %s", module_name, exc)
            continue
        router = getattr(module, "router", None)
        if router is not None:
            # Pick up ROUTER_PREFIX, ROUTER_TAG, and INCLUDE_ROUTER_IN_SCHEMA if present
            router_prefix = getattr(module, "ROUTER_PREFIX", None)
            router_tag = getattr(module, "ROUTER_TAG", None)
            include_in_schema = getattr(module, "INCLUDE_ROUTER_IN_SCHEMA", True)
            include_kwargs = {"prefix": prefix}
            if router_prefix:
                include_kwargs["prefix"] = prefix.rstrip("/") + router_prefix
            if router_tag:
                include_kwargs["tags"] = [router_tag]
            include_kwargs["include_in_schema"] = include_in_schema
            app.include_router(router, **include_kwargs)
            logger.debug(
                "Included router from module: %s (prefix=%s, tag=%s, include_in_schema=%s)",
                module_name, include_kwargs.get("prefix"), router_tag, include_kwargs.get("include_in_schema")
            )