# Webhooks

svc-infra provides a complete webhook framework for delivering real-time event notifications
to external systems. The framework handles subscription management, payload signing,
reliable delivery via outbox pattern, and verification utilities for consumers.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Your Application                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────────┐   │
│  │   Domain     │───>│  WebhookSvc  │───>│     Outbox (database)    │   │
│  │   Event      │    │  .publish()  │    │   "webhook_delivery"     │   │
│  └──────────────┘    └──────────────┘    └──────────────────────────┘   │
│                                                       │                  │
│                                           ┌───────────┴───────────┐     │
│                                           │    Jobs Worker        │     │
│                                           │  webhook_handler      │     │
│                                           └───────────┬───────────┘     │
│                                                       │                  │
└───────────────────────────────────────────────────────│──────────────────┘
                                                        │
                                              HTTP POST + HMAC signature
                                                        │
                                                        ▼
                                            ┌────────────────────────┐
                                            │   Customer's Endpoint  │
                                            │   (webhook receiver)   │
                                            └────────────────────────┘
```

---

## Quick Start

### 1. Define Webhook Topics

```python
from enum import StrEnum

class WebhookTopic(StrEnum):
    ORDER_CREATED = "order.created"
    ORDER_COMPLETED = "order.completed"
    ORDER_CANCELLED = "order.cancelled"
    PAYMENT_RECEIVED = "payment.received"
    PAYMENT_FAILED = "payment.failed"
    SUBSCRIPTION_ACTIVATED = "subscription.activated"
    SUBSCRIPTION_CANCELLED = "subscription.cancelled"
```

### 2. Create Webhook Service

```python
from svc_infra.webhooks.service import WebhookService, InMemoryWebhookSubscriptions

# For development/testing
subscriptions = InMemoryWebhookSubscriptions()
webhook_service = WebhookService(subscriptions=subscriptions)

# For production (use database-backed subscriptions)
from myapp.webhooks import DatabaseWebhookSubscriptions
subscriptions = DatabaseWebhookSubscriptions(session_factory)
webhook_service = WebhookService(subscriptions=subscriptions)
```

### 3. Publish Events

```python
# When domain event occurs
await webhook_service.publish(
    topic="order.created",
    tenant_id="tenant_123",
    payload={"order_id": "ord_abc", "total": 99.99},
    outbox=outbox_store,  # From svc_infra.jobs.outbox
)
```

### 4. Wire Up Delivery Worker

```python
from svc_infra.jobs.builtins.webhook_delivery import make_webhook_handler
from svc_infra.jobs.worker import run_worker

handler = make_webhook_handler(
    outbox=outbox_store,
    inbox=inbox_store,
    get_webhook_url_for_topic=lambda t: get_subscription_url(t),
    get_secret_for_topic=lambda t: get_subscription_secret(t),
)

await run_worker(
    queue="webhook_delivery",
    handler=handler,
)
```

---

## Subscription Management

### WebhookSubscription Model

```python
from dataclasses import dataclass
from svc_infra.webhooks.service import WebhookSubscription

@dataclass
class WebhookSubscription:
    id: str                    # Unique subscription ID
    tenant_id: str             # Owning tenant
    topic: str                 # Event topic pattern
    url: str                   # Delivery endpoint
    encrypted_secret: str      # HMAC signing secret (encrypted at rest)
    enabled: bool = True       # Active/paused toggle
```

### In-Memory Subscriptions (Development)

```python
from svc_infra.webhooks.service import InMemoryWebhookSubscriptions

subscriptions = InMemoryWebhookSubscriptions()

# Add subscription
await subscriptions.add(WebhookSubscription(
    id="sub_1",
    tenant_id="tenant_123",
    topic="order.*",  # Wildcard support
    url="https://example.com/webhooks",
    encrypted_secret=encrypt(b"secret_key"),
))

# Query subscriptions
subs = await subscriptions.get_for_topic("tenant_123", "order.created")
```

### Database-Backed Subscriptions (Production)

```python
from sqlalchemy import Column, String, Boolean
from sqlalchemy.ext.asyncio import AsyncSession

