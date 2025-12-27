# Background Jobs Guide

Lightweight job queue abstraction with Redis backend for production and in-memory for testing.

## Overview

svc-infra provides a flexible background job system:

- **Multiple Backends**: Redis for production, in-memory for development/testing
- **Delayed Jobs**: Schedule jobs to run after a delay
- **Retry Logic**: Exponential backoff with configurable max attempts
- **Dead Letter Queue**: Failed jobs are moved to DLQ after max retries
- **Visibility Timeout**: Prevents duplicate processing with automatic re-queuing
- **Interval Scheduler**: Simple scheduling for periodic tasks
- **Built-in Jobs**: Webhook delivery, outbox processing

## Quick Start

### Basic Setup

```python
from svc_infra.jobs.easy import easy_jobs

# Initialize queue and scheduler (uses JOBS_DRIVER env var)
queue, scheduler = easy_jobs()

# Enqueue a job
job = queue.enqueue("send_email", {"to": "user@example.com", "subject": "Hello"})
print(f"Enqueued job: {job.id}")
```

### Processing Jobs

```python
from svc_infra.jobs.worker import process_one
from svc_infra.jobs.queue import Job

async def my_handler(job: Job):
    if job.name == "send_email":
        await send_email(job.payload["to"], job.payload["subject"])
    elif job.name == "generate_report":
        await generate_report(job.payload["report_id"])

# Process one job
processed = await process_one(queue, my_handler)
```

### CLI Runner

```bash
# Run the job worker
svc-infra jobs run
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `JOBS_DRIVER` | `memory` | Backend driver (`memory` or `redis`) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `JOB_DEFAULT_TIMEOUT_SECONDS` | — | Per-job execution timeout |
| `JOBS_SCHEDULE_JSON` | — | JSON array of scheduled tasks |

### Backend Selection

```bash
# Development (in-memory)
JOBS_DRIVER=memory

# Production (Redis)
JOBS_DRIVER=redis
REDIS_URL=redis://redis.example.com:6379/0
```

### Programmatic Configuration

```python
from svc_infra.jobs.easy import easy_jobs

# Explicitly set driver
queue, scheduler = easy_jobs(driver="redis")

# Or use environment variable
# JOBS_DRIVER=redis
queue, scheduler = easy_jobs()
```

---

## Enqueueing Jobs

### Basic Enqueue

```python
from svc_infra.jobs.easy import easy_jobs

queue, _ = easy_jobs()

# Simple job
job = queue.enqueue("process_order", {"order_id": 123})

# With payload
job = queue.enqueue("send_notification", {
    "user_id": 456,
    "message": "Your order is ready",
    "channel": "email",
})
```

### Delayed Jobs

Schedule jobs to run after a delay:

```python
# Run after 5 minutes
job = queue.enqueue(
    "send_reminder",
    {"user_id": 123},
    delay_seconds=300,
)

# Run after 1 hour
job = queue.enqueue(
    "generate_daily_report",
    {"date": "2025-01-15"},
    delay_seconds=3600,
)
```

### Job Properties

```python
from svc_infra.jobs.queue import Job

# Jobs have these properties:
job = queue.enqueue("my_job", {"key": "value"})

print(job.id)              # Unique job ID
print(job.name)            # Job name/type
print(job.payload)         # Job data
print(job.available_at)    # When job becomes available
print(job.attempts)        # Number of processing attempts
print(job.max_attempts)    # Maximum retry attempts (default: 5)
print(job.backoff_seconds) # Base backoff for retries (default: 60)
print(job.last_error)      # Error from last failed attempt
```

---

## Job Handlers

### Handler Function

```python
from svc_infra.jobs.queue import Job

async def my_handler(job: Job) -> None:
    """Process a job based on its name."""
    if job.name == "send_email":
        await handle_send_email(job.payload)
    elif job.name == "generate_report":
        await handle_generate_report(job.payload)
    else:
        raise ValueError(f"Unknown job type: {job.name}")
