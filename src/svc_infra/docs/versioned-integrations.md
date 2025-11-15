# Using add_* Functions Under Versioned Routing

## Problem

Integration functions like `add_banking()`, `add_payments()`, or `add_sql_db()` are designed to create their own documentation cards (e.g., `/banking/docs`, `/_sql/docs`). However, you may want all features consolidated under a single versioned API prefix (e.g., `/v0/banking`) instead.

## Solution

Intercept the router before it's mounted to the app, preventing the separate docs card while preserving all the functionality.

### Pattern

```python
# src/your_api/routers/v0/banking.py
from fastapi import FastAPI, APIRouter
from unittest.mock import patch

# Create mock app to capture router
_mock_app = FastAPI()
_captured_router: APIRouter | None = None

# Intercept include_router to capture instead of mount
def _capture_router(router_to_capture: APIRouter, **kwargs):
    global _captured_router
    _captured_router = router_to_capture

_mock_app.include_router = _capture_router

# Patch add_prefixed_docs to prevent separate card
def _noop_add_prefixed_docs(*args, **kwargs):
    pass

# Call add_* function - it creates all routes but we capture the router
from fin_infra.banking import add_banking

with patch('svc_infra.api.fastapi.docs.scoped.add_prefixed_docs', _noop_add_prefixed_docs):
    banking_provider = add_banking(
        _mock_app,
        provider="plaid",
        prefix="/banking",
        cache_ttl=60,
    )

# Export captured router - svc-infra auto-discovers it
router = _captured_router
```

### Result

- ✅ All banking endpoints under `/v0/banking/*`
- ✅ Banking docs included in `/v0/docs` (not separate card)
- ✅ Full `add_banking()` functionality preserved (all routes, dependencies, validation)
- ✅ No manual endpoint redefinition required

## Complete Example

```python
# Directory structure
your_api/
  routers/
    v0/
      __init__.py
      status.py
      banking.py      # <- Integration wrapper
      payments.py     # <- Another integration wrapper

# banking.py - Full working example
"""
Banking integration under v0 routing.
Uses fin-infra's add_banking() with all features intact.
"""
from fastapi import FastAPI, APIRouter
from unittest.mock import patch

_mock_app = FastAPI()
_captured_router: APIRouter | None = None

def _capture_router(router: APIRouter, **kwargs):
    global _captured_router
    _captured_router = router

_mock_app.include_router = _capture_router

def _noop_docs(*args, **kwargs):
    pass

from fin_infra.banking import add_banking

with patch('svc_infra.api.fastapi.docs.scoped.add_prefixed_docs', _noop_docs):
    banking_provider = add_banking(
        _mock_app,
        provider="plaid",  # or "teller"
        prefix="/banking",
        cache_ttl=60,
    )

router = _captured_router

# Usage in app
# Just works - svc-infra auto-discovers router in v0 package
# Results in /v0/banking/* endpoints
```

## When to Use This Pattern

**Use when:**
- Building a monolithic versioned API where all features belong under `/v0`, `/v1`, etc.
- You want unified documentation at `/v0/docs` showing all features together
- You're consolidating multiple integrations under one version
- You need version-specific behavior for third-party integrations

**Don't use when:**
- Feature should have its own public docs card (e.g., public payment webhooks at `/payments/webhooks`)
- You want scoped documentation with separate OpenAPI specs per feature
- Integration is shared across multiple versions
- You need different auth/middleware for the integration vs versioned routes

## How It Works

1. **Router Capture**: Monkey-patch `app.include_router()` to intercept the router object
2. **Docs Prevention**: Patch `add_prefixed_docs()` to prevent creating separate card
3. **Call Integration**: Run `add_*()` function - it creates all routes/dependencies normally
4. **Export Router**: Return captured router for svc-infra auto-discovery
5. **Auto-Mount**: svc-infra finds `router` in `v0.banking` and mounts at `/v0/banking`

## Works With

This pattern works with any svc-infra or fin-infra function that:
- Calls `app.include_router()` internally
- Optionally calls `add_prefixed_docs()`
- Returns a provider/integration object

Examples:
- `add_banking()` - Financial account aggregation
- `add_payments()` - Payment processing
- `add_sql_db()` - SQL database resources (if you want under `/v0/_sql` instead of `/_sql`)
- `add_auth()` - Authentication system
- Custom `add_*()` functions following the same pattern

## Alternative: Manual Definition

If you need more control or the integration is simple, define routes manually:

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

## See Also

- [API Versioning](./api.md#versioning) - How svc-infra version routing works
- [Scoped Documentation](./docs-and-sdks.md#scoped-docs) - Understanding separate docs cards
- [Router Auto-Discovery](./api.md#router-discovery) - How routers are found and mounted
