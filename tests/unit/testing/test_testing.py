"""Unit tests for svc_infra.testing module."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from svc_infra.testing import (
    CacheEntry,
    MockCache,
    MockJob,
    MockJobQueue,
    TenantFixtureData,
    UserFixtureData,
    create_test_tenant,
    create_test_tenant_data,
    create_test_user,
    create_test_user_data,
    generate_email,
    generate_uuid,
    pytest_fixtures,
)

# =============================================================================
# CacheEntry Tests
# =============================================================================


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_entry_without_expiration(self):
        """Entry without expiration never expires."""
        entry = CacheEntry(value="test", expires_at=None)
        assert not entry.is_expired()

    def test_entry_not_yet_expired(self):
        """Entry with future expiration is not expired."""
        entry = CacheEntry(value="test", expires_at=time.time() + 100)
        assert not entry.is_expired()

    def test_entry_expired(self):
        """Entry with past expiration is expired."""
        entry = CacheEntry(value="test", expires_at=time.time() - 1)
        assert entry.is_expired()


# =============================================================================
# MockCache Tests
# =============================================================================


class TestMockCache:
    """Tests for MockCache class."""

    def test_init_default_prefix(self):
        """Cache has default prefix."""
        cache = MockCache()
        assert cache.prefix == "test"

    def test_init_custom_prefix(self):
        """Cache accepts custom prefix."""
        cache = MockCache(prefix="myapp")
        assert cache.prefix == "myapp"

    def test_set_and_get(self):
        """Basic set/get works."""
        cache = MockCache()
        cache.set("key1", {"data": "value"})
        assert cache.get("key1") == {"data": "value"}

    def test_get_missing_key(self):
        """Getting missing key returns None."""
        cache = MockCache()
        assert cache.get("nonexistent") is None

    def test_set_with_ttl(self):
        """TTL is respected."""
        cache = MockCache()
        cache.set("key1", "value", ttl=1)
        assert cache.get("key1") == "value"
        # Simulate expiration
        cache._store["test:key1"].expires_at = time.time() - 1
        assert cache.get("key1") is None

    def test_delete_existing_key(self):
        """Deleting existing key returns True."""
        cache = MockCache()
        cache.set("key1", "value")
        assert cache.delete("key1") is True
        assert cache.get("key1") is None

    def test_delete_missing_key(self):
        """Deleting missing key returns False."""
        cache = MockCache()
        assert cache.delete("nonexistent") is False

    def test_exists_true(self):
        """Exists returns True for existing key."""
        cache = MockCache()
        cache.set("key1", "value")
        assert cache.exists("key1") is True

    def test_exists_false(self):
        """Exists returns False for missing key."""
        cache = MockCache()
        assert cache.exists("nonexistent") is False

    def test_exists_expired(self):
        """Exists returns False for expired key."""
        cache = MockCache()
        cache.set("key1", "value", ttl=1)
        cache._store["test:key1"].expires_at = time.time() - 1
        assert cache.exists("key1") is False

    def test_clear(self):
        """Clear removes all entries."""
        cache = MockCache()
        cache.set("key1", "v1")
        cache.set("key2", "v2")
        cache.clear()
        assert cache.size() == 0

    def test_keys_all(self):
        """Keys returns all keys."""
        cache = MockCache()
        cache.set("user:1", "v1")
        cache.set("user:2", "v2")
        cache.set("other", "v3")
        keys = cache.keys()
        assert sorted(keys) == ["other", "user:1", "user:2"]

    def test_keys_with_pattern(self):
        """Keys supports pattern matching."""
        cache = MockCache()
        cache.set("user:1", "v1")
        cache.set("user:2", "v2")
        cache.set("order:1", "v3")
        keys = cache.keys("user:*")
        assert sorted(keys) == ["user:1", "user:2"]

    def test_delete_pattern(self):
        """Delete pattern removes matching keys."""
        cache = MockCache()
        cache.set("user:1", "v1")
        cache.set("user:2", "v2")
        cache.set("order:1", "v3")
        count = cache.delete_pattern("user:*")
        assert count == 2
        assert cache.get("user:1") is None
        assert cache.get("user:2") is None
        assert cache.get("order:1") == "v3"

    def test_size_excludes_expired(self):
        """Size doesn't count expired entries."""
        cache = MockCache()
        cache.set("key1", "v1")
        cache.set("key2", "v2", ttl=1)
        cache._store["test:key2"].expires_at = time.time() - 1
        assert cache.size() == 1

    def test_tags_basic(self):
        """Tags can be used to group keys."""
        cache = MockCache()
        cache.set("user:1", "v1", tags=["users"])
        cache.set("user:2", "v2", tags=["users"])
        cache.set("order:1", "v3", tags=["orders"])
        count = cache.delete_by_tag("users")
        assert count == 2
        assert cache.get("user:1") is None
        assert cache.get("order:1") == "v3"


