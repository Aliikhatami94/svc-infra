"""Retry utility with exponential backoff.

This module provides a decorator for retrying async functions with
configurable backoff strategies. It does NOT depend on tenacity to
keep dependencies minimal.

Example:
    >>> from svc_infra.resilience import with_retry
    >>>
    >>> @with_retry(max_attempts=3, base_delay=0.1)
    ... async def fetch_data():
    ...     return await api.get("/data")
    >>>
    >>> # Retry only on specific exceptions
    >>> @with_retry(max_attempts=5, retry_on=(TimeoutError, ConnectionError))
    ... async def connect():
    ...     return await socket.connect()
"""

from __future__ import annotations

import asyncio
import functools
import logging
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ParamSpec, TypeVar

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


class RetryExhaustedError(Exception):
    """Raised when all retry attempts have been exhausted.

    Attributes:
        attempts: Number of attempts made.
        last_exception: The last exception that caused a retry.
    """

    def __init__(
        self,
        message: str,
        *,
        attempts: int,
        last_exception: Exception | None = None,
    ):
        self.attempts = attempts
        self.last_exception = last_exception
        super().__init__(message)

    def __repr__(self) -> str:
        return f"RetryExhaustedError(attempts={self.attempts})"


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_attempts: Maximum number of attempts (including first try).
        base_delay: Initial delay in seconds before first retry.
        max_delay: Maximum delay in seconds (caps exponential growth).
        exponential_base: Base for exponential backoff (default 2).
        jitter: Add random jitter to delays (0.0-1.0, default 0.1).
        retry_on: Tuple of exception types to retry on.
    """

    max_attempts: int = 3
    base_delay: float = 0.1
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: float = 0.1
    retry_on: tuple[type[Exception], ...] = field(default_factory=lambda: (Exception,))

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number (1-indexed).

        Uses exponential backoff with optional jitter:
        delay = min(base_delay * (exponential_base ** (attempt - 1)), max_delay)
        delay = delay * (1 + random.uniform(-jitter, jitter))
        """
        delay = self.base_delay * (self.exponential_base ** (attempt - 1))
        delay = min(delay, self.max_delay)

        if self.jitter > 0:
            jitter_amount = delay * random.uniform(-self.jitter, self.jitter)
            delay = max(0, delay + jitter_amount)

        return delay


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: float = 0.1,
    retry_on: tuple[type[Exception], ...] = (Exception,),
    *,
    on_retry: Callable[[int, Exception], None] | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Decorator for retrying async functions with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts (including first try).
        base_delay: Initial delay in seconds before first retry.
        max_delay: Maximum delay in seconds (caps exponential growth).
        exponential_base: Base for exponential backoff (default 2).
        jitter: Add random jitter to delays (0.0-1.0, default 0.1).
        retry_on: Tuple of exception types to retry on.
        on_retry: Optional callback called on each retry (attempt, exception).

    Returns:
        Decorated async function with retry logic.

    Example:
        >>> @with_retry(max_attempts=3, retry_on=(ConnectionError, TimeoutError))
        ... async def fetch():
        ...     return await api.get("/data")
        >>>
        >>> # With callback
        >>> def log_retry(attempt, exc):
        ...     print(f"Retry {attempt}: {exc}")
        >>>
        >>> @with_retry(max_attempts=3, on_retry=log_retry)
        ... async def fetch():
        ...     return await api.get("/data")
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        retry_on=retry_on,
    )

    def decorator(fn: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            last_exception: Exception | None = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    return await fn(*args, **kwargs)
                except config.retry_on as e:
                    last_exception = e

                    if attempt == config.max_attempts:
                        # Last attempt failed, raise RetryExhaustedError
                        logger.warning(
                            "Retry exhausted after %d attempts for %s: %s",
                            attempt,
                            fn.__name__,
                            e,
                        )
                        raise RetryExhaustedError(
                            f"All {config.max_attempts} retry attempts exhausted",
                            attempts=attempt,
                            last_exception=e,
                        ) from e

                    # Calculate delay and wait
                    delay = config.calculate_delay(attempt)
                    logger.debug(
                        "Retry %d/%d for %s in %.3fs: %s",
                        attempt,
                        config.max_attempts,
                        fn.__name__,
                        delay,
                        e,
                    )

                    if on_retry:
                        on_retry(attempt, e)

                    await asyncio.sleep(delay)

            # Should never reach here, but satisfy type checker
            raise RetryExhaustedError(
                "Retry loop completed without success",
                attempts=config.max_attempts,
                last_exception=last_exception,
            )

        return wrapper

    return decorator


def retry_sync(
    max_attempts: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: float = 0.1,
    retry_on: tuple[type[Exception], ...] = (Exception,),
    *,
    on_retry: Callable[[int, Exception], None] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator for retrying sync functions with exponential backoff.

    Same as with_retry but for synchronous functions.

    Args:
        max_attempts: Maximum number of attempts (including first try).
        base_delay: Initial delay in seconds before first retry.
        max_delay: Maximum delay in seconds.
        exponential_base: Base for exponential backoff.
        jitter: Add random jitter to delays.
        retry_on: Tuple of exception types to retry on.
        on_retry: Optional callback called on each retry.

    Returns:
        Decorated sync function with retry logic.
    """
    import time

    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        retry_on=retry_on,
    )

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            last_exception: Exception | None = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except config.retry_on as e:
                    last_exception = e

                    if attempt == config.max_attempts:
                        logger.warning(
                            "Retry exhausted after %d attempts for %s: %s",
                            attempt,
                            fn.__name__,
                            e,
                        )
                        raise RetryExhaustedError(
                            f"All {config.max_attempts} retry attempts exhausted",
                            attempts=attempt,
                            last_exception=e,
                        ) from e

                    delay = config.calculate_delay(attempt)
                    logger.debug(
                        "Retry %d/%d for %s in %.3fs: %s",
                        attempt,
                        config.max_attempts,
                        fn.__name__,
                        delay,
                        e,
                    )

                    if on_retry:
                        on_retry(attempt, e)

                    time.sleep(delay)

            raise RetryExhaustedError(
                "Retry loop completed without success",
                attempts=config.max_attempts,
                last_exception=last_exception,
            )

        return wrapper

    return decorator


__all__ = [
    "RetryConfig",
    "RetryExhaustedError",
    "retry_sync",
    "with_retry",
]