class WebhookSubscriptionModel(Base):
    __tablename__ = "webhook_subscriptions"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    topic = Column(String, nullable=False)
    url = Column(String, nullable=False)
    encrypted_secret = Column(String, nullable=False)
    enabled = Column(Boolean, default=True)

class DatabaseWebhookSubscriptions:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    async def get_for_topic(
        self, tenant_id: str, topic: str
    ) -> list[WebhookSubscription]:
        async with self.session_factory() as session:
            # Match exact topic or wildcard patterns
            stmt = select(WebhookSubscriptionModel).where(
                WebhookSubscriptionModel.tenant_id == tenant_id,
                WebhookSubscriptionModel.enabled == True,
                # Topic matching logic (exact or wildcard)
            )
            result = await session.execute(stmt)
            return [to_subscription(row) for row in result.scalars()]
```

---

## Payload Signing

### How Signing Works

```
Canonical JSON body
        │
        ▼
┌───────────────────────────────────────┐
│   HMAC-SHA256(secret, canonical_json) │
└───────────────────────────────────────┘
        │
        ▼
X-Webhook-Signature: sha256=<hex_digest>
```

### Sign Function

```python
from svc_infra.webhooks.signing import sign

signature = sign(secret=b"secret_key", body={"order_id": "123"})
# Returns: "sha256=abc123..."
```

### Verify Function

```python
from svc_infra.webhooks.signing import verify, verify_any

# Single secret
is_valid = verify(
    secret=b"secret_key",
    body=request_body,
    signature=request.headers["X-Webhook-Signature"],
)

# Multiple secrets (for rotation)
is_valid = verify_any(
    secrets=[b"new_secret", b"old_secret"],
    body=request_body,
    signature=signature,
)
```

### Canonical JSON

The signing process uses canonical JSON (sorted keys, no whitespace):

```python
import json

def canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))

# {"amount":100,"order_id":"123"}
# NOT: {"order_id": "123", "amount": 100}
```

---

## Delivery

### Webhook Delivery Handler

```python
from svc_infra.jobs.builtins.webhook_delivery import make_webhook_handler

handler = make_webhook_handler(
    outbox=outbox_store,
    inbox=inbox_store,
    get_webhook_url_for_topic=get_url,
    get_secret_for_topic=get_secret,
    timeout_seconds=10,  # Per-delivery timeout
)
```

### HTTP Request Format

```http
POST /webhook HTTP/1.1
Host: customer.example.com
Content-Type: application/json
X-Webhook-ID: evt_abc123
X-Webhook-Topic: order.created
X-Webhook-Signature: sha256=<hmac_hex>
X-Webhook-Timestamp: 2024-01-15T10:30:00Z

{
  "order_id": "ord_abc",
  "total": 99.99
}
```

### Response Handling

| Status | Behavior |
|--------|----------|
| 2xx | Success, mark delivered |
| 4xx | Permanent failure, no retry |
| 5xx | Temporary failure, retry |
| Timeout | Temporary failure, retry |
| Network error | Temporary failure, retry |

---

## Retry Strategy

### Exponential Backoff

```python
from svc_infra.jobs.retry import ExponentialBackoff

retry_policy = ExponentialBackoff(
    base_delay=60,      # Start at 1 minute
    max_delay=3600,     # Max 1 hour between retries
    max_attempts=8,     # Total 8 attempts
    jitter=True,        # Add randomization
)

# Attempt 1: immediate
# Attempt 2: ~1 min
# Attempt 3: ~2 min
# Attempt 4: ~4 min
# Attempt 5: ~8 min
# Attempt 6: ~16 min
# Attempt 7: ~32 min
# Attempt 8: ~60 min (capped)
```

### Custom Retry Configuration

```python
handler = make_webhook_handler(
    outbox=outbox_store,
    inbox=inbox_store,
    get_webhook_url_for_topic=get_url,
    get_secret_for_topic=get_secret,
    retry_policy=ExponentialBackoff(
        base_delay=30,
        max_delay=7200,  # 2 hours
        max_attempts=10,
    ),
)
```

### Dead Letter Queue

Failed webhooks after all retries go to DLQ:

```python
from svc_infra.jobs.worker import run_worker

