# Using add_* Functions Under Versioned Routing

## Problem

By default, `add_*` functions from svc-infra and fin-infra mount routes at root level (e.g., `/banking/*`, `/_sql/*`). However, you may want all features consolidated under a single versioned API prefix (e.g., `/v0/banking`) to keep your API organized under version namespaces.

## Simple Solution (Recommended)

Use the `extract_router()` helper:

```python
# src/your_api/routers/v0/banking.py
from svc_infra.api.fastapi.versioned import extract_router
from fin_infra.banking import add_banking

# Extract router and provider from add_banking()
router, banking_provider = extract_router(
    add_banking,
    prefix="/banking",
    provider="plaid",
    cache_ttl=60,
)

# That's it! svc-infra auto-discovers 'router' and mounts at /v0/banking
```

### Result

- ✅ All banking endpoints under `/v0/banking/*`
- ✅ Banking docs included in `/v0/docs` (not separate card)
- ✅ Full `add_banking()` functionality preserved
- ✅ Returns provider instance for additional use

## Complete Example

```python
# Directory structure
your_api/
  routers/
    v0/
      __init__.py
      status.py
      banking.py      # <- Integration using helper
      payments.py     # <- Another integration

# banking.py - Clean and simple
"""Banking integration under v0 routing."""
from svc_infra.api.fastapi.versioned import extract_router
from fin_infra.banking import add_banking

router, banking_provider = extract_router(
    add_banking,
    prefix="/banking",
    provider="plaid",  # or "teller"
    cache_ttl=60,
)

# Optional: Store provider on app state for later use
# This happens in app.py after router discovery:
# app.state.banking = banking_provider
```

## Works With

Any svc-infra or fin-infra function that calls `app.include_router()`:

```python
# Banking integration
from fin_infra.banking import add_banking
router, provider = extract_router(add_banking, prefix="/banking", provider="plaid")

# Market data
from fin_infra.markets import add_market_data
router, provider = extract_router(add_market_data, prefix="/markets")

# Analytics
from fin_infra.analytics import add_analytics
router, provider = extract_router(add_analytics, prefix="/analytics")

# Budgets
from fin_infra.budgets import add_budgets
router, provider = extract_router(add_budgets, prefix="/budgets")

# Documents
from fin_infra.documents import add_documents
router, provider = extract_router(add_documents, prefix="/documents")

# Any custom add_* function following the pattern
```

## When to Use

**Use when:**
- Building a monolithic versioned API where all features belong under `/v0`, `/v1`, etc.
- You want unified documentation at `/v0/docs` showing all features together
- You're consolidating multiple integrations under one version
- You need version-specific behavior for third-party integrations

**Don't use when:**
- Feature should have its own root-level endpoint (e.g., public webhooks at `/webhooks`)
- Integration is shared across multiple versions (mount at root instead)
- You only need a subset of endpoints (define manually)

## Alternative: Manual Definition

For simple integrations, define routes manually:

```python
# routers/v0/banking.py
from svc_infra.api.fastapi.dual.public import public_router
from fin_infra.banking import easy_banking

router = public_router(prefix="/banking", tags=["Banking"])
banking = easy_banking(provider="plaid")

@router.post("/link")
async def create_link(request: CreateLinkRequest):
    return banking.create_link_token(user_id=request.user_id)

# ... define other endpoints
```

Use manual definition when:
- Only need a subset of integration endpoints
- Want custom validation/transforms per endpoint
- Integration is very simple (2-3 endpoints)
- Need version-specific behavior per endpoint

## How It Works

The `extract_router()` helper:

1. **Creates Mock App**: Temporary FastAPI instance to capture router
2. **Intercepts Router**: Monkey-patches `include_router()` to capture instead of mount
3. **Calls Integration**: Runs `add_*()` function which creates all routes normally
4. **Returns Router**: Exports captured router for svc-infra auto-discovery
5. **Auto-Mounts**: svc-infra finds `router` in `v0.banking` and mounts at `/v0/banking`

The provider/integration instance is also returned for additional use if needed.

## See Also

- [API Versioning](./api.md#versioning) - How svc-infra version routing works
- [Router Auto-Discovery](./api.md#router-discovery) - How routers are found and mounted
- [Dual Routers](./api.md#dual-routers) - Similar pattern for public/protected routers
- `svc_infra.api.fastapi.versioned` - Source code for helper function
