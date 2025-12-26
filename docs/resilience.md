# Resilience Patterns

This guide covers retry logic, circuit breakers, and timeout enforcement for building robust services that handle failures gracefully.

## Why Resilience?

- **Retry logic** handles transient failures (network blips, temporary unavailability)
- **Circuit breakers** prevent cascading failures when dependencies are down
- **Timeouts** ensure operations don't hang indefinitely

## Quick Start

```python
from svc_infra.resilience import with_retry, CircuitBreaker, RetryConfig

# Retry with exponential backoff
@with_retry(max_attempts=3, base_delay=0.1)
async def fetch_data():
    return await external_api.get("/data")

# Circuit breaker for failing dependencies
breaker = CircuitBreaker("payment-service", failure_threshold=5)

async with breaker:
    result = await payment_service.charge(amount)
```

## Retry with Exponential Backoff

The `with_retry` decorator automatically retries failed async operations with configurable backoff.

### Basic Usage

```python
from svc_infra.resilience import with_retry

@with_retry(max_attempts=3)
async def fetch_user(user_id: str):
    return await api.get(f"/users/{user_id}")
```

### Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_attempts` | 3 | Total attempts including first try |
| `base_delay` | 0.1 | Initial delay in seconds |
| `max_delay` | 60.0 | Maximum delay cap |
| `exponential_base` | 2.0 | Backoff multiplier |
| `jitter` | 0.1 | Random jitter factor (0.0-1.0) |
| `retry_on` | `(Exception,)` | Exception types to retry |
| `on_retry` | None | Callback `(attempt, exception) -> None` |

### Retry Only on Specific Exceptions

```python
from svc_infra.resilience import with_retry

@with_retry(
    max_attempts=5,
    retry_on=(TimeoutError, ConnectionError),
)
async def connect_to_service():
    return await socket.connect()
```

### Retry Callback for Logging/Metrics

```python
from svc_infra.resilience import with_retry

def on_retry(attempt: int, exc: Exception) -> None:
    logger.warning(f"Attempt {attempt} failed: {exc}")
    metrics.increment("api.retry", tags={"attempt": attempt})

@with_retry(max_attempts=3, on_retry=on_retry)
async def fetch_data():
    return await api.get("/data")
```

### Sync Function Retry

For synchronous functions, use `retry_sync`:

```python
from svc_infra.resilience import retry_sync

@retry_sync(max_attempts=3, base_delay=0.5)
def fetch_config():
    return requests.get("/config").json()
```

### Using RetryConfig

For reusable configuration across multiple functions:

```python
from svc_infra.resilience import RetryConfig, with_retry

api_retry = RetryConfig(
    max_attempts=5,
    base_delay=0.2,
    max_delay=30.0,
    retry_on=(TimeoutError, ConnectionError),
)

# Use config values in decorator
@with_retry(
    max_attempts=api_retry.max_attempts,
    base_delay=api_retry.base_delay,
    max_delay=api_retry.max_delay,
    retry_on=api_retry.retry_on,
)
async def fetch():
    ...
```

### RetryExhaustedError

When all retries fail, `RetryExhaustedError` is raised:

```python
from svc_infra.resilience import with_retry, RetryExhaustedError

@with_retry(max_attempts=3)
async def flaky_operation():
    raise ValueError("Always fails")

try:
    await flaky_operation()
except RetryExhaustedError as e:
    print(f"Failed after {e.attempts} attempts")
    print(f"Last error: {e.last_exception}")
```

## Circuit Breaker

The circuit breaker pattern prevents repeated calls to a failing service, giving it time to recover.

### States

```
    ┌─────────┐  failure threshold   ┌──────┐
    │ CLOSED  │ ──────────────────► │ OPEN │
    │ (normal)│                      │(fail)│
    └─────────┘                      └──────┘
         ▲                              │
         │                              │ recovery timeout
         │      success threshold       ▼
         │ ◄──────────────────── ┌───────────┐
         │                       │ HALF_OPEN │
         └────────────────────── │  (test)   │
              failure            └───────────┘
```

- **CLOSED**: Normal operation, calls pass through
- **OPEN**: Calls blocked, `CircuitBreakerError` raised immediately
- **HALF_OPEN**: Limited calls allowed to test if service recovered

### Basic Usage

```python
from svc_infra.resilience import CircuitBreaker

breaker = CircuitBreaker(
    name="payment-api",
    failure_threshold=5,      # Open after 5 failures
    recovery_timeout=30.0,    # Wait 30s before trying again
)

async with breaker:
    result = await payment_api.charge(amount)
```

### Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `name` | "default" | Name for logging/metrics |
| `failure_threshold` | 5 | Failures before opening |
| `recovery_timeout` | 30.0 | Seconds before half-open |
| `half_open_max_calls` | 3 | Max calls in half-open |
| `success_threshold` | 2 | Successes to close circuit |
| `failure_exceptions` | `(Exception,)` | Exception types that count as failures |

### Using as Decorator

```python
from svc_infra.resilience import CircuitBreaker

breaker = CircuitBreaker("external-api", failure_threshold=5)

@breaker.protect
async def call_external():
    return await external_api.get("/data")
```