```

### Handler Registry Pattern

```python
from svc_infra.jobs.queue import Job
from typing import Callable, Awaitable

# Registry of handlers
HANDLERS: dict[str, Callable[[dict], Awaitable[None]]] = {}

def register_handler(name: str):
    """Decorator to register a job handler."""
    def decorator(func: Callable[[dict], Awaitable[None]]):
        HANDLERS[name] = func
        return func
    return decorator

@register_handler("send_email")
async def handle_send_email(payload: dict):
    await email_service.send(
        to=payload["to"],
        subject=payload["subject"],
        body=payload["body"],
    )

@register_handler("process_payment")
async def handle_process_payment(payload: dict):
    await payment_service.process(payload["payment_id"])

async def dispatch_handler(job: Job) -> None:
    """Dispatch job to registered handler."""
    handler = HANDLERS.get(job.name)
    if not handler:
        raise ValueError(f"No handler for job: {job.name}")
    await handler(job.payload)
```

### Dependency Injection in Handlers

```python
from svc_infra.jobs.queue import Job
from functools import partial

class EmailService:
    async def send(self, to: str, subject: str, body: str):
        # Send email implementation
        pass

def make_handler(email_service: EmailService):
    """Create handler with injected dependencies."""
    async def handler(job: Job) -> None:
        if job.name == "send_email":
            await email_service.send(
                to=job.payload["to"],
                subject=job.payload["subject"],
                body=job.payload["body"],
            )
    return handler

# Create handler with dependencies
email_service = EmailService()
handler = make_handler(email_service)
```

---

## Worker Runner

### Basic Worker Loop

```python
from svc_infra.jobs.runner import WorkerRunner
from svc_infra.jobs.easy import easy_jobs

queue, _ = easy_jobs()

async def my_handler(job):
    print(f"Processing: {job.name}")
    # Handle job...

runner = WorkerRunner(queue, my_handler, poll_interval=0.5)

# Start the worker (runs indefinitely)
task = runner.start()

# Later, stop gracefully
await runner.stop(grace_seconds=10.0)
```

### Graceful Shutdown

```python
import asyncio
import signal
from svc_infra.jobs.runner import WorkerRunner

async def main():
    queue, _ = easy_jobs()
    runner = WorkerRunner(queue, my_handler)

    # Handle shutdown signals
    loop = asyncio.get_event_loop()

    def shutdown():
        asyncio.create_task(runner.stop(grace_seconds=30.0))

    loop.add_signal_handler(signal.SIGTERM, shutdown)
    loop.add_signal_handler(signal.SIGINT, shutdown)

    # Start worker
    await runner.start()

asyncio.run(main())
```

### Multiple Workers

```python
import asyncio
from svc_infra.jobs.runner import WorkerRunner

async def run_workers(num_workers: int = 4):
    queue, _ = easy_jobs()

    runners = [
        WorkerRunner(queue, my_handler, poll_interval=0.25)
        for _ in range(num_workers)
    ]

    # Start all workers
    tasks = [runner.start() for runner in runners]

    # Wait for all (they run indefinitely)
    await asyncio.gather(*tasks)
```

---

## Scheduling

### Interval-Based Scheduling

```python
from svc_infra.jobs.scheduler import InMemoryScheduler

scheduler = InMemoryScheduler(tick_interval=60.0)

# Add periodic tasks
async def cleanup_sessions():
    await db.delete_expired_sessions()

async def send_daily_digest():
    await email_service.send_digest()

scheduler.add_task("cleanup_sessions", 300, cleanup_sessions)  # Every 5 minutes
scheduler.add_task("daily_digest", 86400, send_daily_digest)   # Every 24 hours

# Run scheduler (blocks indefinitely)
await scheduler.run()
```

### Environment-Based Schedule

Configure tasks via JSON environment variable:

```bash
JOBS_SCHEDULE_JSON='[
  {"name": "cleanup", "interval_seconds": 300, "target": "myapp.tasks:cleanup"},
  {"name": "health_check", "interval_seconds": 60, "target": "myapp.tasks:health_ping"}
]'
```

Load and register:

```python
from svc_infra.jobs.loader import schedule_from_env
from svc_infra.jobs.scheduler import InMemoryScheduler

