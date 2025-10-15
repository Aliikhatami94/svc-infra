# APF Payments Integration Guide

A unified payments abstraction for FastAPI services supporting multiple payment providers (Stripe, Aiydan, etc.) with consistent APIs for intents, subscriptions, invoices, disputes, and more.

**Key Features:**
- 🚀 **Zero-boilerplate setup** – One function call creates a production-ready service
- 🔌 **Multi-provider support** – Stripe, Aiydan, or custom adapters
- 🛡️ **Built-in security** – Idempotency, rate limiting, webhook verification, auth guards
- 📊 **Observability included** – Prometheus metrics, OpenTelemetry tracing, structured logging
- 🔄 **Auto-configuration** – Reads environment variables, sensible defaults
- 📝 **Complete API** – 40+ endpoints for payments, subscriptions, invoices, disputes, refunds
- 🧪 **Test-friendly** – Mock adapters, comprehensive test coverage

---

## Quick Start

### 1. Install & Configure

```bash
# Install with your provider extras
pip install svc-infra stripe  # for Stripe
# or
pip install svc-infra aiydan  # for Aiydan (when available)
```

Set environment variables for your chosen provider:

**Stripe:**
```bash
export STRIPE_SECRET="sk_test_..."
export STRIPE_WH_SECRET="whsec_..."  # optional, for webhook verification
export PAYMENTS_PROVIDER="stripe"    # default
```

**Aiydan:**
```bash
export AIYDAN_API_KEY="aiydan_key_..."
export AIYDAN_CLIENT_KEY="..."           # optional
export AIYDAN_MERCHANT_ACCOUNT="..."     # optional
export AIYDAN_HMAC_KEY="..."             # optional
export AIYDAN_BASE_URL="https://..."     # optional
export AIYDAN_WH_SECRET="..."            # optional
export PAYMENTS_PROVIDER="aiydan"
```

### 2. Create Your FastAPI App with Payments

**Option A: The Easiest Way (Recommended)**

Use `easy_service_app` for a complete FastAPI service with logging, observability, and payments in one call:

```python
from svc_infra.api.fastapi.ease import easy_service_app

app = easy_service_app(
    name="My Payment Service",
    release="1.0.0",
    versions=[
        ("v1", "myapp.routers.v1", None),  # (tag, routers_package, public_base_url)
    ],
    root_routers="myapp.routers.root",  # includes your root-level routes
)

# That's it! Logging, metrics, and all svc-infra features are auto-configured from env vars.
```

Then add payments:

```python
from svc_infra.api.fastapi.apf_payments.setup import add_payments

add_payments(app, prefix="/payments")
```

**Option B: Manual Setup (More Control)**

If you need fine-grained control:

```python
from fastapi import FastAPI
from svc_infra.api.fastapi.apf_payments.setup import add_payments

app = FastAPI()

# Auto-registers default providers (Stripe, Aiydan) based on env config
add_payments(app, prefix="/payments")
```

**Option C: Full-Featured Service Setup**

Use `setup_service_api` for multi-version APIs with custom routers:

```python
from svc_infra.api.fastapi.setup import setup_service_api
from svc_infra.api.fastapi.openapi.models import ServiceInfo, APIVersionSpec
from svc_infra.api.fastapi.apf_payments.setup import add_payments

service = ServiceInfo(name="My Payment Service", release="1.0.0")
versions = [
    APIVersionSpec(tag="v1", routers_package="myapp.routers.v1"),
]

app = setup_service_api(
    service=service,
    versions=versions,
    root_routers="myapp.routers.root",
    public_cors_origins=["http://localhost:3000"],
)

add_payments(app, prefix="/payments")
```

**Tenant Context**

All payments endpoints require a tenant identifier. The FastAPI router now
derives it automatically from the authenticated principal:

- API key principals → ``principal.api_key.tenant_id``
- User principals → ``principal.user.tenant_id``
- Fallbacks: ``X-Tenant-Id`` request header or ``request.state.tenant_id``

