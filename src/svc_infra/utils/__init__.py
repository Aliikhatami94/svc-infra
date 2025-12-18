"""svc-infra utilities package.

This package provides utility functions and helpers for svc-infra.
"""

from svc_infra.utils.deprecation import (
    DeprecatedWarning,
    deprecated,
    deprecated_parameter,
)

__all__ = [
    "deprecated",
    "deprecated_parameter",
    "DeprecatedWarning",
]
