# Error Handling Guide

This guide documents the exception hierarchies and error handling patterns in svc-infra.

## Exception Hierarchy

```
Exception
└── SvcInfraError (base for all svc-infra exceptions)
    ├── ConfigurationError
    │   └── MissingSecretError
    ├── AuthenticationError
    │   ├── InvalidCredentialsError
    │   ├── TokenExpiredError
    │   └── SessionNotFoundError
    ├── AuthorizationError
    │   └── InsufficientPermissionsError
    ├── DatabaseError
    │   ├── ConnectionError
    │   ├── QueryError
    │   └── MigrationError
    ├── CacheError
    │   ├── CacheConnectionError
    │   └── CacheMissError
    ├── StorageError
    │   ├── FileNotFoundError
    │   └── UploadError
    ├── RateLimitError
    ├── ValidationError
    └── WebhookError
        ├── SignatureVerificationError
        └── DeliveryError
```

## Best Practices

### 1. Catch Specific Exceptions

```python
from svc_infra.exceptions import (
    AuthenticationError,
    TokenExpiredError,
    CacheError,
)

try:
    user = await authenticate(token)
except TokenExpiredError:
    # Handle expired token specifically
    return redirect_to_login()
except AuthenticationError:
    # Handle other auth errors
    raise HTTPException(status_code=401)
```

### 2. Never Silently Swallow Exceptions

```python
# ❌ WRONG
try:
    risky_operation()
except Exception:
    pass

# ✅ CORRECT
try:
    risky_operation()
except SpecificError as e:
    logger.warning(f"Operation failed: {e}")
    # Handle or re-raise
```

### 3. Add Context When Re-Raising

```python
try:
    result = external_api.call()
except ExternalAPIError as e:
    raise DatabaseError(f"Failed to sync data: {e}") from e
```

### 4. Use Error Codes for API Responses

```python
class APIError:
    INVALID_TOKEN = "auth.invalid_token"
    EXPIRED_TOKEN = "auth.expired_token"
    RATE_LIMITED = "rate.limit_exceeded"

# In response:
{
    "error": {
        "code": "auth.expired_token",
        "message": "Your session has expired. Please log in again."
    }
}
```

## HTTP Status Code Mapping

| Exception | HTTP Status |
|-----------|-------------|
| ValidationError | 400 |
| AuthenticationError | 401 |
| AuthorizationError | 403 |
| NotFoundError | 404 |
| RateLimitError | 429 |
| DatabaseError | 500 |
| ConfigurationError | 500 |

## Logging Errors

```python
import logging

logger = logging.getLogger(__name__)

try:
    process_request(data)
except ValidationError as e:
    # User error - log at WARNING
    logger.warning(f"Invalid request: {e}")
    raise
except DatabaseError as e:
    # System error - log at ERROR with stack trace
    logger.error(f"Database error: {e}", exc_info=True)
    raise
except Exception as e:
    # Unexpected - log at CRITICAL
    logger.critical(f"Unexpected error: {e}", exc_info=True)
    raise
```

## Retry Patterns

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(TransientError),
)
async def call_external_api():
    return await api.request()
```