If you need custom mapping logic (for example, translating API keys to an
external tenant registry), register an override during startup:

```python
from svc_infra.api.fastapi.apf_payments.router import set_payments_tenant_resolver

async def resolve_tenant(request, identity, header):
    # return a string tenant id, or None to fall back to the defaults
    return "tenant-from-custom-logic"

set_payments_tenant_resolver(resolve_tenant)
```

If no tenant can be derived (and the override also returns ``None``), the
router responds with ``400 tenant_context_missing`` so callers can supply the
missing context explicitly.

**Environment-Based Configuration**

The `easy_service_app` reads these env vars automatically:
- `ENABLE_LOGGING` (default: true) – Auto-configures JSON logs in prod, plain logs in dev
- `ENABLE_OBS` (default: true) – Enables Prometheus metrics at `/metrics`
- `LOG_LEVEL` – DEBUG, INFO, WARNING, etc.
- `LOG_FORMAT` – json or plain
- `CORS_ALLOW_ORIGINS` – Comma-separated CORS origins

No boilerplate needed! 🎉

---

That's it! Your app now has:
- `POST /payments/customers` – Create/upsert customers
- `POST /payments/intents` – Create payment intents
- `POST /payments/methods/attach` – Attach payment methods
- `GET /payments/methods` – List customer payment methods
- `POST /payments/subscriptions` – Create subscriptions
- `POST /payments/invoices` – Create invoices
- `POST /payments/webhooks/{provider}` – Handle provider webhooks
- And many more endpoints for refunds, disputes, payouts, etc.

### 3. Complete Example (app.py)

Here's a complete, production-ready service in ~20 lines:

```python
# app.py
from svc_infra.api.fastapi.ease import easy_service_app
from svc_infra.api.fastapi.apf_payments.setup import add_payments

# Create service with auto-configured logging, metrics, CORS, middleware
app = easy_service_app(
    name="Payment API",
    release="1.0.0",
    versions=[
        ("v1", "myapp.routers.v1", None),
    ],
)

# Add payments functionality
add_payments(app, prefix="/payments")

# Optional: Add custom routes
@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

**Run it:**
```bash
export STRIPE_SECRET="sk_test_..."
export STRIPE_WH_SECRET="whsec_..."
python app.py
```

**Access:**
- Swagger docs: `http://localhost:8000/` (landing page with all doc links)
- Version v1: `http://localhost:8000/v1/docs`
- Payments: `http://localhost:8000/payments/`
- Metrics: `http://localhost:8000/metrics`

### Why Use `easy_service_app`?

Without `easy_service_app`, you'd need to manually:
- Configure logging (JSON in prod, plain in dev)
- Set up CORS middleware
- Add request ID middleware
- Configure error handlers (catch-all exceptions)
- Add idempotency middleware
- Add rate limiting middleware
- Set up OpenAPI documentation
- Configure Prometheus metrics
- Add OpenTelemetry instrumentation
- Mount versioned routers
- Create a landing page for docs
- Handle environment-based config

**That's 50+ lines of boilerplate!** With `easy_service_app`, it's **3 lines**:

```python
app = easy_service_app(name="My API", release="1.0.0", versions=[("v1", "myapp.routers.v1", None)])
add_payments(app, prefix="/payments")
# Done! Production-ready service with all features.
```

---

## Core Concepts

### Providers
Payment providers are registered adapters that implement the `ProviderAdapter` protocol. Built-in:
- **Stripe** (`stripe`): Full-featured, production-ready.
- **Aiydan** (`aiydan`): Custom provider with similar capabilities.

The active provider is selected via `PAYMENTS_PROVIDER` env var.

### Router Groups by Auth Posture
- **Public** (`/payments/webhooks/{provider}`): No auth, for webhooks.
- **User** (`/payments/customers`, `/payments/intents`, `/payments/methods/attach`): Requires user JWT.
- **Protected** (`/payments/methods`, `/payments/intents/{id}/confirm`, etc.): Requires auth (user or service).
- **Service** (`/payments/products`, `/payments/prices`): Service-to-service auth (API key).