# Main delivery worker
await run_worker(queue="webhook_delivery", handler=handler)

# DLQ processor (alerting, manual review)
await run_worker(
    queue="webhook_delivery_dlq",
    handler=dlq_handler,  # Alert, store for manual retry
)
```

---

## Webhook Versioning

### API Version Header

```http
X-Webhook-Version: 2024-01-15
```

### Versioned Payloads

```python
class WebhookPayloadV1:
    """Original format."""
    order_id: str
    total: float

class WebhookPayloadV2:
    """New format with more detail."""
    order_id: str
    total: Money  # Structured money type
    line_items: list[LineItem]

def get_payload(version: str, order: Order) -> dict:
    if version >= "2024-01-15":
        return WebhookPayloadV2.from_order(order).to_dict()
    return WebhookPayloadV1.from_order(order).to_dict()
```

### Subscription Version Preference

```python
@dataclass
class WebhookSubscription:
    id: str
    tenant_id: str
    topic: str
    url: str
    encrypted_secret: str
    api_version: str = "2024-01-15"  # Preferred API version
```

---

## Security Best Practices

### 1. Always Verify Signatures

```python
from fastapi import HTTPException, Request
from svc_infra.webhooks.signing import verify

@app.post("/webhook")
async def receive_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Webhook-Signature")

    if not signature:
        raise HTTPException(400, "Missing signature")

    if not verify(secret=WEBHOOK_SECRET, body=body, signature=signature):
        raise HTTPException(401, "Invalid signature")

    payload = json.loads(body)
    await process_webhook(payload)
    return {"status": "ok"}
```

### 2. Validate Timestamp

Prevent replay attacks by checking timestamp freshness:

```python
from datetime import datetime, timedelta, timezone

MAX_AGE = timedelta(minutes=5)

def validate_timestamp(timestamp_header: str) -> bool:
    try:
        ts = datetime.fromisoformat(timestamp_header.rstrip("Z"))
        ts = ts.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - ts
        return abs(age) < MAX_AGE
    except ValueError:
        return False

@app.post("/webhook")
async def receive_webhook(request: Request):
    timestamp = request.headers.get("X-Webhook-Timestamp")
    if not validate_timestamp(timestamp):
        raise HTTPException(401, "Timestamp too old or invalid")
    # ... continue with signature verification
```

### 3. Secret Rotation

Support multiple secrets during rotation:

```python
from svc_infra.webhooks.signing import verify_any

# Provider side: store both secrets
secrets = [current_secret, previous_secret]

# Receiver side: verify against any valid secret
if not verify_any(secrets=secrets, body=body, signature=signature):
    raise HTTPException(401, "Invalid signature")
```

### 4. HTTPS Only

```python
@dataclass
class WebhookSubscription:
    url: str

    def __post_init__(self):
        if not self.url.startswith("https://"):
            raise ValueError("Webhook URL must use HTTPS")
```

### 5. IP Allowlisting (Optional)

```python
ALLOWED_IPS = ["203.0.113.10", "203.0.113.11"]

@app.post("/webhook")
async def receive_webhook(request: Request):
    client_ip = request.client.host
    if client_ip not in ALLOWED_IPS:
        raise HTTPException(403, "IP not allowed")
    # ... continue
```

### 6. Encrypt Secrets at Rest

```python
from svc_infra.crypto import encrypt_aes_gcm, decrypt_aes_gcm

# When storing subscription
encrypted = encrypt_aes_gcm(secret, encryption_key)
subscription.encrypted_secret = encrypted

# When delivering webhook
secret = decrypt_aes_gcm(subscription.encrypted_secret, encryption_key)
signature = sign(secret, payload)
```

---

## Payload Transformation

### Event to Webhook Payload

```python
from dataclasses import dataclass, asdict