scheduler = InMemoryScheduler()
schedule_from_env(scheduler)  # Reads JOBS_SCHEDULE_JSON

await scheduler.run()
```

### Target Format

The `target` must be an import path in `module:function` format:

```python
# myapp/tasks.py
async def cleanup():
    """Called by scheduler."""
    await perform_cleanup()

def sync_task():
    """Sync functions are auto-wrapped as async."""
    perform_sync_work()
```

```bash
# Reference in JOBS_SCHEDULE_JSON
{"target": "myapp.tasks:cleanup"}
{"target": "myapp.tasks:sync_task"}
```

---

## Reliability

### Visibility Timeout

Redis queue uses visibility timeout to prevent duplicate processing:

```python
from redis import Redis
from svc_infra.jobs.redis_queue import RedisJobQueue

client = Redis.from_url("redis://localhost:6379/0")
queue = RedisJobQueue(
    client,
    prefix="jobs",
    visibility_timeout=60,  # Job re-queued if not ack'd in 60s
)
```

### Retry with Exponential Backoff

Failed jobs are automatically retried with backoff:

```python
# Job configuration (set during enqueue or via defaults)
job.max_attempts = 5        # Try up to 5 times
job.backoff_seconds = 60    # Base backoff

# Retry delays:
# Attempt 1: immediate
# Attempt 2: 60 seconds delay
# Attempt 3: 120 seconds delay (60 * 2)
# Attempt 4: 180 seconds delay (60 * 3)
# Attempt 5: 240 seconds delay (60 * 4)
# After attempt 5: moved to DLQ
```

### Dead Letter Queue

Jobs exceeding max attempts are moved to DLQ:

```python
# Redis keys used:
# {prefix}:dlq - List of failed job IDs

# Inspect DLQ (manual)
dlq_jobs = redis_client.lrange("jobs:dlq", 0, -1)
for job_id in dlq_jobs:
    job_data = redis_client.hgetall(f"jobs:job:{job_id}")
    print(f"Failed job: {job_id}, error: {job_data.get('last_error')}")
```

### Idempotency Patterns

Design handlers for safe retries:

```python
from svc_infra.db.inbox import InboxStore

async def handle_send_email(job: Job, inbox: InboxStore):
    # Create idempotency key from job
    key = f"email:{job.id}"

    # Check if already processed
    if inbox.is_marked(key):
        return  # Skip duplicate

    # Process the job
    await email_service.send(job.payload)

    # Mark as processed
    inbox.mark(key)
```

---

## Built-in Jobs

### Webhook Delivery

Deliver webhooks with retry and signing:

```python
from svc_infra.jobs.builtins.webhook_delivery import make_webhook_handler
from svc_infra.db.outbox import OutboxStore
from svc_infra.db.inbox import InboxStore

def get_webhook_url(topic: str) -> str:
    return webhook_config[topic]["url"]

def get_webhook_secret(topic: str) -> str:
    return webhook_config[topic]["secret"]

handler = make_webhook_handler(
    outbox=OutboxStore(session),
    inbox=InboxStore(session),
    get_webhook_url_for_topic=get_webhook_url,
    get_secret_for_topic=get_webhook_secret,
    header_name="X-Signature",
)

# Enqueue webhook delivery
queue.enqueue("webhook.user.created", {
    "outbox_id": 123,
    "topic": "user.created",
    "payload": {"user_id": 456, "email": "user@example.com"},
})
```

### Outbox Processing

Move outbox messages to job queue:

```python
from svc_infra.jobs.builtins.outbox_processor import make_outbox_tick
from svc_infra.db.outbox import OutboxStore

outbox = OutboxStore(session)
outbox_tick = make_outbox_tick(
    outbox=outbox,
    queue=queue,
    topics=["user.created", "order.completed"],
    job_name_prefix="outbox",
)

