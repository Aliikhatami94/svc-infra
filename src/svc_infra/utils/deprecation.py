"""Deprecation utilities for svc-infra.

This module provides decorators and functions for marking features as deprecated,
following the deprecation policy defined in DEPRECATION.md.

Example:
    >>> from svc_infra.utils.deprecation import deprecated
    >>>
    >>> @deprecated(
    ...     version="1.2.0",
    ...     reason="Use new_function() instead",
    ...     removal_version="1.4.0"
    ... )
    ... def old_function():
    ...     pass
"""

from __future__ import annotations

import functools
import warnings
from collections.abc import Callable
from typing import Any, TypeVar

__all__ = [
    "deprecated",
    "deprecated_parameter",
    "DeprecatedWarning",
]

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
            original_init = func.__init__

            @functools.wraps(original_init)
            def new_init(self: Any, *args: Any, **kwargs: Any) -> None:
                warnings.warn(message, DeprecatedWarning, stacklevel=stacklevel)
                original_init(self, *args, **kwargs)

            func.__init__ = new_init  # type: ignore[method-assign]

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
