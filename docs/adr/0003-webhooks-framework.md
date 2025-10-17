# ADR 0003: Webhooks Framework

Date: 2025-10-15

Status: Accepted

## Context
Services need a consistent way to publish domain events to external consumers via webhooks, verify inbound signatures, and handle retries with backoff. We already have an outbox pattern, a job queue, and a webhook delivery worker.

## Decision
- Event Schema: minimal fields {topic, payload, version, created_at}. Versioning included to evolve payloads.
- Signing: HMAC-SHA256 over canonical JSON payload; header `X-Signature` carries hex digest. Future: include timestamp and v1 signature header variant.
- Outbox → Job Queue: Producer writes events to Outbox; outbox tick enqueues delivery jobs; worker performs HTTP POST with signature.
- Subscriptions: In-memory subscription store maps topic → {url, secret}. Persistence deferred.
- Verification: Provide helper for verifying incoming webhook requests by recomputing the HMAC.
- Retry: Already handled by JobQueue backoff; DLQ after max attempts.

## Consequences
- Clear boundary: producers don't call HTTP directly; they publish to Outbox.
- Deterministic signing & verification across producer/consumer.
- Extensibility: timestamped signed headers, secret rotation, persisted subscriptions are future extensions.

## Testing
- Unit tests for verification helper and end-to-end publish→outbox→queue→delivery using in-memory components and a fake HTTP client.
