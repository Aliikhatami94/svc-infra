"""Centralized exception re-exports for svc-infra.

This module provides a single import point for all svc-infra exceptions.
Exceptions are organized by domain and all inherit from the base SvcInfraError.

Example:
    from svc_infra.exceptions import (
        SvcInfraError,
        WebSocketError,
        StorageError,
        FastApiException,
    )
"""

# ruff: noqa: E402

from __future__ import annotations

import logging
from typing import Any

# =============================================================================
# Logging Helper
# =============================================================================


def log_exception(
    logger: logging.Logger,
    msg: str,
    exc: Exception,
    *,
    level: str = "warning",
    include_traceback: bool = True,
) -> None:
    """Log an exception with consistent formatting.

    Use this helper instead of bare `except Exception:` blocks to ensure
    all exceptions are properly logged with context.

    Args:
        logger: The logger instance to use
        msg: Context message describing what operation failed
        exc: The exception that was caught
        level: Log level - "debug", "info", "warning", "error", "critical"
        include_traceback: Whether to include full traceback (exc_info=True)

    Example:
        try:
            result = await service.process()
        except Exception as e:
            log_exception(logger, "Failed to process request", e)
            # Handle gracefully or re-raise
    """
    log_func = getattr(logger, level.lower(), logger.warning)
    log_func(f"{msg}: {type(exc).__name__}: {exc}", exc_info=include_traceback)


# =============================================================================
# Base Error
# =============================================================================


class SvcInfraError(Exception):
    """Base exception for all svc-infra errors.

    All svc-infra exceptions can be caught with this single class.

    Attributes:
        message: Human-readable error description
        details: Additional context as key-value pairs
    """

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.message!r})"


# =============================================================================
# Re-exports from submodules
# =============================================================================

# API exceptions
from svc_infra.api.fastapi.middleware.errors.exceptions import FastApiException

# App exceptions
from svc_infra.app.env import MissingSecretError

# Security exceptions
from svc_infra.security.passwords import PasswordValidationError

# Storage exceptions
from svc_infra.storage.base import FileNotFoundError as StorageFileNotFoundError
from svc_infra.storage.base import (
    InvalidKeyError,
    PermissionDeniedError,
    QuotaExceededError,
    StorageError,
)

# WebSocket exceptions
from svc_infra.websocket.exceptions import AuthenticationError as WebSocketAuthError
from svc_infra.websocket.exceptions import (
    ConnectionClosedError,
    ConnectionFailedError,
    MessageTooLargeError,
    WebSocketError,
)

__all__ = [
    # Logging helper
    "log_exception",
    # Base
    "SvcInfraError",
    # WebSocket
    "WebSocketError",
    "WebSocketAuthError",
    "ConnectionClosedError",
    "ConnectionFailedError",
    "MessageTooLargeError",
    # Storage
    "StorageError",
    "StorageFileNotFoundError",
    "InvalidKeyError",
    "PermissionDeniedError",
    "QuotaExceededError",
    # API
    "FastApiException",
    # App
    "MissingSecretError",
    # Security
    "PasswordValidationError",
]
