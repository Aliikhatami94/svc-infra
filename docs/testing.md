# Testing Guide

Mock implementations and test fixtures for testing applications built with svc-infra, without requiring external services.

## Overview

svc-infra provides testing utilities that eliminate the need for Redis, PostgreSQL, or other external services during testing:

- **MockCache**: In-memory cache backend with TTL and tag support
- **MockJobQueue**: Synchronous job queue with immediate or queued execution
- **Fixture Factories**: Pre-built factories for users and tenants
- **Pytest Integration**: Ready-to-use pytest fixtures

## Quick Start

### Mock Cache

```python
from svc_infra.testing import MockCache

cache = MockCache()

# Basic operations
cache.set("user:123", {"name": "Alice"}, ttl=300)
user = cache.get("user:123")  # {"name": "Alice"}

# Delete operations
cache.delete("user:123")
cache.delete_pattern("user:*")  # Delete all user keys

# Tag-based invalidation
cache.set("order:1", {"total": 100}, tags=["user:123"])
cache.set("order:2", {"total": 200}, tags=["user:123"])
cache.delete_by_tag("user:123")  # Deletes both orders
```

### Mock Job Queue

```python
from svc_infra.testing import MockJobQueue

queue = MockJobQueue()

# Register a handler
@queue.handler("send_email")
def handle_email(payload):
    print(f"Sending to {payload['to']}")
    return {"sent": True}

# Enqueue a job
job = queue.enqueue("send_email", {"to": "test@example.com"})

# Process all pending jobs
queue.process_all()  # Prints: "Sending to test@example.com"

# Check results
assert job.status == "completed"
assert job.result == {"sent": True}
```

---

## MockCache

### Initialization

```python
from svc_infra.testing import MockCache

# Default prefix
cache = MockCache()

# Custom prefix for namespacing
cache = MockCache(prefix="myapp")
```

### Basic Operations

```python
# Set with TTL (seconds)
cache.set("key", "value", ttl=60)

# Get (returns None if expired or missing)
value = cache.get("key")

# Check existence
exists = cache.exists("key")

# Delete single key
deleted = cache.delete("key")  # Returns True if existed

# Clear all
cache.clear()
```

### Pattern Operations

```python
# Delete all keys matching pattern
count = cache.delete_pattern("user:*")

# Get all keys matching pattern
keys = cache.keys("user:*")  # ["user:1", "user:2", ...]

# Get cache size (excluding expired)
size = cache.size()
```

### Tag-Based Invalidation

```python
# Set with tags
cache.set("order:1", {"total": 100}, ttl=300, tags=["user:123", "orders"])
cache.set("order:2", {"total": 200}, ttl=300, tags=["user:123", "orders"])

# Invalidate by tag (deletes all tagged items)
count = cache.delete_by_tag("user:123")  # Returns 2
```

### Testing Example

```python
import pytest
from svc_infra.testing import MockCache

@pytest.fixture
def cache():
    return MockCache()

async def test_user_caching(cache):
    # Simulate caching a user
    cache.set("user:123", {"id": 123, "name": "Alice"}, ttl=300)

    # Verify cache hit
    user = cache.get("user:123")
    assert user["name"] == "Alice"

    # Verify cache miss after delete
    cache.delete("user:123")
    assert cache.get("user:123") is None
```

---

## MockJobQueue

### Initialization

```python
from svc_infra.testing import MockJobQueue

# Default: jobs are queued for manual processing
queue = MockJobQueue()

# Sync mode: jobs execute immediately on enqueue
queue = MockJobQueue(sync_mode=True)
```

### Registering Handlers

```python
# Decorator style
@queue.handler("send_email")
def handle_email(payload):
    return send_email(payload["to"], payload["subject"])

# Programmatic registration
def handle_notification(payload):
    return notify_user(payload["user_id"], payload["message"])

queue.register_handler("notify", handle_notification)
```

### Enqueuing Jobs

```python
# Basic enqueue
job = queue.enqueue("send_email", {"to": "user@example.com"})

# With delay (seconds)
job = queue.enqueue("send_reminder", {"user_id": 123}, delay_seconds=3600)

# With retry configuration
job = queue.enqueue("process_payment", {"order_id": 456}, max_attempts=3)
```

### Processing Jobs

