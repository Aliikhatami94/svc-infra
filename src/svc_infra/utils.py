"""svc-infra utilities module.

This module provides utility functions and helpers for svc-infra, including:
- Template rendering and file writing utilities
- Deprecation decorators and warnings
"""

from __future__ import annotations

import functools
import importlib.resources as pkg
import warnings
from collections.abc import Callable
from pathlib import Path
from string import Template as _T
from typing import Any, TypeVar

__all__ = [
    # Template utilities
    "render_template",
    "write",
    "ensure_init_py",
    # Deprecation utilities
    "deprecated",
    "deprecated_parameter",
    "DeprecatedWarning",
]


# =============================================================================
# Template Utilities
# =============================================================================


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


# =============================================================================
# Deprecation Utilities
# =============================================================================

F = TypeVar("F", bound=Callable[..., Any])


class DeprecatedWarning(DeprecationWarning):
    """Custom deprecation warning for svc-infra.

    This warning is used to distinguish svc-infra deprecations from
    Python's built-in DeprecationWarning.
    """

    pass


def deprecated(
    version: str,
    reason: str,
    removal_version: str | None = None,
    *,
    stacklevel: int = 2,
) -> Callable[[F], F]:
    """Decorator to mark a function or class as deprecated.

    The decorated function/class will emit a DeprecationWarning when called/instantiated.

    Args:
        version: The version in which the feature was deprecated (e.g., "1.2.0").
        reason: The reason for deprecation and recommended alternative.
        removal_version: The version in which the feature will be removed (e.g., "1.4.0").
        stacklevel: Stack level for the warning (default 2 for immediate caller).

    Returns:
        A decorator that wraps the function/class with deprecation warning.

    Example:
        >>> @deprecated(
        ...     version="1.2.0",
        ...     reason="Use new_function() instead",
        ...     removal_version="1.4.0"
        ... )
        ... def old_function():
        ...     return "result"
        >>>
        >>> old_function()  # Emits DeprecationWarning
        'result'
    """

    def decorator(func: F) -> F:
        # Build the warning message
        name = getattr(func, "__qualname__", getattr(func, "__name__", str(func)))
        message = f"{name} is deprecated since version {version}."

        if removal_version:
            message += f" It will be removed in version {removal_version}."

        message += f" {reason}"

        if isinstance(func, type):
            # Handle class deprecation
            original_init = func.__init__  # type: ignore[misc]

            @functools.wraps(original_init)
            def new_init(self: Any, *args: Any, **kwargs: Any) -> None:
                warnings.warn(message, DeprecatedWarning, stacklevel=stacklevel)
                original_init(self, *args, **kwargs)

            func.__init__ = new_init  # type: ignore[misc]

            # Add deprecation info to docstring
            if func.__doc__:
                func.__doc__ = f".. deprecated:: {version}\n   {reason}\n\n{func.__doc__}"
            else:
                func.__doc__ = f".. deprecated:: {version}\n   {reason}"

            return func  # type: ignore[return-value]
        else:
            # Handle function deprecation
            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                warnings.warn(message, DeprecatedWarning, stacklevel=stacklevel)
                return func(*args, **kwargs)

            # Add deprecation info to docstring
            if wrapper.__doc__:
                wrapper.__doc__ = f".. deprecated:: {version}\n   {reason}\n\n{wrapper.__doc__}"
            else:
                wrapper.__doc__ = f".. deprecated:: {version}\n   {reason}"

            return wrapper  # type: ignore[return-value]

    return decorator


def deprecated_parameter(
    name: str,
    version: str,
    reason: str,
    removal_version: str | None = None,
    *,
    stacklevel: int = 2,
) -> None:
    """Emit a deprecation warning for a deprecated parameter.

    Call this function when a deprecated parameter is used. This should be
    called at the beginning of a function that has deprecated parameters.

    Args:
        name: The name of the deprecated parameter.
        version: The version in which the parameter was deprecated.
        reason: The reason for deprecation and recommended alternative.
        removal_version: The version in which the parameter will be removed.
        stacklevel: Stack level for the warning (default 2 for immediate caller).

    Example:
        >>> def my_function(new_param: str, old_param: str | None = None):
        ...     if old_param is not None:
        ...         deprecated_parameter(
        ...             name="old_param",
        ...             version="1.2.0",
        ...             reason="Use new_param instead"
        ...         )
        ...         new_param = old_param
        ...     return new_param
    """
    message = f"Parameter '{name}' is deprecated since version {version}."

    if removal_version:
        message += f" It will be removed in version {removal_version}."

    message += f" {reason}"

    warnings.warn(message, DeprecatedWarning, stacklevel=stacklevel + 1)