### Key Entities
- **Customers**: Link your app users to provider customer records.
- **Payment Intents**: Represent a payment attempt (amount, currency, status).
- **Payment Methods**: Saved cards/bank accounts attached to customers.
- **Subscriptions**: Recurring billing tied to prices and products.
- **Invoices**: Generated bills (automatic or manual).
- **Refunds / Disputes / Payouts**: Post-payment flows.

---

## Common Workflows

### Create a Customer and Attach a Payment Method

```python
import httpx

# 1. Create/upsert customer
resp = await client.post(
    "/payments/customers",
    json={"email": "user@example.com", "name": "Alice"},
    headers={"Idempotency-Key": "customer-alice-1"}
)
customer = resp.json()
customer_id = customer["provider_customer_id"]  # e.g., "cus_123"

# 2. Attach payment method (token from frontend)
resp = await client.post(
    "/payments/methods/attach",
    json={
        "customer_provider_id": customer_id,
        "payment_method_token": "pm_test_...",  # from Stripe.js or similar
        "make_default": True
    },
    headers={"Idempotency-Key": "attach-pm-1"}
)
method = resp.json()
```

### Create a Payment Intent

```python
# Create an intent for $50.00 USD
resp = await client.post(
    "/payments/intents",
    json={
        "amount": 5000,  # minor units (cents)
        "currency": "USD",
        "description": "Order #12345",
        "capture_method": "automatic"
    },
    headers={"Idempotency-Key": "intent-order-12345"}
)
intent = resp.json()
client_secret = intent["client_secret"]  # pass to frontend for confirmation
```

### List Customer Payment Methods

```python
resp = await client.get(
    "/payments/methods",
    params={"customer_provider_id": "cus_123"}
)
methods = resp.json()["items"]
```

### Create a Subscription

```python
# 1. Create product & price (service-level)
product_resp = await client.post(
    "/payments/products",
    json={"name": "Pro Plan", "active": True},
    headers={"Idempotency-Key": "product-pro", "Authorization": "Bearer <service-token>"}
)
product_id = product_resp.json()["provider_product_id"]

price_resp = await client.post(
    "/payments/prices",
    json={
        "provider_product_id": product_id,
        "currency": "USD",
        "unit_amount": 2000,
        "interval": "month",
        "active": True
    },
    headers={"Idempotency-Key": "price-pro-monthly", "Authorization": "Bearer <service-token>"}
)
price_id = price_resp.json()["provider_price_id"]

# 2. Subscribe customer
sub_resp = await client.post(
    "/payments/subscriptions",
    json={
        "customer_provider_id": "cus_123",
        "price_provider_id": price_id,
        "quantity": 1
    },
    headers={"Idempotency-Key": "sub-alice-pro"}
)
subscription = sub_resp.json()
```

### Handle Webhooks

```python
# Provider (e.g., Stripe) POSTs to /payments/webhooks/stripe
# The adapter verifies signature and parses event
# Events trigger internal actions (e.g., mark payment succeeded, post to ledger)

# In your app:
from svc_infra.apf_payments.service import PaymentsService

async def on_payment_succeeded(event_data: dict):
    # Custom business logic after payment
    pass
```

---

## Advanced Usage

### Fine-Tuned App Configuration

Override env-based defaults with `EasyAppOptions`:

```python
from svc_infra.api.fastapi.ease import easy_service_app, EasyAppOptions, LoggingOptions, ObservabilityOptions

app = easy_service_app(
    name="Payment API",
    release="1.0.0",
    versions=[("v1", "myapp.routers.v1", None)],
    options=EasyAppOptions(
        logging=LoggingOptions(
            enable=True,
            level="DEBUG",
            fmt="json"
        ),
        observability=ObservabilityOptions(
            enable=True,
            db_engines=[engine],  # pass SQLAlchemy engines for connection pool metrics
            metrics_path="/metrics",
            skip_metric_paths=["/health", "/metrics"]
        )
    )
)
```