# Add to scheduler
scheduler.add_task("outbox_processor", 5, outbox_tick)  # Every 5 seconds
```

---

## Redis Queue Details

### Redis Keys

The Redis queue uses these keys (with configurable prefix):

| Key | Type | Description |
|-----|------|-------------|
| `{prefix}:ready` | LIST | Job IDs ready for processing |
| `{prefix}:processing` | LIST | Job IDs currently being processed |
| `{prefix}:processing_vt` | ZSET | Visibility timeout tracking |
| `{prefix}:delayed` | ZSET | Delayed jobs (score = available_at) |
| `{prefix}:seq` | STRING | Auto-incrementing job ID counter |
| `{prefix}:job:{id}` | HASH | Job data (name, payload, attempts, etc.) |
| `{prefix}:dlq` | LIST | Dead letter queue job IDs |

### Atomic Operations

Reserve uses Lua scripting for atomic pop-and-push:

```lua
-- Atomic reserve: pop from ready, push to processing
local job_id = redis.call('RPOPLPUSH', ready_key, processing_key)
if job_id then
    redis.call('ZADD', processing_vt_key, visible_at, job_id)
end
return job_id
```

### Visibility Timeout Requeue

Timed-out jobs are automatically re-queued:

```python
# Jobs in processing longer than visibility_timeout
# are moved back to ready queue on next reserve_next() call
```

---

## Worker Deployment

### CLI Usage

```bash
# Basic worker
svc-infra jobs run

# With environment configuration
JOBS_DRIVER=redis REDIS_URL=redis://localhost:6379/0 svc-infra jobs run
```

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -e .

# Run worker
CMD ["svc-infra", "jobs", "run"]
```

```yaml
# docker-compose.yml
services:
  api:
    build: .
    command: uvicorn main:app --host 0.0.0.0 --port 8000

  worker:
    build: .
    command: svc-infra jobs run
    environment:
      - JOBS_DRIVER=redis
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
```

### Kubernetes Deployment

```yaml
# worker-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: job-worker
spec:
  replicas: 3
  selector:
    matchLabels:
      app: job-worker
  template:
    metadata:
      labels:
        app: job-worker
    spec:
      containers:
        - name: worker
          image: myapp:latest
          command: ["svc-infra", "jobs", "run"]
          env:
            - name: JOBS_DRIVER
              value: "redis"
            - name: REDIS_URL
              valueFrom:
                secretKeyRef:
                  name: redis-secret
                  key: url
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
```

### Scaling Workers

```bash
# Scale horizontally in Kubernetes
kubectl scale deployment job-worker --replicas=5

# Or in docker-compose
docker-compose up --scale worker=5
```

---

## Monitoring

### Job Metrics

Track job processing metrics:

```python
from prometheus_client import Counter, Histogram, Gauge

jobs_processed = Counter(
    "jobs_processed_total",
    "Total jobs processed",
    ["name", "status"],
)

job_duration = Histogram(
    "job_duration_seconds",
    "Job processing duration",
    ["name"],
)

dlq_size = Gauge(
    "jobs_dlq_size",
    "Number of jobs in dead letter queue",
)

async def instrumented_handler(job: Job):
    with job_duration.labels(name=job.name).time():
        try:
            await actual_handler(job)
            jobs_processed.labels(name=job.name, status="success").inc()
        except Exception:
            jobs_processed.labels(name=job.name, status="failure").inc()
            raise
```

### DLQ Alerting

```yaml
# Prometheus alert rule
groups:
  - name: jobs
    rules:
      - alert: HighDLQSize
        expr: jobs_dlq_size > 100
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Dead letter queue has {{ $value }} jobs"
```

---

## Testing

### In-Memory Queue