# =============================================================================
# MockJobQueue Tests
# =============================================================================


class TestMockJob:
    """Tests for MockJob dataclass."""

    def test_job_defaults(self):
        """Job has expected defaults."""
        job = MockJob(id="1", name="test", payload={})
        assert job.attempts == 0
        assert job.max_attempts == 5
        assert job.status == "pending"
        assert job.result is None
        assert job.error is None


class TestMockJobQueue:
    """Tests for MockJobQueue class."""

    def test_init_default_mode(self):
        """Queue defaults to async mode (sync_mode=False)."""
        queue = MockJobQueue()
        assert queue.sync_mode is False

    def test_enqueue_creates_job(self):
        """Enqueue creates a job with correct data."""
        queue = MockJobQueue()
        job = queue.enqueue("send_email", {"to": "test@example.com"})
        assert job.id == "job-1"
        assert job.name == "send_email"
        assert job.payload == {"to": "test@example.com"}
        assert job.status == "pending"

    def test_enqueue_increments_id(self):
        """Each job gets a unique ID."""
        queue = MockJobQueue()
        job1 = queue.enqueue("job1", {})
        job2 = queue.enqueue("job2", {})
        assert job1.id == "job-1"
        assert job2.id == "job-2"

    def test_enqueue_with_delay(self):
        """Delayed jobs are not immediately available."""
        queue = MockJobQueue()
        job = queue.enqueue("delayed", {}, delay_seconds=3600)
        assert job.available_at > datetime.now(timezone.utc)

    def test_handler_decorator(self):
        """Handler decorator registers function."""
        queue = MockJobQueue()

        @queue.handler("greet")
        def handle_greet(payload):
            return f"Hello, {payload['name']}!"

        assert "greet" in queue._handlers

    def test_register_handler(self):
        """register_handler adds handler."""
        queue = MockJobQueue()
        queue.register_handler("greet", lambda p: f"Hi {p['name']}")
        assert "greet" in queue._handlers

    def test_process_next_with_handler(self):
        """process_next executes handler and completes job."""
        queue = MockJobQueue()
        results = []

        @queue.handler("test")
        def handle(payload):
            results.append(payload["value"])
            return "done"

        queue.enqueue("test", {"value": 42})
        job = queue.process_next()

        assert job is not None
        assert job.status == "completed"
        assert job.result == "done"
        assert results == [42]

    def test_process_next_no_jobs(self):
        """process_next returns None when no jobs."""
        queue = MockJobQueue()
        assert queue.process_next() is None

    def test_process_next_no_handler(self):
        """process_next fails job if no handler registered."""
        queue = MockJobQueue()
        queue.enqueue("unknown", {})
        job = queue.process_next()
        assert job is not None
        assert job.status == "failed"
        assert "No handler registered" in job.error

    def test_process_next_handler_exception(self):
        """process_next handles exceptions."""
        queue = MockJobQueue()

        @queue.handler("failing")
        def handle(payload):
            raise ValueError("Test error")

        queue.enqueue("failing", {}, max_attempts=1)
        job = queue.process_next()
        assert job.status == "failed"
        assert "Test error" in job.error

    def test_process_all(self):
        """process_all processes multiple jobs."""
        queue = MockJobQueue()
        results = []

        @queue.handler("add")
        def handle(payload):
            results.append(payload["n"])

        queue.enqueue("add", {"n": 1})
        queue.enqueue("add", {"n": 2})
        queue.enqueue("add", {"n": 3})

        count = queue.process_all()
        assert count == 3
        assert results == [1, 2, 3]

    def test_sync_mode_executes_immediately(self):
        """sync_mode=True executes jobs on enqueue."""
        queue = MockJobQueue(sync_mode=True)
        results = []

        @queue.handler("instant")
        def handle(payload):
            results.append("done")

        queue.enqueue("instant", {})
        assert results == ["done"]

    def test_sync_mode_skips_delayed(self):
        """sync_mode doesn't execute delayed jobs immediately."""
        queue = MockJobQueue(sync_mode=True)
        results = []

        @queue.handler("delayed")
        def handle(payload):
            results.append("done")

        queue.enqueue("delayed", {}, delay_seconds=60)
        assert results == []

    def test_jobs_property(self):
        """jobs property returns pending jobs only."""
        queue = MockJobQueue()
        queue.handler("test")(lambda p: None)
        queue.enqueue("test", {"n": 1})
        queue.enqueue("test", {"n": 2})
        queue.process_next()
        assert len(queue.jobs) == 1

    def test_completed_jobs_property(self):
        """completed_jobs returns completed jobs."""
        queue = MockJobQueue()
        queue.handler("test")(lambda p: "result")
        queue.enqueue("test", {})
        queue.process_next()
        assert len(queue.completed_jobs) == 1
        assert queue.completed_jobs[0].result == "result"

    def test_failed_jobs_property(self):
        """failed_jobs returns failed jobs."""
        queue = MockJobQueue()
        queue.enqueue("unknown", {})
        queue.process_next()
        assert len(queue.failed_jobs) == 1

    def test_get_job(self):
        """get_job finds job by ID."""
        queue = MockJobQueue()
        job = queue.enqueue("test", {})
        found = queue.get_job(job.id)
        assert found is job

    def test_get_job_not_found(self):
        """get_job returns None for missing ID."""
        queue = MockJobQueue()
        assert queue.get_job("nonexistent") is None

    def test_clear(self):
        """clear removes all jobs."""
        queue = MockJobQueue()
        queue.handler("test")(lambda p: None)
        queue.enqueue("test", {})
        queue.process_all()
        queue.enqueue("test", {})
        queue.clear()
        assert queue.jobs == []
        assert queue.completed_jobs == []
        assert queue.failed_jobs == []


