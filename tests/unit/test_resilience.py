"""Tests for svc-infra resilience utilities.

Tests for retry, circuit breaker, and related utilities.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from svc_infra.resilience import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitState,
    RetryConfig,
    RetryExhaustedError,
    retry_sync,
    with_retry,
)

if TYPE_CHECKING:
    pass


# =============================================================================
# RetryConfig Tests
# =============================================================================


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.base_delay == 0.1
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter == 0.1

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=0.5,
            max_delay=30.0,
            exponential_base=3.0,
            jitter=0.2,
        )
        assert config.max_attempts == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0
        assert config.exponential_base == 3.0
        assert config.jitter == 0.2

    def test_calculate_delay_exponential(self) -> None:
        """Test delay calculation with exponential backoff."""
        config = RetryConfig(base_delay=1.0, jitter=0.0)

        # First attempt: 1.0 * 2^0 = 1.0
        assert config.calculate_delay(1) == 1.0
        # Second attempt: 1.0 * 2^1 = 2.0
        assert config.calculate_delay(2) == 2.0
        # Third attempt: 1.0 * 2^2 = 4.0
        assert config.calculate_delay(3) == 4.0

    def test_calculate_delay_respects_max(self) -> None:
        """Test delay is capped at max_delay."""
        config = RetryConfig(base_delay=1.0, max_delay=5.0, jitter=0.0)

        # Would be 512 without cap
        assert config.calculate_delay(10) == 5.0


# =============================================================================
# with_retry Tests
# =============================================================================


class TestWithRetry:
    """Tests for with_retry decorator."""

    @pytest.mark.asyncio
    async def test_success_no_retry(self) -> None:
        """Test successful call doesn't retry."""
        call_count = 0

        @with_retry(max_attempts=3)
        async def success() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await success()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_failure(self) -> None:
        """Test retries on failure."""
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.001)
        async def fails_twice() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Not yet")
            return "success"

        result = await fails_twice()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_exhausts_retries(self) -> None:
        """Test raises RetryExhaustedError after all attempts."""

        @with_retry(max_attempts=3, base_delay=0.001)
        async def always_fails() -> None:
            raise ValueError("Always fails")

        with pytest.raises(RetryExhaustedError) as exc_info:
            await always_fails()

        assert exc_info.value.attempts == 3
        assert isinstance(exc_info.value.last_exception, ValueError)

    @pytest.mark.asyncio
    async def test_retry_only_on_specified(self) -> None:
        """Test only retries on specified exceptions."""
        call_count = 0

        @with_retry(max_attempts=3, retry_on=(ValueError,))
        async def fails() -> None:
            nonlocal call_count
            call_count += 1
            raise TypeError("Not retryable")

        with pytest.raises(TypeError):
            await fails()

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_on_retry_callback(self) -> None:
        """Test on_retry callback is called."""
        callbacks: list[tuple[int, Exception]] = []

        def on_retry(attempt: int, exc: Exception) -> None:
            callbacks.append((attempt, exc))

        @with_retry(max_attempts=3, base_delay=0.001, on_retry=on_retry)
        async def fails_then_succeeds() -> str:
            if len(callbacks) < 2:
                raise ValueError("Retry")
            return "success"

        result = await fails_then_succeeds()
        assert result == "success"
        assert len(callbacks) == 2
        assert callbacks[0][0] == 1
        assert callbacks[1][0] == 2


# =============================================================================
# retry_sync Tests
# =============================================================================


class TestRetrySync:
    """Tests for retry_sync decorator."""

    def test_sync_success(self) -> None:
        """Test successful sync function doesn't retry."""
        call_count = 0

        @retry_sync(max_attempts=3)
        def success() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = success()
        assert result == "success"
        assert call_count == 1

    def test_sync_retry(self) -> None:
        """Test sync function retries on failure."""
        call_count = 0

        @retry_sync(max_attempts=3, base_delay=0.001)
        def fails_once() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("First call fails")
            return "success"

        result = fails_once()
        assert result == "success"
        assert call_count == 2


# =============================================================================
# CircuitBreaker Tests
# =============================================================================


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    def test_initial_state_closed(self) -> None:
        """Test circuit starts in CLOSED state."""
        breaker = CircuitBreaker("test")
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_opens_after_failures(self) -> None:
        """Test circuit opens after failure threshold."""
        breaker = CircuitBreaker("test", failure_threshold=3)

        for _ in range(3):
            try:
                async with breaker:
                    raise ValueError("Failure")
            except ValueError:
                pass

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_rejects_when_open(self) -> None:
        """Test open circuit rejects calls."""
        breaker = CircuitBreaker("test", failure_threshold=1)

        # Trigger open
        try:
            async with breaker:
                raise ValueError()
        except ValueError:
            pass

        assert breaker.state == CircuitState.OPEN

        with pytest.raises(CircuitBreakerError):
            async with breaker:
                pass

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self) -> None:
        """Test circuit goes to half-open after recovery timeout."""
        breaker = CircuitBreaker(
            "test",
            failure_threshold=1,
            recovery_timeout=0.01,
            success_threshold=1,  # Only need 1 success to close
        )

        # Trigger open
        try:
            async with breaker:
                raise ValueError()
        except ValueError:
            pass

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery
        await asyncio.sleep(0.02)

        # Should allow call through (half-open) and close after success
        async with breaker:
            pass

        # Should be closed after success
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_protect_decorator(self) -> None:
        """Test protect decorator wraps function."""
        breaker = CircuitBreaker("test")

        @breaker.protect
        async def protected_fn() -> str:
            return "result"

        result = await protected_fn()
        assert result == "result"

    def test_reset(self) -> None:
        """Test manual reset."""
        breaker = CircuitBreaker("test")
        breaker._state = CircuitState.OPEN
        breaker._failure_count = 10

        breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        assert breaker._failure_count == 0

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self) -> None:
        """Test successful call resets failure count."""
        breaker = CircuitBreaker("test", failure_threshold=3)

        # Add 2 failures
        for _ in range(2):
            try:
                async with breaker:
                    raise ValueError()
            except ValueError:
                pass

        assert breaker._failure_count == 2

        # Successful call
        async with breaker:
            pass

        assert breaker._failure_count == 0


# =============================================================================
# CircuitBreakerError Tests
# =============================================================================


class TestCircuitBreakerError:
    """Tests for CircuitBreakerError."""

    def test_error_contains_state(self) -> None:
        """Test error includes circuit state."""
        err = CircuitBreakerError("test", state=CircuitState.OPEN)
        assert err.name == "test"
        assert err.state == CircuitState.OPEN


# =============================================================================
# Export Tests
# =============================================================================


class TestExports:
    """Tests for module exports."""

    def test_all_exports_importable(self) -> None:
        """Test all exports are importable."""
        from svc_infra.resilience import (
            CircuitBreaker,
            CircuitBreakerError,
            CircuitBreakerStats,
            CircuitState,
            RetryConfig,
            RetryExhaustedError,
            retry_sync,
            with_retry,
        )

        assert CircuitBreaker is not None
        assert CircuitBreakerError is not None
        assert CircuitBreakerStats is not None
        assert CircuitState is not None
        assert RetryConfig is not None
        assert RetryExhaustedError is not None
        assert callable(retry_sync)
        assert callable(with_retry)
