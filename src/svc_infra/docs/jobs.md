# Background Jobs & Scheduling

This module provides a lightweight JobQueue abstraction with a Redis backend for production and in-memory implementations for local/tests. A simple interval scheduler and CLI runner are included.

> ℹ️ Job-related environment variables are documented in [Environment Reference](environment.md).

## Quickstart

- Initialize in app code:

```python
from svc_infra.jobs.easy import easy_jobs
queue, scheduler = easy_jobs()  # uses JOBS_DRIVER=memory|redis
```

- Enqueue a job:

```python
job = queue.enqueue("send_email", {"to": "user@example.com"})
```

- Process one job (async):

```python
from svc_infra.jobs.worker import process_one
await process_one(queue, handler)
```

- Run the CLI runner:

```bash
svc-infra jobs run
```

## Redis Backend

Set environment variables:
- JOBS_DRIVER=redis
- REDIS_URL=redis://localhost:6379/0

Features:
- Visibility timeout during processing
- Exponential backoff on failures (base backoff_seconds * attempts)
- DLQ after max_attempts

## Scheduler

An interval-based scheduler runs async callables. You can define tasks via environment JSON:

- JOBS_SCHEDULE_JSON:

```json
[
  {"name": "ping", "interval_seconds": 60, "target": "myapp.tasks:ping"}
]
```

The `target` must be an import path of the form `module:function`. Sync functions are wrapped.

## Testing

- In-memory queue and scheduler enable fast, deterministic tests.
- Redis tests use `fakeredis` and cover enqueue/reserve/ack/fail and DLQ path.

## Next

- Add metrics, Redis Lua for atomic multi-ops, SQL-backed queue, distributed scheduler.
