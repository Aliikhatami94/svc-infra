"""Testing utilities for svc-infra applications.

This module provides mock implementations and test fixtures for
testing applications built with svc-infra, without requiring
real Redis, PostgreSQL, or other external services.

Features:
- MockCache: In-memory cache backend for tests
- MockJobQueue: Synchronous job queue for tests
- Test fixture factories for users and tenants
- Async test client utilities

Example:
    >>> from svc_infra.testing import MockCache, MockJobQueue
    >>>
    >>> # Use mock cache in tests
    >>> cache = MockCache()
    >>> cache.set("key", "value", ttl=60)
    >>> assert cache.get("key") == "value"
    >>>
    >>> # Use mock job queue
    >>> queue = MockJobQueue()
    >>> queue.enqueue("send_email", {"to": "test@example.com"})
    >>> assert len(queue.jobs) == 1
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar

# Type variable for generic model creation
T = TypeVar("T")


# =============================================================================
# Mock Cache
# =============================================================================


@dataclass
class CacheEntry:
    """Internal representation of a cached value."""

    value: Any
    expires_at: float | None = None  # Unix timestamp

    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


class MockCache:
    """
    In-memory cache backend for testing.

    Provides a simple synchronous cache that mimics the behavior of
    Redis or other cache backends without external dependencies.

    Features:
    - TTL support with expiration
    - Key prefix namespacing
    - Pattern-based key deletion
    - Thread-safe for single-threaded tests

    Example:
        >>> cache = MockCache(prefix="test")
        >>> cache.set("user:123", {"name": "Alice"}, ttl=300)
        >>> cache.get("user:123")
        {'name': 'Alice'}
        >>> cache.delete("user:123")
        >>> cache.get("user:123") is None
        True
    """

    def __init__(self, prefix: str = "test"):
        """
        Initialize mock cache.

        Args:
            prefix: Key prefix for namespacing (default: "test")
        """
        self.prefix = prefix
        self._store: dict[str, CacheEntry] = {}
        self._tags: dict[str, set[str]] = {}  # tag -> set of keys

    def _prefixed_key(self, key: str) -> str:
        """Get the full key with prefix."""
        return f"{self.prefix}:{key}"

    def get(self, key: str) -> Any | None:
        """
        Get a value from the cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        full_key = self._prefixed_key(key)
        entry = self._store.get(full_key)
        if entry is None:
            return None
        if entry.is_expired():
            del self._store[full_key]
            return None
        return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """
        Set a value in the cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (None for no expiration)
            tags: Optional list of tags for grouped invalidation
        """
        full_key = self._prefixed_key(key)
        expires_at = time.time() + ttl if ttl else None
        self._store[full_key] = CacheEntry(value=value, expires_at=expires_at)

        # Track tags
        if tags:
            for tag in tags:
                if tag not in self._tags:
                    self._tags[tag] = set()
                self._tags[tag].add(full_key)

    def delete(self, key: str) -> bool:
        """
        Delete a key from the cache.

        Args:
            key: Cache key

        Returns:
            True if key existed, False otherwise
        """
        full_key = self._prefixed_key(key)
        if full_key in self._store:
            del self._store[full_key]
            return True
        return False

    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern.

        Args:
            pattern: Pattern with * as wildcard (e.g., "user:*")

        Returns:
            Number of keys deleted
        """
        import fnmatch

        full_pattern = self._prefixed_key(pattern)
        to_delete = [k for k in self._store if fnmatch.fnmatch(k, full_pattern)]
        for key in to_delete:
            del self._store[key]
        return len(to_delete)

    def delete_by_tag(self, tag: str) -> int:
        """
        Delete all keys associated with a tag.

        Args:
            tag: Tag name

        Returns:
            Number of keys deleted
        """
        keys = self._tags.pop(tag, set())
        count = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                count += 1
        return count

    def exists(self, key: str) -> bool:
        """
        Check if a key exists in the cache.

        Args:
            key: Cache key

        Returns:
            True if key exists and is not expired
        """
        return self.get(key) is not None

    def clear(self) -> None:
        """Clear all cached values."""
        self._store.clear()
        self._tags.clear()

    def keys(self, pattern: str = "*") -> list[str]:
        """
        Get all keys matching a pattern.

        Args:
            pattern: Pattern with * as wildcard

        Returns:
            List of matching keys (without prefix)
        """
        import fnmatch

        full_pattern = self._prefixed_key(pattern)
        prefix_len = len(self.prefix) + 1  # +1 for the colon
        return [
            k[prefix_len:]
            for k in self._store
            if fnmatch.fnmatch(k, full_pattern) and not self._store[k].is_expired()
        ]

    def size(self) -> int:
        """Get the number of cached items (excluding expired)."""
        # Clean up expired entries
        now = time.time()
        self._store = {
            k: v for k, v in self._store.items() if v.expires_at is None or v.expires_at > now
        }
        return len(self._store)


# =============================================================================
# Mock Job Queue
# =============================================================================


@dataclass
class MockJob:
    """Representation of a job in the mock queue."""

    id: str
    name: str
    payload: dict[str, Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    available_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    attempts: int = 0
    max_attempts: int = 5
    status: str = "pending"  # pending, processing, completed, failed
    result: Any | None = None
    error: str | None = None


class MockJobQueue:
    """
    Synchronous mock job queue for testing.

    Jobs can be processed immediately (sync_mode=True) or queued
    for manual processing. Useful for testing job handlers without
    Redis or async complexity.

    Example:
        >>> queue = MockJobQueue()
        >>>
        >>> # Register a handler
        >>> @queue.handler("send_email")
        ... def handle_email(payload):
        ...     print(f"Sending to {payload['to']}")
        ...
        >>> # Enqueue a job
        >>> job = queue.enqueue("send_email", {"to": "test@example.com"})
        >>>
        >>> # Process all pending jobs
        >>> queue.process_all()
        Sending to test@example.com
    """

    def __init__(self, sync_mode: bool = False):
        """
        Initialize mock job queue.

        Args:
            sync_mode: If True, execute jobs immediately on enqueue
        """
        self.sync_mode = sync_mode
        self._seq = 0
        self._jobs: list[MockJob] = []
        self._handlers: dict[str, Callable[[dict[str, Any]], Any]] = {}
        self._completed: list[MockJob] = []
        self._failed: list[MockJob] = []

    def _next_id(self) -> str:
        """Generate next job ID."""
        self._seq += 1
        return f"job-{self._seq}"

    def handler(self, name: str) -> Callable:
        """
        Decorator to register a job handler.

        Args:
            name: Job name to handle

        Returns:
            Decorator function
        """

        def decorator(func: Callable[[dict[str, Any]], Any]) -> Callable:
            self._handlers[name] = func
            return func

        return decorator

    def register_handler(self, name: str, handler: Callable[[dict[str, Any]], Any]) -> None:
        """
        Register a job handler function.

        Args:
            name: Job name to handle
            handler: Handler function that receives payload dict
        """
        self._handlers[name] = handler

    def enqueue(
        self,
        name: str,
        payload: dict[str, Any],
        *,
        delay_seconds: int = 0,
        max_attempts: int = 5,
    ) -> MockJob:
        """
        Enqueue a job.

        Args:
            name: Job name (must have a registered handler to process)
            payload: Job payload dictionary
            delay_seconds: Delay before job becomes available
            max_attempts: Maximum retry attempts

        Returns:
            The created MockJob
        """
        available_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
        job = MockJob(
            id=self._next_id(),
            name=name,
            payload=dict(payload),
            available_at=available_at,
            max_attempts=max_attempts,
        )
        self._jobs.append(job)

        if self.sync_mode and delay_seconds == 0:
            self._process_job(job)

        return job

    def _process_job(self, job: MockJob) -> bool:
        """
        Process a single job.

        Returns:
            True if job succeeded, False if failed
        """
        handler = self._handlers.get(job.name)
        if handler is None:
            job.status = "failed"
            job.error = f"No handler registered for job type: {job.name}"
            self._failed.append(job)
            return False

        job.attempts += 1
        job.status = "processing"

        try:
            result = handler(job.payload)
            job.status = "completed"
            job.result = result
            self._completed.append(job)
            return True
        except Exception as e:
            job.error = str(e)
            if job.attempts >= job.max_attempts:
                job.status = "failed"
                self._failed.append(job)
            else:
                job.status = "pending"
                # Exponential backoff
                delay = 60 * job.attempts
                job.available_at = datetime.now(UTC) + timedelta(seconds=delay)
            return False

    def process_next(self) -> MockJob | None:
        """
        Process the next available job.

        Returns:
            The processed job, or None if no jobs available
        """
        now = datetime.now(UTC)
        for job in self._jobs:
            if job.status == "pending" and job.available_at <= now:
                self._process_job(job)
                if job.status in ("completed", "failed"):
                    self._jobs.remove(job)
                return job
        return None

    def process_all(self) -> int:
        """
        Process all available jobs.

        Returns:
            Number of jobs processed
        """
        count = 0
        while self.process_next() is not None:
            count += 1
        return count

    @property
    def jobs(self) -> list[MockJob]:
        """Get all pending jobs."""
        return [j for j in self._jobs if j.status == "pending"]

    @property
    def completed_jobs(self) -> list[MockJob]:
        """Get all completed jobs."""
        return self._completed.copy()

    @property
    def failed_jobs(self) -> list[MockJob]:
        """Get all failed jobs."""
        return self._failed.copy()

    def clear(self) -> None:
        """Clear all jobs (pending, completed, and failed)."""
        self._jobs.clear()
        self._completed.clear()
        self._failed.clear()

    def get_job(self, job_id: str) -> MockJob | None:
        """
        Get a job by ID.

        Args:
            job_id: Job ID

        Returns:
            The job or None if not found
        """
        for job in self._jobs + self._completed + self._failed:
            if job.id == job_id:
                return job
        return None


# =============================================================================
# Test Fixture Factories
# =============================================================================


def generate_uuid() -> str:
    """Generate a random UUID string."""
    return str(uuid.uuid4())


def generate_email(prefix: str = "test") -> str:
    """Generate a unique test email address."""
    return f"{prefix}+{uuid.uuid4().hex[:8]}@example.com"


@dataclass
class UserFixtureData:
    """Data for creating a test user."""

    id: str = field(default_factory=generate_uuid)
    email: str = field(default_factory=lambda: generate_email("user"))
    hashed_password: str = "$2b$12$test.hashed.password.placeholder"
    is_active: bool = True
    is_verified: bool = True
    is_superuser: bool = False
    full_name: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class TenantFixtureData:
    """Data for creating a test tenant."""

    id: str = field(default_factory=generate_uuid)
    name: str = field(default_factory=lambda: f"Test Tenant {uuid.uuid4().hex[:6]}")
    slug: str | None = None
    is_active: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.slug is None:
            self.slug = self.name.lower().replace(" ", "-")


def create_test_user_data(**overrides: Any) -> UserFixtureData:
    """
    Create test user data with optional overrides.

    Args:
        **overrides: Fields to override (id, email, is_superuser, etc.)

    Returns:
        UserFixtureData instance

    Example:
        >>> user_data = create_test_user_data(is_superuser=True)
        >>> print(user_data.is_superuser)
        True
    """
    return UserFixtureData(**overrides)


def create_test_tenant_data(**overrides: Any) -> TenantFixtureData:
    """
    Create test tenant data with optional overrides.

    Args:
        **overrides: Fields to override (id, name, slug, etc.)

    Returns:
        TenantFixtureData instance

    Example:
        >>> tenant_data = create_test_tenant_data(name="Acme Corp")
        >>> print(tenant_data.slug)
        'acme-corp'
    """
    return TenantFixtureData(**overrides)


async def create_test_user(
    session: Any,
    user_model: Callable[..., T],
    **overrides: Any,
) -> T:
    """
    Create a test user in the database.

    Args:
        session: SQLAlchemy async session
        user_model: User model class (must accept id, email, hashed_password,
            is_active, is_verified, is_superuser as kwargs)
        **overrides: Field overrides

    Returns:
        Created user instance

    Example:
        >>> async with async_session() as session:
        ...     user = await create_test_user(session, User, is_superuser=True)
        ...     print(user.email)
    """
    data = create_test_user_data(**overrides)
    user = user_model(
        id=data.id,
        email=data.email,
        hashed_password=data.hashed_password,
        is_active=data.is_active,
        is_verified=data.is_verified,
        is_superuser=data.is_superuser,
        **data.extra,
    )
    if hasattr(user, "full_name") and data.full_name:
        user.full_name = data.full_name

    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def create_test_tenant(
    session: Any,
    tenant_model: Callable[..., T],
    **overrides: Any,
) -> T:
    """
    Create a test tenant in the database.

    Args:
        session: SQLAlchemy async session
        tenant_model: Tenant model class
        **overrides: Field overrides

    Returns:
        Created tenant instance

    Example:
        >>> async with async_session() as session:
        ...     tenant = await create_test_tenant(session, Tenant, name="Test Co")
        ...     print(tenant.slug)
    """
    data = create_test_tenant_data(**overrides)
    tenant = tenant_model(
        id=data.id,
        name=data.name,
        slug=data.slug,
        is_active=data.is_active,
        **data.extra,
    )
    session.add(tenant)
    await session.commit()
    await session.refresh(tenant)
    return tenant


# =============================================================================
# Pytest Fixtures (importable for conftest.py)
# =============================================================================


def pytest_fixtures() -> dict[str, Callable]:
    """
    Get pytest fixture functions for use in conftest.py.

    Returns:
        Dictionary of fixture name -> fixture function

    Example:
        In your conftest.py:
        >>> from svc_infra.testing import pytest_fixtures
        >>> import pytest
        >>>
        >>> fixtures = pytest_fixtures()
        >>> mock_cache = pytest.fixture(fixtures["mock_cache"])
        >>> mock_job_queue = pytest.fixture(fixtures["mock_job_queue"])
    """

    def mock_cache() -> MockCache:
        """Provide a fresh MockCache for each test."""
        return MockCache()

    def mock_job_queue() -> MockJobQueue:
        """Provide a fresh MockJobQueue for each test."""
        return MockJobQueue()

    def sync_job_queue() -> MockJobQueue:
        """Provide a MockJobQueue that executes jobs immediately."""
        return MockJobQueue(sync_mode=True)

    return {
        "mock_cache": mock_cache,
        "mock_job_queue": mock_job_queue,
        "sync_job_queue": sync_job_queue,
    }


__all__ = [
    # Mock implementations
    "MockCache",
    "MockJobQueue",
    "MockJob",
    "CacheEntry",
    # Test data factories
    "UserFixtureData",
    "TenantFixtureData",
    "create_test_user_data",
    "create_test_tenant_data",
    "create_test_user",
    "create_test_tenant",
    # Utilities
    "generate_uuid",
    "generate_email",
    "pytest_fixtures",
]