@dataclass
class OrderCreatedEvent:
    order_id: str
    customer_id: str
    line_items: list
    total_cents: int
    created_at: datetime

def to_webhook_payload(event: OrderCreatedEvent) -> dict:
    """Transform internal event to external webhook payload."""
    return {
        "event_type": "order.created",
        "event_id": str(uuid4()),
        "created_at": event.created_at.isoformat(),
        "data": {
            "order": {
                "id": event.order_id,
                "customer_id": event.customer_id,
                "total": {
                    "amount": event.total_cents,
                    "currency": "USD",
                },
                "items": [
                    {"sku": item.sku, "quantity": item.qty}
                    for item in event.line_items
                ],
            }
        }
    }
```

### Filtering Sensitive Data

```python
SENSITIVE_FIELDS = {"ssn", "credit_card", "password", "secret"}

def sanitize_payload(payload: dict) -> dict:
    """Remove sensitive fields from webhook payloads."""
    return {
        k: sanitize_payload(v) if isinstance(v, dict) else v
        for k, v in payload.items()
        if k.lower() not in SENSITIVE_FIELDS
    }
```

---

## Testing

### Unit Tests

```python
import pytest
from svc_infra.webhooks.signing import sign, verify

def test_sign_and_verify():
    secret = b"test_secret"
    body = {"order_id": "123"}

    signature = sign(secret, body)

    assert verify(secret, body, signature)
    assert not verify(b"wrong_secret", body, signature)

def test_verify_any_with_rotation():
    old_secret = b"old"
    new_secret = b"new"
    body = {"data": "test"}

    # Signed with old secret
    signature = sign(old_secret, body)

    # Verify works with either secret
    assert verify_any([new_secret, old_secret], body, signature)
```

### Integration Tests

```python
import pytest
from httpx import AsyncClient

@pytest.fixture
def webhook_server(httpx_mock):
    """Mock external webhook receiver."""
    httpx_mock.add_response(url="https://example.com/webhook", status_code=200)
    return httpx_mock

async def test_webhook_delivery(webhook_service, webhook_server, outbox):
    # Publish event
    await webhook_service.publish(
        topic="order.created",
        tenant_id="test",
        payload={"order_id": "123"},
        outbox=outbox,
    )

    # Process delivery
    await process_outbox_once(outbox, webhook_handler)

    # Verify request was made
    request = webhook_server.get_request()
    assert request.headers["X-Webhook-Topic"] == "order.created"
    assert "X-Webhook-Signature" in request.headers

async def test_webhook_retry_on_5xx(webhook_service, httpx_mock, outbox):
    # First call fails, second succeeds
    httpx_mock.add_response(status_code=500)
    httpx_mock.add_response(status_code=200)

    await webhook_service.publish(
        topic="order.created",
        tenant_id="test",
        payload={"order_id": "123"},
        outbox=outbox,
    )

    # First attempt fails
    with pytest.raises(DeliveryFailed):
        await process_outbox_once(outbox, webhook_handler)

    # Retry succeeds
    await process_outbox_once(outbox, webhook_handler)

    assert httpx_mock.call_count == 2
```

### End-to-End Tests

```python
from fastapi.testclient import TestClient

def test_full_webhook_flow(client: TestClient, mock_webhook_receiver):
    # Create subscription
    response = client.post("/webhooks", json={
        "topic": "order.created",
        "url": mock_webhook_receiver.url,
    })
    assert response.status_code == 201

    # Trigger event
    response = client.post("/orders", json={"item": "widget"})
    assert response.status_code == 201

    # Wait for delivery
    import time
    time.sleep(1)

    # Verify webhook was received
    assert len(mock_webhook_receiver.received) == 1
    webhook = mock_webhook_receiver.received[0]
    assert webhook["topic"] == "order.created"
```

---

## Monitoring

### Key Metrics

```python
from prometheus_client import Counter, Histogram

webhook_deliveries = Counter(
    "webhook_deliveries_total",
    "Total webhook deliveries",
    ["topic", "status"],  # success, failed, retried
)