Or use flags for quick toggles:

```python
app = easy_service_app(
    name="Payment API",
    release="1.0.0",
    versions=[("v1", "myapp.routers.v1", None)],
    enable_logging=True,
    enable_observability=False  # disable metrics
)
```

**Configuration Precedence** (strongest → weakest):
1. Function arguments (`enable_logging`, `enable_observability`)
2. `options=` parameter
3. Environment variables (`ENABLE_LOGGING`, `ENABLE_OBS`, etc.)

### Custom Provider Adapter

If you need a provider not included by default:

```python
from svc_infra.apf_payments.provider.base import ProviderAdapter
from svc_infra.api.fastapi.apf_payments.setup import add_payments

class MyCustomAdapter(ProviderAdapter):
    name = "mycustom"

    async def ensure_customer(self, data):
        # Your implementation
        ...

    async def create_intent(self, data, *, user_id):
        # Your implementation
        ...

    # Implement all required methods...

# Register it
add_payments(
    app,
    register_default_providers=False,  # skip Stripe/Aiydan auto-registration
    adapters=[MyCustomAdapter()]
)
```

### Multiple Providers in One App

```python
from svc_infra.apf_payments.provider.stripe import StripeAdapter
from svc_infra.apf_payments.provider.aiydan import AiydanAdapter
from svc_infra.apf_payments.provider.registry import get_provider_registry

# Register both
reg = get_provider_registry()
reg.register(StripeAdapter())
reg.register(AiydanAdapter())

# Select at runtime via settings or per-request logic
# (Default provider is controlled by PAYMENTS_PROVIDER env)
```

### Database Models

The payments module creates these tables (via Alembic migrations):
- `pay_customers`: Maps app users to provider customer IDs
- `pay_intents`: Stores payment intent records
- `pay_payment_methods`: Cached payment methods
- `pay_products`, `pay_prices`: Product/price catalog
- `pay_subscriptions`: Active subscriptions
- `pay_invoices`: Invoice records
- `pay_events`: Webhook event log
- `ledger_entries`: Financial ledger (debits/credits for payments, refunds, fees, payouts)

To generate migrations:
```bash
# From your project root
svc-infra db revision -m "Add payments tables"
svc-infra db upgrade head
```

### Observability

Payments endpoints are instrumented with OpenTelemetry spans. Webhook processing is logged.

```python
from svc_infra.obs import add_observability

shutdown = add_observability(app, db_engines=[engine])
# Metrics available at /metrics
```

### Idempotency

All mutating endpoints (`POST`, `PUT`, `DELETE`) require an `Idempotency-Key` header to prevent duplicate operations:

```python
headers = {"Idempotency-Key": "unique-key-per-request"}
```

Implemented via `IdempotencyMiddleware` (uses in-memory store by default; plug in Redis for production).

---

## Configuration Reference

### Environment Variables

**FastAPI Service Setup** (used by `easy_service_app`):

| Variable | Description | Default |
|----------|-------------|---------|
| `ENABLE_LOGGING` | Enable automatic logging setup | `true` |
| `ENABLE_OBS` | Enable observability (metrics/tracing) | `true` |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | INFO (prod/test), DEBUG (dev/local) |
| `LOG_FORMAT` | Log format (`json` or `plain`) | json (prod/test), plain (dev/local) |
| `LOG_DROP_PATHS` | Comma-separated paths to exclude from logs | `/metrics` (prod/test) |
| `CORS_ALLOW_ORIGINS` | Comma-separated CORS origins | `http://localhost:3000` |
| `METRICS_PATH` | Path for Prometheus metrics endpoint | `/metrics` |
| `OBS_SKIP_PATHS` | Comma/space-separated paths to skip in metrics | `/metrics,/health` |
| `APP_ENV` | Environment name (prod, test, dev, local) | Auto-detected from `RAILWAY_ENVIRONMENT_NAME` or defaults to `local` |

**Payment Provider Configuration**:

