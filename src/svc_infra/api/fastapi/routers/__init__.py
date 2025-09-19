from __future__ import annotations

import importlib
import logging
import pkgutil
from types import ModuleType
from typing import Optional

from fastapi import FastAPI

from svc_infra.app.env import ALL_ENVIRONMENTS, CURRENT_ENVIRONMENT, DEV_ENV, LOCAL_ENV, Environment

logger = logging.getLogger(__name__)


def _should_skip_module(module_name: str) -> bool:
    """
    Returns True if the module should be skipped based on:
    - private/dunder final segment
    """
    parts = module_name.split(".")
    last_segment = parts[-1]
    return last_segment.startswith("_")


def register_all_routers(
    app: FastAPI,
    *,
    base_package: Optional[str] = None,
    prefix: str = "",
    environment: Optional[Environment | str] = None,
    force_include_in_schema: Optional[bool] = None,
) -> None:
    """
    Recursively discover and register all FastAPI routers under a routers package.

    Args:
        app: FastAPI application instance.
        base_package: Import path to the root routers package (e.g., "myapp.api.routers").
            If omitted, derived from this module's package.
        prefix: API prefix for all routers (e.g., "/v0").
        environment: The current environment (defaults to get_env()).

    Behavior:
        - Any module under the package with a top-level `router` variable is included.
        - Files/packages whose final segment starts with '_' are skipped.
        - If a module defines ROUTER_ENVIRONMENTS, it is a set/list of environments (Env or str) in which the router is included.
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
        raise RuntimeError(
            f"Provided base_package '{base_package}' is not a package (no __path__)."
        )

    environment = (
        CURRENT_ENVIRONMENT
        if environment is None
        else (Environment(environment) if not isinstance(environment, Environment) else environment)
    )

    if force_include_in_schema is None:
        force_include_in_schema = environment in (LOCAL_ENV, DEV_ENV)

    for _, module_name, _ in pkgutil.walk_packages(
        package_module.__path__, prefix=f"{base_package}."
    ):
        if _should_skip_module(module_name):
            logger.debug("Skipping router module due to exclusion/private: %s", module_name)
            continue
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            logger.exception("Failed to import router module %s: %s", module_name, exc)
            continue
        router = getattr(module, "router", None)
        if router is not None:
            # Check for ROUTER_EXCLUDED_ENVIRONMENTS
            router_excluded_envs = getattr(module, "ROUTER_EXCLUDED_ENVIRONMENTS", None)
            if router_excluded_envs is not None:
                # Support ALL_ENVIRONMENTS as a special value
                if router_excluded_envs is ALL_ENVIRONMENTS or (
                    isinstance(router_excluded_envs, set)
                    and router_excluded_envs == ALL_ENVIRONMENTS
                ):
                    logger.debug(
                        f"Skipping router module {module_name} due to ALL_ENVIRONMENTS exclusion."
                    )
                    continue
                # Normalize to set of Environment or str
                if not isinstance(router_excluded_envs, (set, list, tuple)):
                    logger.warning(
                        f"ROUTER_EXCLUDED_ENVIRONMENTS in {module_name} must be a set/list/tuple, got {type(router_excluded_envs)}"
                    )
                    continue
                normalized_excluded_envs = set()
                for e in router_excluded_envs:
                    try:
                        normalized_excluded_envs.add(
                            Environment(e) if not isinstance(e, Environment) else e
                        )
                    except Exception:
                        normalized_excluded_envs.add(str(e))
                if (
                    environment in normalized_excluded_envs
                    or str(environment) in normalized_excluded_envs
                ):
                    logger.debug(
                        f"Skipping router module {module_name} due to ROUTER_EXCLUDED_ENVIRONMENTS restriction: {router_excluded_envs}"
                    )
                    continue
            # module-level opt-out that still works even in LOCAL (rare but handy)
            if getattr(module, "ROUTER_NEVER_IN_SCHEMA", False) is True:
                continue

            router_prefix = getattr(module, "ROUTER_PREFIX", None)
            router_tag = getattr(module, "ROUTER_TAG", None)
            include_in_schema = getattr(module, "INCLUDE_ROUTER_IN_SCHEMA", True)

            include_kwargs = {"prefix": prefix}
            if router_prefix:
                include_kwargs["prefix"] = prefix.rstrip("/") + router_prefix
            if router_tag:
                include_kwargs["tags"] = [router_tag]

            # the key line: force in LOCAL, otherwise respect the module
            include_kwargs["include_in_schema"] = (
                True if force_include_in_schema else include_in_schema
            )

            app.include_router(router, **include_kwargs)
            logger.debug(
                "Included router from module: %s (prefix=%s, tag=%s, include_in_schema=%s)",
                module_name,
                include_kwargs.get("prefix"),
                router_tag,
                include_kwargs.get("include_in_schema"),
            )