```python
import pytest
from svc_infra.jobs.queue import InMemoryJobQueue

@pytest.fixture
def queue():
    return InMemoryJobQueue()

async def test_enqueue_and_process(queue):
    # Enqueue job
    job = queue.enqueue("test_job", {"key": "value"})
    assert job.id == "1"

    # Reserve job
    reserved = queue.reserve_next()
    assert reserved.id == job.id
    assert reserved.payload == {"key": "value"}

    # Acknowledge completion
    queue.ack(job.id)

    # No more jobs
    assert queue.reserve_next() is None
```

### Testing with fakeredis

```python
import pytest
from fakeredis import FakeRedis
from svc_infra.jobs.redis_queue import RedisJobQueue

@pytest.fixture
def redis_queue():
    client = FakeRedis()
    return RedisJobQueue(client, prefix="test")

async def test_delayed_job(redis_queue):
    # Enqueue with delay
    job = redis_queue.enqueue("delayed", {}, delay_seconds=60)

    # Not available immediately
    assert redis_queue.reserve_next() is None
```

### Testing Handlers

```python
import pytest
from svc_infra.jobs.queue import Job
from datetime import datetime, UTC

@pytest.fixture
def sample_job():
    return Job(
        id="1",
        name="send_email",
        payload={"to": "test@example.com"},
        available_at=datetime.now(UTC),
    )

async def test_email_handler(sample_job, mocker):
    mock_send = mocker.patch("myapp.email.send")

    await handle_send_email(sample_job)

    mock_send.assert_called_once_with("test@example.com")
```

---

## Production Recommendations

### Redis Configuration

```bash
# Production Redis
REDIS_URL=redis://user:password@redis.example.com:6379/0

# With TLS
REDIS_URL=rediss://redis.example.com:6379/0
```

### Worker Sizing

| Workload | Workers | Poll Interval |
|----------|---------|---------------|
| Low volume (< 100/min) | 1-2 | 1.0s |
| Medium volume (100-1000/min) | 3-5 | 0.5s |
| High volume (1000+/min) | 5-10 | 0.25s |

### Job Timeouts

```bash
# Set default timeout for all jobs
JOB_DEFAULT_TIMEOUT_SECONDS=300

# Per-job timeout in handler
import asyncio

async def handler_with_timeout(job: Job):
    try:
        await asyncio.wait_for(
            process_job(job),
            timeout=60.0,
        )
    except asyncio.TimeoutError:
        raise Exception("Job timed out")
```

### Graceful Shutdown

```python
# Kubernetes terminationGracePeriodSeconds should exceed
# your worker's grace_seconds
await runner.stop(grace_seconds=30.0)
```

---

## Troubleshooting

### Stuck Jobs

```
Jobs not being processed
```

**Solutions:**
1. Check worker is running: `svc-infra jobs run`
2. Verify `JOBS_DRIVER` matches your queue backend
3. Check Redis connection with `redis-cli ping`
4. Inspect queue sizes: `redis-cli llen jobs:ready`

### Memory Leaks

```
Worker memory growing over time
```

**Solutions:**
1. Add job timeout: `JOB_DEFAULT_TIMEOUT_SECONDS=300`
2. Check for unclosed resources in handlers
3. Use async context managers properly
4. Monitor with memory profiler

### Jobs Retrying Forever

```
Jobs keep failing and retrying
```

**Solutions:**
1. Check `max_attempts` configuration
2. Review DLQ for error patterns
3. Add better error logging in handlers
4. Implement circuit breaker for external services

### Lost Jobs

```
Jobs enqueued but never processed
```

**Solutions:**
1. Check visibility timeout is appropriate
2. Verify workers are acknowledging jobs
3. Check for exceptions before `queue.ack()`
4. Review Redis persistence settings

### Slow Processing

```
Job queue growing faster than processing
```

**Solutions:**
1. Scale worker replicas horizontally
2. Reduce `poll_interval` for faster pickup
3. Optimize handler performance
4. Consider job batching for high-volume tasks

---

## See Also

- [Cache Guide](cache.md) - Redis caching
- [Webhooks Guide](webhooks.md) - Webhook delivery
- [Environment Reference](environment.md) - All job environment variables
- [Observability Guide](observability.md) - Monitoring job workers