| Variable | Description | Default |
|----------|-------------|---------|
| `PAYMENTS_PROVIDER` | Active provider name (`stripe`, `aiydan`, etc.) | `stripe` |
| `STRIPE_SECRET` or `STRIPE_API_KEY` | Stripe secret key | - |
| `STRIPE_WH_SECRET` | Stripe webhook signing secret | - |
| `AIYDAN_API_KEY` | Aiydan API key | - |
| `AIYDAN_CLIENT_KEY` | Aiydan client key (optional) | - |
| `AIYDAN_MERCHANT_ACCOUNT` | Aiydan merchant account (optional) | - |
| `AIYDAN_HMAC_KEY` | Aiydan HMAC key for signatures (optional) | - |
| `AIYDAN_BASE_URL` | Aiydan API base URL (optional) | - |
| `AIYDAN_WH_SECRET` | Aiydan webhook secret (optional) | - |

### Settings Object

```python
from svc_infra.apf_payments.settings import get_payments_settings

settings = get_payments_settings()
print(settings.default_provider)  # "stripe"
print(settings.stripe.secret_key.get_secret_value())  # "sk_test_..."
```

---

## API Endpoints Summary

### Customers
- `POST /payments/customers` – Create/upsert customer (user auth)

### Payment Intents
- `POST /payments/intents` – Create intent (user auth)
- `POST /payments/intents/{id}/confirm` – Confirm intent (protected)
- `POST /payments/intents/{id}/cancel` – Cancel intent (protected)
- `POST /payments/intents/{id}/refund` – Refund intent (protected)
- `POST /payments/intents/{id}/capture` – Capture manual intent (protected)
- `GET /payments/intents/{id}` – Retrieve intent (protected)
- `GET /payments/intents` – List intents (protected)

### Payment Methods
- `POST /payments/methods/attach` – Attach method to customer (user auth)
- `GET /payments/methods` – List customer methods (protected, requires `customer_provider_id` query param)
- `POST /payments/methods/{id}/detach` – Detach method (protected)
- `POST /payments/methods/{id}/default` – Set as default (protected, requires `customer_provider_id` query param)
- `GET /payments/methods/{id}` – Retrieve method (protected)
- `PUT /payments/methods/{id}` – Update method (protected)

### Products & Prices (Service Auth)
- `POST /payments/products` – Create product
- `GET /payments/products` – List products
- `GET /payments/products/{id}` – Retrieve product
- `PUT /payments/products/{id}` – Update product
- `POST /payments/prices` – Create price
- `GET /payments/prices` – List prices
- `GET /payments/prices/{id}` – Retrieve price
- `PUT /payments/prices/{id}` – Update price

### Subscriptions
- `POST /payments/subscriptions` – Create subscription (protected)
- `POST /payments/subscriptions/{id}` – Update subscription (protected)
- `POST /payments/subscriptions/{id}/cancel` – Cancel subscription (protected)
- `GET /payments/subscriptions/{id}` – Retrieve subscription (protected)
- `GET /payments/subscriptions` – List subscriptions (protected)

### Invoices
- `POST /payments/invoices` – Create invoice (protected)
- `POST /payments/invoices/{id}/finalize` – Finalize invoice (protected)
- `POST /payments/invoices/{id}/void` – Void invoice (protected)
- `POST /payments/invoices/{id}/pay` – Pay invoice (protected)
- `POST /payments/invoices/{id}/line-items` – Add line item (protected)
- `GET /payments/invoices/{id}` – Retrieve invoice (protected)
- `GET /payments/invoices` – List invoices (protected)
- `GET /payments/invoices/{id}/line-items` – List line items (protected)
- `GET /payments/invoices/preview` – Preview upcoming invoice (protected)

### Disputes
- `GET /payments/disputes` – List disputes (protected)
- `GET /payments/disputes/{id}` – Retrieve dispute (protected)
- `POST /payments/disputes/{id}/evidence` – Submit evidence (protected)

