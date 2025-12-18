"""Logging utilities for svc-infra applications.

This module provides logging utilities optimized for containerized
environments like Railway, Render, and Kubernetes, where log buffering
can cause visibility issues.

Features:
- Force flush for immediate log visibility in containers
- JSON-formatted structured logging
- Context injection for request tracing
- Pre-configured loggers with sensible defaults

Example:
    >>> from svc_infra.logging import flush, get_logger, configure_for_container
    >>>
    >>> # Configure logging at app startup
    >>> configure_for_container()
    >>>
    >>> # Get a logger
    >>> logger = get_logger(__name__)
    >>> logger.info("Starting application", extra={"version": "1.0.0"})
    >>>
    >>> # Force flush after critical operations
    >>> flush()
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

# Context variables for structured logging
_log_context: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "log_context", default={}
)

# Default log level from environment
DEFAULT_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

# Whether to use JSON format (default: True in containers)
USE_JSON_FORMAT = os.environ.get("LOG_FORMAT", "").lower() != "text"


def flush() -> None:
    """
    Force flush stdout and stderr for immediate log visibility.

    In containerized environments (Docker, Railway, Kubernetes), Python's
    output buffering can delay log visibility. Call this after critical
    operations to ensure logs are immediately visible.

    This is a no-op in terms of log content but ensures buffered output
    is written to the underlying streams.

    Example:
        >>> import logging
        >>> from svc_infra.logging import flush
        >>>
        >>> logging.info("Starting database migration...")
        >>> # ... perform migration ...
        >>> logging.info("Migration complete")
        >>> flush()  # Ensure logs are visible in container logs
    """
    sys.stdout.flush()
    sys.stderr.flush()


class JsonFormatter(logging.Formatter):
    """
    JSON log formatter for structured logging.

    Produces JSON-formatted log lines suitable for log aggregation
    systems like Datadog, Elastic, or CloudWatch.

    Output format:
        {"timestamp": "...", "level": "INFO", "logger": "...", "message": "...", ...}

    Any extra fields passed to the logger are included in the output.
    Context from `with_context()` is also merged in.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON."""
        # Base log structure
        log_dict: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_dict["exception"] = self.formatException(record.exc_info)

        # Add context from context variable
        context = _log_context.get()
        if context:
            log_dict.update(context)

        # Add any extra fields from the log call
        # Skip standard LogRecord attributes
        standard_attrs = {
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "exc_info",
            "exc_text",
            "thread",
            "threadName",
            "taskName",
            "message",
        }
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                log_dict[key] = value

        return json.dumps(log_dict, default=str)


class TextFormatter(logging.Formatter):
    """
    Human-readable text formatter with context support.

    Suitable for local development where JSON is harder to read.

    Output format:
        2024-01-15 10:30:45 [INFO] logger.name: Message {context}
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as human-readable text."""
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        base = f"{timestamp} [{record.levelname}] {record.name}: {record.getMessage()}"

        # Add context if present
        context = _log_context.get()
        if context:
            context_str = " ".join(f"{k}={v}" for k, v in context.items())
            base = f"{base} [{context_str}]"

        # Add exception if present
        if record.exc_info:
            base = f"{base}\n{self.formatException(record.exc_info)}"

        return base


def configure_for_container(
    level: str | None = None,
    json_format: bool | None = None,
    stream: Any = None,
) -> None:
    """
    Configure logging for containerized environments.

    Sets up:
    - Unbuffered output for immediate log visibility
    - JSON or text formatting based on environment
    - Appropriate log level from LOG_LEVEL env var

    This should be called once at application startup, typically
    before any other logging configuration.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR). Defaults to LOG_LEVEL env var or INFO.
        json_format: If True, use JSON format; if False, use text. Defaults to LOG_FORMAT env var.
        stream: Output stream. Defaults to sys.stderr.

    Environment Variables:
        LOG_LEVEL: Default log level (default: INFO)
        LOG_FORMAT: "text" for human-readable, anything else for JSON (default: JSON)
        PYTHONUNBUFFERED: Set to "1" for unbuffered output

    Example:
        >>> from svc_infra.logging import configure_for_container
        >>>
        >>> # In your app's main.py or __init__.py
        >>> configure_for_container()
        >>>
        >>> # Or with explicit settings
        >>> configure_for_container(level="DEBUG", json_format=False)
    """
    # Determine settings
    log_level = level or DEFAULT_LOG_LEVEL
    use_json = json_format if json_format is not None else USE_JSON_FORMAT
    output_stream = stream or sys.stderr

    # Force unbuffered output
    os.environ["PYTHONUNBUFFERED"] = "1"

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Create handler with appropriate formatter
    handler = logging.StreamHandler(output_stream)
    handler.setLevel(getattr(logging, log_level, logging.INFO))

    if use_json:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(TextFormatter())

    root_logger.addHandler(handler)

    # Also configure uvicorn loggers to use our format
    for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.addHandler(handler)
        uvicorn_logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """
    Get a pre-configured logger instance.

    Returns a logger that respects the configuration set by
    `configure_for_container()`. If that hasn't been called,
    the logger will use Python's default configuration.

    Args:
        name: Logger name, typically `__name__` of the module.

    Returns:
        Configured logger instance.

    Example:
        >>> from svc_infra.logging import get_logger
        >>>
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing request", extra={"user_id": 123})
    """
    return logging.getLogger(name)


@contextmanager
def with_context(**kwargs: Any) -> Iterator[None]:
    """
    Context manager for adding structured context to log messages.

    All log messages within the context will include the specified
    key-value pairs, making it easy to trace requests or operations
    across multiple log statements.

    Args:
        **kwargs: Key-value pairs to add to log context.

    Yields:
        None

    Example:
        >>> from svc_infra.logging import with_context, get_logger
        >>>
        >>> logger = get_logger(__name__)
        >>>
        >>> with with_context(request_id="abc-123", user_id=42):
        ...     logger.info("Processing request")
        ...     # Output includes: {"request_id": "abc-123", "user_id": 42, ...}
        ...     do_something()
        ...     logger.info("Request complete")
        >>>
        >>> # Context is automatically cleared after the block
        >>> logger.info("No context here")
    """
    # Get current context and merge with new values
    current = _log_context.get()
    new_context = {**current, **kwargs}

    # Set new context
    token = _log_context.set(new_context)
    try:
        yield
    finally:
        # Restore previous context
        _log_context.reset(token)


def set_context(**kwargs: Any) -> None:
    """
    Set persistent log context (not scoped like with_context).

    Use this for context that should persist across multiple operations,
    like tenant_id or user_id for the entire request lifecycle.

    Args:
        **kwargs: Key-value pairs to add to log context.

    Example:
        >>> from svc_infra.logging import set_context, clear_context, get_logger
        >>>
        >>> logger = get_logger(__name__)
        >>>
        >>> # In request middleware
        >>> set_context(request_id="abc-123", tenant_id="tenant-1")
        >>>
        >>> # All subsequent logs include context
        >>> logger.info("Processing...")
        >>>
        >>> # Clear at end of request
        >>> clear_context()
    """
    current = _log_context.get()
    _log_context.set({**current, **kwargs})


def clear_context() -> None:
    """
    Clear all log context.

    Call this at the end of a request or operation to ensure
    context doesn't leak to subsequent operations.

    Example:
        >>> from svc_infra.logging import set_context, clear_context
        >>>
        >>> set_context(request_id="abc-123")
        >>> # ... handle request ...
        >>> clear_context()  # Clean up
    """
    _log_context.set({})


def get_context() -> dict[str, Any]:
    """
    Get the current log context.

    Returns:
        Dictionary of current context key-value pairs.

    Example:
        >>> from svc_infra.logging import set_context, get_context
        >>>
        >>> set_context(request_id="abc-123")
        >>> ctx = get_context()
        >>> print(ctx)  # {"request_id": "abc-123"}
    """
    return _log_context.get().copy()


__all__ = [
    "flush",
    "configure_for_container",
    "get_logger",
    "with_context",
    "set_context",
    "clear_context",
    "get_context",
    "JsonFormatter",
    "TextFormatter",
]