```python
# Process one job
job = queue.process_next()  # Returns processed job or None

# Process all available jobs
count = queue.process_all()  # Returns number processed
```

### Job Status

```python
# Access job properties
print(job.id)       # "job-1"
print(job.name)     # "send_email"
print(job.status)   # "pending", "processing", "completed", "failed"
print(job.result)   # Return value from handler
print(job.error)    # Error message if failed
print(job.attempts) # Number of attempts

# Get job by ID
job = queue.get_job("job-1")
```

### Accessing Job Lists

```python
# Pending jobs
pending = queue.jobs

# Completed jobs
completed = queue.completed_jobs

# Failed jobs (exhausted retries)
failed = queue.failed_jobs

# Clear all
queue.clear()
```

### Testing Example

```python
import pytest
from svc_infra.testing import MockJobQueue

@pytest.fixture
def job_queue():
    queue = MockJobQueue()

    @queue.handler("process_order")
    def handle_order(payload):
        return {"processed": True, "order_id": payload["order_id"]}

    return queue

def test_order_processing(job_queue):
    # Enqueue a job
    job = job_queue.enqueue("process_order", {"order_id": 123})
    assert job.status == "pending"

    # Process the job
    job_queue.process_all()

    # Verify completion
    assert job.status == "completed"
    assert job.result["processed"] is True
    assert job.result["order_id"] == 123

def test_job_retry_on_failure(job_queue):
    attempts = []

    @job_queue.handler("flaky_job")
    def flaky_handler(payload):
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("Temporary failure")
        return {"success": True}

    job = job_queue.enqueue("flaky_job", {}, max_attempts=5)

    # Process until success
    while job.status == "pending":
        job_queue.process_next()

    assert job.status == "completed"
    assert len(attempts) == 3
```

---

## Test Fixture Factories

### User Fixtures

```python
from svc_infra.testing import (
    create_test_user_data,
    create_test_user,
    UserFixtureData,
)

# Create user data (no database)
user_data = create_test_user_data()
print(user_data.id)       # UUID
print(user_data.email)    # "user+abc123@example.com"
print(user_data.is_active)  # True

# With overrides
admin_data = create_test_user_data(
    is_superuser=True,
    full_name="Admin User",
)

# Create in database (async)
async def test_create_user(async_session, User):
    user = await create_test_user(
        async_session,
        User,
        is_superuser=True,
    )
    assert user.is_superuser is True
```

### Tenant Fixtures

```python
from svc_infra.testing import (
    create_test_tenant_data,
    create_test_tenant,
    TenantFixtureData,
)

# Create tenant data
tenant_data = create_test_tenant_data()
print(tenant_data.id)     # UUID
print(tenant_data.name)   # "Test Tenant abc123"
print(tenant_data.slug)   # "test-tenant-abc123"

# With overrides
tenant_data = create_test_tenant_data(name="Acme Corp")
print(tenant_data.slug)   # "acme-corp" (auto-generated)

# Create in database (async)
async def test_create_tenant(async_session, Tenant):
    tenant = await create_test_tenant(
        async_session,
        Tenant,
        name="Test Company",
    )
    assert tenant.slug == "test-company"
```

### Utility Functions

```python
from svc_infra.testing import generate_uuid, generate_email

# Generate unique identifiers
user_id = generate_uuid()  # "550e8400-e29b-41d4-a716-446655440000"

# Generate unique email
email = generate_email()           # "test+abc12345@example.com"
email = generate_email("admin")    # "admin+abc12345@example.com"
```

---

## Pytest Integration

### Using Built-in Fixtures

```python
# conftest.py
import pytest
from svc_infra.testing import pytest_fixtures

fixtures = pytest_fixtures()

@pytest.fixture
def mock_cache():
    return fixtures["mock_cache"]()

@pytest.fixture
def mock_job_queue():
    return fixtures["mock_job_queue"]()

@pytest.fixture
def sync_job_queue():
    """Job queue that executes jobs immediately."""
    return fixtures["sync_job_queue"]()
```

### Manual Fixture Setup