### Balance & Payouts
- `GET /payments/balance` – Get balance snapshot (protected)
- `GET /payments/payouts` – List payouts (protected)
- `GET /payments/payouts/{id}` – Retrieve payout (protected)

### Refunds
- `GET /payments/refunds` – List refunds (protected)
- `GET /payments/refunds/{id}` – Retrieve refund (protected)

### Transactions & Statements
- `GET /payments/transactions` – List all ledger transactions (protected)
- `GET /payments/statements/daily` – Daily rollup statements (protected)

### Usage Records (Metered Billing)
- `POST /payments/usage-records` – Create usage record (protected)
- `GET /payments/usage-records` – List usage records (protected)
- `GET /payments/usage-records/{id}` – Retrieve usage record (protected)

### Setup Intents (Off-Session)
- `POST /payments/setup-intents` – Create setup intent (user auth)
- `POST /payments/setup-intents/{id}/confirm` – Confirm setup intent (protected)
- `GET /payments/setup-intents/{id}` – Retrieve setup intent (protected)

### Webhooks
- `POST /payments/webhooks/{provider}` – Receive provider webhooks (public, no auth)

### Webhook Replay (Testing)
- `POST /payments/webhooks/{provider}/replay` – Replay webhook event (protected)

---

## Testing

### Unit Tests

```bash
pytest tests/payments/
```

### Integration Tests

Mock the provider adapter:

```python
from svc_infra.apf_payments.provider.base import ProviderAdapter

class FakeAdapter(ProviderAdapter):
    name = "fake"

    async def ensure_customer(self, data):
        return CustomerOut(
            id="cus_fake",
            provider="fake",
            provider_customer_id="cus_fake",
            email=data.email
        )
    # ... implement other methods

add_payments(app, register_default_providers=False, adapters=[FakeAdapter()])
```

### Local Webhook Testing

Use Stripe CLI or similar:

```bash
stripe listen --forward-to http://localhost:8000/payments/webhooks/stripe
```

---

## Troubleshooting

### "No payments adapter registered for 'xyz'"
- Ensure you've set the correct `PAYMENTS_PROVIDER` env var.
- Verify the provider SDK is installed (`pip install stripe` or `pip install aiydan`).
- Check that the provider credentials are configured.

### "Idempotency-Key required"
- All mutating operations need an `Idempotency-Key` header.
- Use a unique key per logical operation (e.g., `f"order-{order_id}-payment"`).

### Webhook signature verification fails
- Ensure `STRIPE_WH_SECRET` (or equivalent) is set correctly.
- Check that the webhook endpoint URL in your provider dashboard matches your deployment.

### Database migrations not applied
```bash
svc-infra db upgrade head
```

---

## Security Best Practices

1. **Never log or expose secret keys** – Use `SecretStr` in settings.
2. **Always verify webhook signatures** – Prevents spoofed events.
3. **Use HTTPS in production** – Payment data is sensitive.
4. **Implement rate limiting** – Protect webhook endpoints from abuse.
5. **Store minimal PII** – Only cache what's needed; rely on provider for full records.
6. **Rotate API keys periodically** – Follow provider recommendations.

---

## Performance Tips

- **Cache payment methods locally** – Reduce API calls to provider.
- **Use cursor-based pagination** – More efficient for large result sets.
- **Process webhooks asynchronously** – Respond quickly (< 5s) to avoid retries.
- **Monitor provider API usage** – Stay within rate limits.

---

## Roadmap

- [ ] Support for additional providers (PayPal, Square, etc.)
- [ ] Enhanced ledger reconciliation tools
- [ ] Multi-currency support improvements
- [ ] Automatic retry logic for failed provider calls
- [ ] Admin dashboard for payment operations

---

## Support

- GitHub Issues: [svc-infra/issues](https://github.com/your-org/svc-infra/issues)
- Documentation: [Full docs](https://github.com/your-org/svc-infra#readme)
- Provider docs: [Stripe](https://stripe.com/docs/api), [Aiydan](#) (when available)

---

**Happy payments building!** 🎉