### Checking Circuit State

```python
from svc_infra.resilience import CircuitBreaker, CircuitState

breaker = CircuitBreaker("api")

if breaker.state == CircuitState.OPEN:
    # Fall back to cache or default
    return cached_value

# Normal path
async with breaker:
    return await api.get("/data")
```

### Handling CircuitBreakerError

```python
from svc_infra.resilience import CircuitBreaker, CircuitBreakerError

breaker = CircuitBreaker("api")

try:
    async with breaker:
        return await api.call()
except CircuitBreakerError as e:
    logger.warning(f"Circuit {e.name} is {e.state.value}")
    if e.remaining_timeout:
        logger.info(f"Retry in {e.remaining_timeout:.1f}s")
    return fallback_value
```

### Circuit Breaker Statistics

```python
from svc_infra.resilience import CircuitBreaker

breaker = CircuitBreaker("api")

# After some operations...
stats = breaker.stats

print(f"Total calls: {stats.total_calls}")
print(f"Successful: {stats.successful_calls}")
print(f"Failed: {stats.failed_calls}")
print(f"Rejected: {stats.rejected_calls}")
print(f"State changes: {stats.state_changes}")
```

### Manual Reset

For testing or manual intervention, you can force-reset the circuit:

```python
breaker.reset()  # Force circuit to CLOSED state, clear counters
```

> **Warning**: Use `reset()` sparingly in production. It's mainly for testing or emergency recovery.

## Combining Retry and Circuit Breaker

For robust external API calls, combine both patterns:

```python
from svc_infra.resilience import with_retry, CircuitBreaker, CircuitBreakerError

# Circuit breaker at the service level
api_breaker = CircuitBreaker("external-api", failure_threshold=5)

# Retry for transient failures, but not when circuit is open
@with_retry(
    max_attempts=3,
    retry_on=(TimeoutError, ConnectionError),  # NOT CircuitBreakerError
)
async def fetch_with_retry():
    async with api_breaker:
        return await external_api.get("/data")

async def fetch_data():
    try:
        return await fetch_with_retry()
    except CircuitBreakerError:
        # Circuit is open - use fallback
        return get_cached_data()
```

## Best Practices

### 1. Set Appropriate Thresholds

```python
# High-traffic, latency-sensitive
breaker = CircuitBreaker(
    failure_threshold=10,     # Need more data points
    recovery_timeout=10.0,    # Recover faster
)

# Low-traffic, can wait
breaker = CircuitBreaker(
    failure_threshold=3,      # Open quickly
    recovery_timeout=60.0,    # Longer recovery
)
```

### 2. Use Specific Exception Types

```python
# ❌ Retries on ALL exceptions (including validation errors)
@with_retry(max_attempts=3)
async def fetch():
    ...

# ✅ Only retry on transient failures
@with_retry(max_attempts=3, retry_on=(TimeoutError, ConnectionError))
async def fetch():
    ...
```

### 3. Add Observability

```python
def on_retry(attempt: int, exc: Exception) -> None:
    metrics.increment("retry", tags={"attempt": str(attempt)})
    logger.warning(f"Retry {attempt}: {exc}")

@with_retry(max_attempts=3, on_retry=on_retry)
async def fetch():
    ...
```

### 4. Don't Retry Non-Idempotent Operations

```python
# ❌ Dangerous - may charge multiple times
@with_retry(max_attempts=3)
async def charge_card(amount):
    ...

# ✅ Use idempotency keys instead
async def charge_card(amount, idempotency_key: str):
    return await payment_api.charge(
        amount=amount,
        idempotency_key=idempotency_key,
    )
```

### 5. Implement Fallbacks

```python
from svc_infra.resilience import CircuitBreaker, CircuitBreakerError

breaker = CircuitBreaker("recommendations")

async def get_recommendations(user_id: str):
    try:
        async with breaker:
            return await recommendation_service.get(user_id)
    except CircuitBreakerError:
        # Graceful degradation
        return get_default_recommendations()
```

## API Reference

### Retry

| Export | Type | Description |
|--------|------|-------------|
| `with_retry` | Decorator | Async function retry with backoff |
| `retry_sync` | Decorator | Sync function retry with backoff |
| `RetryConfig` | Dataclass | Reusable retry configuration |
| `RetryExhaustedError` | Exception | Raised when all retries fail |

### Circuit Breaker

| Export | Type | Description |
|--------|------|-------------|
| `CircuitBreaker` | Class | Circuit breaker implementation |
| `CircuitBreakerError` | Exception | Raised when circuit is open |
| `CircuitBreakerStats` | Dataclass | Statistics about circuit usage |
| `CircuitState` | Enum | CLOSED, OPEN, HALF_OPEN |

## See Also

- [Timeouts & Resource Limits](timeouts-and-resource-limits.md) - Request and handler timeouts
- [Error Handling](error-handling.md) - Exception hierarchy and patterns
- [Idempotency](idempotency.md) - Safe retries for non-idempotent operations
