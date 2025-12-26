"""Resilience utilities for svc-infra.

This module provides utilities for building resilient services:
- Retry with exponential backoff
- Circuit breaker for protecting against cascading failures
- Timeout enforcement

Example:
    >>> from svc_infra.resilience import with_retry, CircuitBreaker
    >>>
    >>> @with_retry(max_attempts=3)
    ... async def fetch_data():
    ...     return await external_api.get()
    >>>
    >>> breaker = CircuitBreaker(failure_threshold=5)
    >>> async with breaker:
    ...     await risky_operation()
"""

from svc_infra.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerStats,
    CircuitState,
)
from svc_infra.resilience.retry import (
    RetryConfig,
    RetryExhaustedError,
    retry_sync,
    with_retry,
)

__all__ = [
    # Retry
    "RetryConfig",
    "RetryExhaustedError",
    "retry_sync",
    "with_retry",
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerError",
    "CircuitBreakerStats",
    "CircuitState",
]