# =============================================================================
# Test Fixture Factory Tests
# =============================================================================


class TestGenerators:
    """Tests for utility generators."""

    def test_generate_uuid(self):
        """generate_uuid returns valid UUID string."""
        uuid1 = generate_uuid()
        uuid2 = generate_uuid()
        assert isinstance(uuid1, str)
        assert len(uuid1) == 36
        assert uuid1 != uuid2

    def test_generate_email_default(self):
        """generate_email uses default prefix."""
        email = generate_email()
        assert email.startswith("test+")
        assert email.endswith("@example.com")

    def test_generate_email_custom_prefix(self):
        """generate_email accepts custom prefix."""
        email = generate_email("admin")
        assert email.startswith("admin+")

    def test_generate_email_unique(self):
        """generate_email returns unique emails."""
        emails = {generate_email() for _ in range(100)}
        assert len(emails) == 100


class TestUserFixtureData:
    """Tests for UserFixtureData factory."""

    def test_defaults(self):
        """UserFixtureData has sensible defaults."""
        data = UserFixtureData()
        assert len(data.id) == 36  # UUID
        assert "@example.com" in data.email
        assert data.is_active is True
        assert data.is_verified is True
        assert data.is_superuser is False

    def test_create_test_user_data(self):
        """create_test_user_data creates data with overrides."""
        data = create_test_user_data(is_superuser=True, email="custom@test.com")
        assert data.is_superuser is True
        assert data.email == "custom@test.com"


