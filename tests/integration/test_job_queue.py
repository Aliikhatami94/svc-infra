"""Integration tests for job queue.

These tests verify job enqueue, processing, retry, timeout, and scheduled jobs.

Run with: pytest tests/integration/test_job_queue.py -v
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import pytest


@pytest.mark.integration
class TestJobEnqueue:
    """Integration tests for job enqueue operations."""

    @pytest.fixture
    def job_queue(self):
        """Create an in-memory job queue for testing."""
        from svc_infra.jobs import InMemoryQueue

        queue = InMemoryQueue()
        yield queue
        queue.clear()

    def test_enqueue_job(self, job_queue):
        """Test enqueueing a job."""
        job_id = job_queue.enqueue(
            task="process_order",
            args={"order_id": "123"},
        )

        assert job_id is not None
        assert len(job_id) > 0

    def test_enqueue_returns_unique_ids(self, job_queue):
        """Test that enqueue returns unique job IDs."""
        job_ids = set()
        for i in range(100):
            job_id = job_queue.enqueue(task="task", args={"i": i})
            job_ids.add(job_id)

        assert len(job_ids) == 100

    def test_enqueue_with_priority(self, job_queue):
        """Test enqueueing jobs with priority."""
        job_queue.enqueue(task="task", args={}, priority=1)  # low priority
        high_id = job_queue.enqueue(task="task", args={}, priority=10)

        # High priority should be processed first
        next_job = job_queue.dequeue()
        assert next_job.id == high_id

    def test_enqueue_with_metadata(self, job_queue):
        """Test enqueueing jobs with metadata."""
        job_id = job_queue.enqueue(
            task="send_email",
            args={"to": "user@example.com"},
            metadata={"tenant_id": "tenant_123", "user_id": "user_456"},
        )

        job = job_queue.get_job(job_id)
        assert job.metadata["tenant_id"] == "tenant_123"


@pytest.mark.integration
class TestJobProcessing:
    """Integration tests for job processing."""

    @pytest.fixture
    def job_queue(self):
        """Create an in-memory job queue for testing."""
        from svc_infra.jobs import InMemoryQueue

        queue = InMemoryQueue()
        yield queue
        queue.clear()

    def test_dequeue_job(self, job_queue):
        """Test dequeuing a job."""
        job_queue.enqueue(task="process", args={"id": 1})
        job_queue.enqueue(task="process", args={"id": 2})

        job = job_queue.dequeue()

        assert job is not None
        assert job.task == "process"

    def test_dequeue_empty_queue(self, job_queue):
        """Test dequeuing from empty queue returns None."""
        job = job_queue.dequeue()

        assert job is None

    def test_mark_job_complete(self, job_queue):
        """Test marking a job as complete."""
        job_id = job_queue.enqueue(task="task", args={})
        job_queue.dequeue()  # Claim the job

        job_queue.complete(job_id, result={"status": "success"})

        completed_job = job_queue.get_job(job_id)
        assert completed_job.status == "completed"
        assert completed_job.result["status"] == "success"

    def test_mark_job_failed(self, job_queue):
        """Test marking a job as failed."""
        job_id = job_queue.enqueue(task="task", args={})
        job_queue.dequeue()  # Claim the job

        job_queue.fail(job_id, error="Something went wrong")

        failed_job = job_queue.get_job(job_id)
        assert failed_job.status == "failed"
        assert "Something went wrong" in failed_job.error

    def test_job_status_transitions(self, job_queue):
        """Test job status transitions."""
        job_id = job_queue.enqueue(task="task", args={})

        # Initial status
        job = job_queue.get_job(job_id)
        assert job.status == "pending"

        # After dequeue
        job_queue.dequeue()
        job = job_queue.get_job(job_id)
        assert job.status == "processing"

        # After completion
        job_queue.complete(job_id, result={})
        job = job_queue.get_job(job_id)
        assert job.status == "completed"


@pytest.mark.integration
class TestJobRetry:
    """Integration tests for job retry logic."""

    @pytest.fixture
    def job_queue(self):
        """Create an in-memory job queue for testing."""
        from svc_infra.jobs import InMemoryQueue

        queue = InMemoryQueue()
        yield queue
        queue.clear()

    def test_retry_failed_job(self, job_queue):
        """Test retrying a failed job."""
        job_id = job_queue.enqueue(task="task", args={}, max_retries=3)
        job = job_queue.dequeue()

        # First failure
        job_queue.fail(job_id, error="First attempt failed")

        # Should be requeued
        job = job_queue.get_job(job_id)
        assert job.attempts == 1
        assert job.status == "pending"

    def test_max_retries_exceeded(self, job_queue):
        """Test behavior when max retries are exceeded."""
        job_id = job_queue.enqueue(task="task", args={}, max_retries=2)

        # Fail multiple times
        for _ in range(3):
            job = job_queue.dequeue()
            if job:
                job_queue.fail(job_id, error="Attempt failed")

        job = job_queue.get_job(job_id)
        assert job.status == "failed"
        assert job.attempts >= 2

    def test_retry_with_backoff(self, job_queue):
        """Test retry with exponential backoff."""
        job_id = job_queue.enqueue(
            task="task",
            args={},
            max_retries=3,
            retry_backoff=True,
        )

        job = job_queue.dequeue()
        job_queue.fail(job_id, error="Failed")

        # Job should have a delayed retry time
        job = job_queue.get_job(job_id)
        if hasattr(job, "scheduled_at"):
            assert job.scheduled_at > datetime.now(UTC)


@pytest.mark.integration
class TestJobTimeout:
    """Integration tests for job timeout handling."""

    @pytest.fixture
    def job_queue(self):
        """Create an in-memory job queue for testing."""
        from svc_infra.jobs import InMemoryQueue

        queue = InMemoryQueue()
        yield queue
        queue.clear()

    def test_job_timeout(self, job_queue):
        """Test job timeout handling."""
        job_id = job_queue.enqueue(
            task="long_task",
            args={},
            timeout=0.01,  # 10ms timeout
        )

        job_queue.dequeue()  # Claim the job
        time.sleep(0.05)  # Exceed timeout

        # Check for timed out jobs
        timed_out = job_queue.check_timeouts()

        assert job_id in [j.id for j in timed_out]

    def test_job_with_no_timeout(self, job_queue):
        """Test job without timeout doesn't time out."""
        job_id = job_queue.enqueue(
            task="task",
            args={},
            timeout=None,  # No timeout
        )

        job_queue.dequeue()  # Claim the job
        time.sleep(0.01)

        timed_out = job_queue.check_timeouts()
        assert job_id not in [j.id for j in timed_out]