webhook_latency = Histogram(
    "webhook_delivery_seconds",
    "Webhook delivery latency",
    ["topic"],
    buckets=[0.1, 0.5, 1, 2, 5, 10],
)
```

### Logging

```python
import structlog

logger = structlog.get_logger()

async def deliver_webhook(subscription, payload):
    logger.info(
        "webhook_delivery_start",
        subscription_id=subscription.id,
        topic=subscription.topic,
        url=subscription.url,
    )

    try:
        response = await client.post(subscription.url, json=payload)
        logger.info(
            "webhook_delivery_success",
            subscription_id=subscription.id,
            status_code=response.status_code,
        )
    except Exception as e:
        logger.error(
            "webhook_delivery_failed",
            subscription_id=subscription.id,
            error=str(e),
        )
        raise
```

### Dashboard Queries (Prometheus)

```promql
# Delivery success rate
sum(rate(webhook_deliveries_total{status="success"}[5m]))
/ sum(rate(webhook_deliveries_total[5m]))

# Average latency by topic
histogram_quantile(0.95,
  sum(rate(webhook_delivery_seconds_bucket[5m])) by (topic, le)
)

# Failed deliveries needing attention
sum(webhook_deliveries_total{status="failed"}) by (topic)
```

---

## Troubleshooting

### Signature Verification Fails

**Causes:**
1. Secret mismatch
2. Body modified after signing
3. Non-canonical JSON on receiver side

**Debug:**
```python
# On receiver side
body_bytes = await request.body()
print(f"Raw body: {body_bytes}")

# Compute expected signature
expected = sign(secret, json.loads(body_bytes))
print(f"Expected: {expected}")
print(f"Received: {request.headers['X-Webhook-Signature']}")
```

### Deliveries Not Processing

**Check:**
1. Is the worker running? (`run_worker(queue="webhook_delivery")`)
2. Is outbox connected to same database?
3. Are jobs being created? (Query outbox table)

```sql
SELECT * FROM outbox_items
WHERE job_type = 'webhook_delivery'
ORDER BY created_at DESC
LIMIT 10;
```

### Customer Not Receiving Webhooks

**Checklist:**
1. Subscription enabled?
2. URL reachable? (test with curl)
3. Firewall blocking?
4. HTTPS certificate valid?
5. Response timing out?

---

## FastAPI Integration

### Complete Setup

```python
from fastapi import FastAPI, Depends, HTTPException
from svc_infra.webhooks.service import WebhookService
from svc_infra.jobs.outbox import OutboxStore

app = FastAPI()

webhook_service = WebhookService(subscriptions=db_subscriptions)

@app.post("/webhooks")
async def create_webhook(
    request: CreateWebhookRequest,
    tenant_id: str = Depends(get_tenant_id),
):
    subscription = await webhook_service.create_subscription(
        tenant_id=tenant_id,
        topic=request.topic,
        url=request.url,
        secret=generate_secret(),
    )
    return {"id": subscription.id, "secret": subscription.secret}

@app.delete("/webhooks/{subscription_id}")
async def delete_webhook(
    subscription_id: str,
    tenant_id: str = Depends(get_tenant_id),
):
    await webhook_service.delete_subscription(subscription_id, tenant_id)
    return {"status": "deleted"}

@app.get("/webhooks")
async def list_webhooks(tenant_id: str = Depends(get_tenant_id)):
    subs = await webhook_service.list_subscriptions(tenant_id)
    return {"webhooks": [to_response(s) for s in subs]}

# In your domain event handlers
async def on_order_created(order: Order, outbox: OutboxStore):
    await webhook_service.publish(
        topic="order.created",
        tenant_id=order.tenant_id,
        payload=to_webhook_payload(order),
        outbox=outbox,
    )
```

---

## See Also

- [Jobs](jobs.md) — Outbox pattern and job workers
- [Idempotency](idempotency.md) — Prevent duplicate event processing
- [API](api.md) — FastAPI setup and error handling
- [Observability](observability.md) — Metrics and tracing