class TestTenantFixtureData:
    """Tests for TenantFixtureData factory."""

    def test_defaults(self):
        """TenantFixtureData has sensible defaults."""
        data = TenantFixtureData()
        assert len(data.id) == 36
        assert "Test Tenant" in data.name
        assert data.is_active is True

    def test_auto_slug(self):
        """Slug is auto-generated from name."""
        data = TenantFixtureData(name="Acme Corp")
        assert data.slug == "acme-corp"

    def test_custom_slug(self):
        """Custom slug is preserved."""
        data = TenantFixtureData(name="Acme", slug="custom-slug")
        assert data.slug == "custom-slug"

    def test_create_test_tenant_data(self):
        """create_test_tenant_data creates data with overrides."""
        data = create_test_tenant_data(name="My Company")
        assert data.name == "My Company"
        assert data.slug == "my-company"


# =============================================================================
# Async Test Factories
# =============================================================================


class TestCreateTestUser:
    """Tests for create_test_user async function."""

    @pytest.mark.asyncio
    async def test_creates_user_model(self):
        """create_test_user creates and persists user model."""
        # Mock session
        session = AsyncMock()
        session.add = MagicMock()

        # Mock user model
        class MockUser:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        user = await create_test_user(session, MockUser, is_superuser=True)

        session.add.assert_called_once()
        session.commit.assert_called_once()
        session.refresh.assert_called_once()
        assert user.is_superuser is True

    @pytest.mark.asyncio
    async def test_sets_full_name_if_provided(self):
        """create_test_user sets full_name when provided."""
        session = AsyncMock()
        session.add = MagicMock()

        class MockUser:
            full_name = None

            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        user = await create_test_user(session, MockUser, full_name="Test User")
        assert user.full_name == "Test User"


class TestCreateTestTenant:
    """Tests for create_test_tenant async function."""

    @pytest.mark.asyncio
    async def test_creates_tenant_model(self):
        """create_test_tenant creates and persists tenant model."""
        session = AsyncMock()
        session.add = MagicMock()

        class MockTenant:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        tenant = await create_test_tenant(session, MockTenant, name="Test Co")

        session.add.assert_called_once()
        session.commit.assert_called_once()
        session.refresh.assert_called_once()
        assert tenant.name == "Test Co"
        assert tenant.slug == "test-co"


# =============================================================================
# Pytest Fixtures Tests
# =============================================================================


class TestPytestFixtures:
    """Tests for pytest_fixtures helper."""

    def test_returns_fixture_dict(self):
        """pytest_fixtures returns dictionary of fixtures."""
        fixtures = pytest_fixtures()
        assert "mock_cache" in fixtures
        assert "mock_job_queue" in fixtures
        assert "sync_job_queue" in fixtures

    def test_mock_cache_fixture(self):
        """mock_cache fixture creates MockCache."""
        fixtures = pytest_fixtures()
        cache = fixtures["mock_cache"]()
        assert isinstance(cache, MockCache)

    def test_mock_job_queue_fixture(self):
        """mock_job_queue fixture creates MockJobQueue."""
        fixtures = pytest_fixtures()
        queue = fixtures["mock_job_queue"]()
        assert isinstance(queue, MockJobQueue)
        assert queue.sync_mode is False

    def test_sync_job_queue_fixture(self):
        """sync_job_queue fixture creates sync MockJobQueue."""
        fixtures = pytest_fixtures()
        queue = fixtures["sync_job_queue"]()
        assert isinstance(queue, MockJobQueue)
        assert queue.sync_mode is True