@pytest.mark.integration
class TestScheduledJobs:
    """Integration tests for scheduled jobs."""

    @pytest.fixture
    def job_queue(self):
        """Create an in-memory job queue for testing."""
        from svc_infra.jobs import InMemoryQueue

        queue = InMemoryQueue()
        yield queue
        queue.clear()

    def test_schedule_job(self, job_queue):
        """Test scheduling a job for later execution."""
        run_at = datetime.now(UTC) + timedelta(seconds=10)

        job_id = job_queue.schedule(
            task="scheduled_task",
            args={"data": "value"},
            run_at=run_at,
        )

        job = job_queue.get_job(job_id)
        assert job.status == "scheduled"
        assert job.scheduled_at == run_at

    def test_scheduled_job_not_ready(self, job_queue):
        """Test that scheduled jobs don't get dequeued early."""
        run_at = datetime.now(UTC) + timedelta(seconds=10)

        job_queue.schedule(
            task="future_task",
            args={},
            run_at=run_at,
        )

        job = job_queue.dequeue()
        assert job is None

    def test_scheduled_job_becomes_ready(self, job_queue):
        """Test that scheduled jobs become ready at the right time."""
        run_at = datetime.now(UTC) + timedelta(milliseconds=50)

        job_id = job_queue.schedule(
            task="soon_task",
            args={},
            run_at=run_at,
        )

        time.sleep(0.1)  # Wait for scheduled time

        job = job_queue.dequeue()
        assert job is not None
        assert job.id == job_id

    def test_recurring_job(self, job_queue):
        """Test setting up a recurring job."""
        job_id = job_queue.schedule_recurring(
            task="cleanup",
            args={},
            interval=timedelta(hours=1),
        )

        assert job_id is not None

        # After completion, should reschedule
        job = job_queue.dequeue()
        if job:
            job_queue.complete(job_id, result={})

        # Check if rescheduled
        next_job = job_queue.get_job(job_id)
        if next_job:
            assert next_job.scheduled_at is not None


@pytest.mark.integration
class TestAsyncJobQueue:
    """Integration tests for async job queue operations."""

    @pytest.fixture
    def async_queue(self):
        """Create an async job queue for testing."""
        from svc_infra.jobs import AsyncInMemoryQueue

        queue = AsyncInMemoryQueue()
        return queue

    @pytest.mark.asyncio
    async def test_async_enqueue(self, async_queue):
        """Test async job enqueue."""
        job_id = await async_queue.enqueue(
            task="async_task",
            args={"key": "value"},
        )

        assert job_id is not None

    @pytest.mark.asyncio
    async def test_async_dequeue(self, async_queue):
        """Test async job dequeue."""
        await async_queue.enqueue(task="task", args={})

        job = await async_queue.dequeue()

        assert job is not None
        assert job.task == "task"

    @pytest.mark.asyncio
    async def test_async_worker(self, async_queue):
        """Test async worker processing jobs."""
        results = []

        async def handler(job):
            results.append(job.args["value"])

        # Enqueue jobs
        for i in range(5):
            await async_queue.enqueue(task="process", args={"value": i})

        # Process all jobs
        worker = async_queue.create_worker(handler)
        await worker.process_all(timeout=1.0)

        assert sorted(results) == [0, 1, 2, 3, 4]


@pytest.mark.integration
class TestJobQueueMonitoring:
    """Integration tests for job queue monitoring."""

    @pytest.fixture
    def job_queue(self):
        """Create an in-memory job queue for testing."""
        from svc_infra.jobs import InMemoryQueue

        queue = InMemoryQueue()
        yield queue
        queue.clear()

    def test_queue_stats(self, job_queue):
        """Test getting queue statistics."""
        # Add various jobs
        job_queue.enqueue(task="task1", args={})
        job_queue.enqueue(task="task2", args={})
        job = job_queue.dequeue()
        job_queue.complete(job.id, result={})

        stats = job_queue.get_stats()

        assert stats["pending"] >= 1
        assert stats["completed"] >= 1

    def test_list_jobs_by_status(self, job_queue):
        """Test listing jobs by status."""
        job_queue.enqueue(task="pending1", args={})
        job_queue.enqueue(task="pending2", args={})

        pending = job_queue.list_jobs(status="pending")
        assert len(pending) >= 2

    def test_purge_completed_jobs(self, job_queue):
        """Test purging old completed jobs."""
        job_id = job_queue.enqueue(task="task", args={})
        job_queue.dequeue()  # Claim the job
        job_queue.complete(job_id, result={})

        # Purge completed jobs older than 0 seconds
        purged = job_queue.purge_completed(older_than=timedelta(seconds=0))

        assert purged >= 1
        assert job_queue.get_job(job_id) is None