```python
# conftest.py
import pytest
from svc_infra.testing import MockCache, MockJobQueue

@pytest.fixture
def cache():
    """Fresh mock cache for each test."""
    return MockCache(prefix="test")

@pytest.fixture
def job_queue():
    """Fresh mock job queue for each test."""
    queue = MockJobQueue()

    # Register common handlers
    @queue.handler("send_email")
    def handle_email(payload):
        return {"sent": True}

    return queue

@pytest.fixture
def sync_queue():
    """Job queue that executes immediately (for simple tests)."""
    return MockJobQueue(sync_mode=True)
```

### Async Test Example

```python
import pytest
from svc_infra.testing import MockCache, create_test_user

@pytest.fixture
async def user_with_cache(async_session, User, cache):
    """Create a test user and cache their data."""
    user = await create_test_user(async_session, User)
    cache.set(f"user:{user.id}", {"id": user.id, "email": user.email})
    return user

@pytest.mark.asyncio
async def test_cached_user_lookup(cache, user_with_cache):
    user = user_with_cache

    # Lookup from cache
    cached = cache.get(f"user:{user.id}")
    assert cached["email"] == user.email
```

---

## Integration Test Patterns

### Service Layer Testing

```python
from svc_infra.testing import MockCache, MockJobQueue

class TestUserService:
    @pytest.fixture
    def user_service(self, mock_cache, mock_job_queue):
        return UserService(cache=mock_cache, job_queue=mock_job_queue)

    async def test_create_user_sends_welcome_email(self, user_service, mock_job_queue):
        # Register email handler
        emails_sent = []

        @mock_job_queue.handler("send_welcome_email")
        def capture_email(payload):
            emails_sent.append(payload)

        # Create user
        user = await user_service.create_user(email="new@example.com")

        # Process jobs
        mock_job_queue.process_all()

        # Verify email was queued
        assert len(emails_sent) == 1
        assert emails_sent[0]["to"] == "new@example.com"

    async def test_get_user_uses_cache(self, user_service, mock_cache):
        # Pre-populate cache
        mock_cache.set("user:123", {"id": 123, "email": "cached@example.com"})

        # Get user (should hit cache)
        user = await user_service.get_user(123)

        assert user["email"] == "cached@example.com"
```

### Endpoint Testing

```python
from fastapi.testclient import TestClient
from svc_infra.testing import MockCache, MockJobQueue

@pytest.fixture
def test_client(mock_cache, mock_job_queue):
    app.dependency_overrides[get_cache] = lambda: mock_cache
    app.dependency_overrides[get_job_queue] = lambda: mock_job_queue

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()

def test_create_order(test_client, mock_job_queue):
    response = test_client.post("/orders", json={"item": "widget", "qty": 5})
    assert response.status_code == 201

    # Verify background job was queued
    assert len(mock_job_queue.jobs) == 1
    assert mock_job_queue.jobs[0].name == "process_order"
```

---

## API Reference

### MockCache

| Method | Description |
|--------|-------------|
| `get(key)` | Get cached value or None |
| `set(key, value, ttl=None, tags=None)` | Set value with optional TTL and tags |
| `delete(key)` | Delete single key |
| `delete_pattern(pattern)` | Delete keys matching glob pattern |
| `delete_by_tag(tag)` | Delete all keys with given tag |
| `exists(key)` | Check if key exists |
| `keys(pattern="*")` | Get keys matching pattern |
| `size()` | Get number of cached items |
| `clear()` | Clear all cached items |

### MockJobQueue

| Method | Description |
|--------|-------------|
| `handler(name)` | Decorator to register job handler |
| `register_handler(name, func)` | Register handler function |
| `enqueue(name, payload, ...)` | Enqueue a job |
| `process_next()` | Process next available job |
| `process_all()` | Process all available jobs |
| `get_job(job_id)` | Get job by ID |
| `clear()` | Clear all jobs |
| `jobs` | Property: pending jobs list |
| `completed_jobs` | Property: completed jobs list |
| `failed_jobs` | Property: failed jobs list |

### Fixture Factories

| Function | Description |
|----------|-------------|
| `create_test_user_data(**overrides)` | Create UserFixtureData instance |
| `create_test_tenant_data(**overrides)` | Create TenantFixtureData instance |
| `create_test_user(session, model, ...)` | Create user in database |
| `create_test_tenant(session, model, ...)` | Create tenant in database |
| `generate_uuid()` | Generate random UUID string |
| `generate_email(prefix="test")` | Generate unique email address |
| `pytest_fixtures()` | Get dict of pytest fixture functions |
