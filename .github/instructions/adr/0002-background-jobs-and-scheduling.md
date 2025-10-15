# ADR 0002: Background Jobs & Scheduling

Date: 2025-10-15

Status: Accepted

## Context
We need production-grade background job processing and simple scheduling with a one-call setup. The library already includes in-memory queue/scheduler for tests/local. We need a production backend and a minimal runner.

## Decision
- JobQueue protocol defines enqueue/reserve/ack/fail with retry and exponential backoff (base seconds * attempts). Jobs have: id, name, payload, available_at, attempts, max_attempts, backoff_seconds, last_error.
- Backends:
  - InMemoryJobQueue for tests/local.
  - RedisJobQueue for production using Redis primitives with visibility timeout and atomic operations.
- Scheduler:
  - InMemoryScheduler providing interval-based scheduling via next_run_at. Cron parsing is out of scope initially; a simple YAML loader can be added later.
- Runner:
  - A CLI loop `svc-infra jobs run` will tick the scheduler and process jobs in a loop with small sleep/backoff.
- Configuration:
  - One-call `easy_jobs()` returns (queue, scheduler). Picks backend via `JOBS_DRIVER` env (memory|redis). Redis URL via `REDIS_URL`.

## Alternatives Considered
- Using RQ/Huey/Celery: heavier dependency and less control over API ergonomic goals; we prefer thin primitives aligned with svc-infra patterns.
- SQL-backed queue first: we will consider later; Redis is sufficient for v1.

## Consequences
- Enables outbox/webhook processors on a reliable queue.
- Minimal cognitive load: consistent APIs, ENV-driven.
- Future work: SQL queue, cron YAML loader, metrics, concurrency controls.

## Redis Data Model (initial)
- List `jobs:ready` holds ready job IDs; a ZSET `jobs:delayed` with score=available_at keeps delayed jobs; a HASH per job `job:{id}` stores fields.
- Reserve uses RPOPLPUSH from `jobs:ready` to `jobs:processing` or BRPOPLPUSH with timeout; sets `visible_at` on job as now+vt and increments `attempts`.
- Ack removes job from `jobs:processing` and deletes `job:{id}`.
- Fail increments attempts and computes next available_at = now + backoff_seconds * attempts; moves job to delayed ZSET.
- A housekeeping step periodically moves due jobs from delayed ZSET to ready list. Reserve also checks ZSET for due jobs opportunistically.

## Testing Strategy
- Unit tests cover enqueue/reserve/ack/fail, visibility timeout behavior, and DLQ after max_attempts.
- Runner tests cover one iteration loop processing.
