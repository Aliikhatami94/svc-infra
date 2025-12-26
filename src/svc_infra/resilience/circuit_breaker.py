"""Circuit breaker for protecting against cascading failures.

A circuit breaker prevents repeated calls to a failing service,
giving it time to recover. The circuit has three states:

- CLOSED: Normal operation, calls pass through.
- OPEN: Calls are blocked, CircuitBreakerError is raised.
- HALF_OPEN: Limited calls allowed to test if service recovered.

Example:
    >>> from svc_infra.resilience import CircuitBreaker
    >>>
    >>> breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0)
    >>>
    >>> async with breaker:
    ...     result = await external_service.call()
    >>>
    >>> # Or use as decorator
    >>> @breaker.protect
    ... async def call_external():
    ...     return await external_service.call()
"""

from __future__ import annotations

import asyncio
import functools
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


class CircuitState(Enum):
    """State of the circuit breaker."""

    CLOSED = "closed"
    """Normal operation, calls pass through."""

    OPEN = "open"
    """Circuit is open, calls are blocked."""

    HALF_OPEN = "half_open"
    """Testing if service recovered, limited calls allowed."""


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open.

    Attributes:
        name: Name of the circuit breaker.
        state: Current state of the circuit.
        remaining_timeout: Seconds until circuit will try half-open.
    """

    def __init__(
        self,
        name: str,
        *,
        state: CircuitState,
        remaining_timeout: float | None = None,
    ):
        self.name = name
        self.state = state
        self.remaining_timeout = remaining_timeout
        message = f"Circuit breaker '{name}' is {state.value}"
        if remaining_timeout is not None:
            message += f" (retry in {remaining_timeout:.1f}s)"
        super().__init__(message)


@dataclass
class CircuitBreakerStats:
    """Statistics for a circuit breaker.

    Attributes:
        total_calls: Total number of calls attempted.
        successful_calls: Number of successful calls.
        failed_calls: Number of failed calls.
        rejected_calls: Number of calls rejected due to open circuit.
        state_changes: Number of state transitions.
    """

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    state_changes: int = 0


class CircuitBreaker:
    """Circuit breaker for protecting against cascading failures.

    The circuit breaker monitors call failures and opens the circuit
    when failures exceed a threshold, preventing further calls until
    the service has time to recover.

    Args:
        name: Name for this circuit breaker (for logging/metrics).
        failure_threshold: Number of failures before opening circuit.
        recovery_timeout: Seconds to wait before trying half-open.
        half_open_max_calls: Max calls in half-open state before decision.
        success_threshold: Successes in half-open to close circuit.
        failure_exceptions: Exception types that count as failures.

    Example:
        >>> breaker = CircuitBreaker(
        ...     name="external-api",
        ...     failure_threshold=5,
        ...     recovery_timeout=30.0,
        ... )
        >>>
        >>> async with breaker:
        ...     result = await api.call()
        >>>
        >>> # Check state
        >>> if breaker.state == CircuitState.OPEN:
        ...     print("Service is down")
    """

    def __init__(
        self,
        name: str = "default",
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
        success_threshold: int = 2,
        failure_exceptions: tuple[type[Exception], ...] = (Exception,),
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.success_threshold = success_threshold
        self.failure_exceptions = failure_exceptions

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float | None = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
        self._stats = CircuitBreakerStats()

    @property
    def state(self) -> CircuitState:
        """Get the current circuit state."""
        return self._state

    @property
    def stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics."""
        return self._stats

    def _should_try_half_open(self) -> bool:
        """Check if enough time has passed to try half-open."""
        if self._state != CircuitState.OPEN:
            return False
        if self._last_failure_time is None:
            return True
        elapsed = time.monotonic() - self._last_failure_time
        return elapsed >= self.recovery_timeout

    def _remaining_timeout(self) -> float | None:
        """Get remaining time until half-open attempt."""
        if self._state != CircuitState.OPEN:
            return None
        if self._last_failure_time is None:
            return 0.0
        elapsed = time.monotonic() - self._last_failure_time
        remaining = self.recovery_timeout - elapsed
        return max(0.0, remaining)

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        if self._state != new_state:
            logger.info(
                "Circuit breaker '%s' state: %s -> %s",
                self.name,
                self._state.value,
                new_state.value,
            )
            self._state = new_state
            self._stats.state_changes += 1

            if new_state == CircuitState.CLOSED:
                self._failure_count = 0
                self._success_count = 0
            elif new_state == CircuitState.HALF_OPEN:
                self._half_open_calls = 0
                self._success_count = 0

    async def _record_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            self._stats.successful_calls += 1

            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    async def _record_failure(self, exc: Exception) -> None:
        """Record a failed call."""
        async with self._lock:
            self._stats.failed_calls += 1
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open goes back to open
                self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
                    logger.warning(
                        "Circuit breaker '%s' opened after %d failures: %s",
                        self.name,
                        self._failure_count,
                        exc,
                    )

    async def _check_state(self) -> None:
        """Check if call should be allowed."""
        async with self._lock:
            self._stats.total_calls += 1

            if self._state == CircuitState.CLOSED:
                return

            if self._state == CircuitState.OPEN:
                if self._should_try_half_open():
                    self._transition_to(CircuitState.HALF_OPEN)
                else:
                    self._stats.rejected_calls += 1
                    raise CircuitBreakerError(
                        self.name,
                        state=self._state,
                        remaining_timeout=self._remaining_timeout(),
                    )

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    self._stats.rejected_calls += 1
                    raise CircuitBreakerError(
                        self.name,
                        state=self._state,
                        remaining_timeout=None,
                    )
                self._half_open_calls += 1

    async def __aenter__(self) -> CircuitBreaker:
        """Enter circuit breaker context."""
        await self._check_state()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """Exit circuit breaker context."""
        if exc_val is None:
            await self._record_success()
        elif isinstance(exc_val, self.failure_exceptions):
            await self._record_failure(exc_val)
        # Don't suppress the exception
        return False

    def protect(
        self,
        fn: Callable[P, Awaitable[R]],
    ) -> Callable[P, Awaitable[R]]:
        """Decorator to protect an async function with this circuit breaker.

        Args:
            fn: Async function to protect.

        Returns:
            Wrapped async function.

        Example:
            >>> @breaker.protect
            ... async def call_api():
            ...     return await api.get("/data")
        """

        @functools.wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            async with self:
                result = await fn(*args, **kwargs)
            return result

        return wrapper

    def reset(self) -> None:
        """Reset the circuit breaker to closed state.

        Use this for testing or manual intervention.
        """
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._half_open_calls = 0
        logger.info("Circuit breaker '%s' reset to CLOSED", self.name)


__all__ = [
    "CircuitBreaker",
    "CircuitBreakerError",
    "CircuitBreakerStats",
    "CircuitState",
]
