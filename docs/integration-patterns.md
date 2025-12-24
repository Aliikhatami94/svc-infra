# Integration Patterns — router_from_object()

> **Purpose**: Cross-package guide for exposing any domain service as REST APIs
>
> **Module**: `svc_infra.api.fastapi.object_router`
>
> **See Also**: [Object Router Reference](object-router.md)

---

## Overview

`router_from_object()` is a generic utility designed for use by any domain package
(fin-infra, robo-infra, custom services) to expose Python objects as FastAPI endpoints.
This guide shows integration patterns and best practices for various domains.

---

## Pattern 1: Financial Services

Expose portfolio managers, analytics, or trading systems as REST APIs.

### Portfolio API

```python
from decimal import Decimal
from fastapi import FastAPI
from pydantic import BaseModel

from svc_infra.api.fastapi import router_from_object


class AllocationResponse(BaseModel):
    """Asset allocation breakdown."""
    stocks: float
    bonds: float
    cash: float
    crypto: float


class PortfolioService:
    """Portfolio analytics service."""

    def __init__(self, user_id: str):
        self.user_id = user_id

    def get_total_value(self) -> float:
        """Get current total portfolio value in USD."""
        return 125432.50

    def get_allocation(self) -> AllocationResponse:
        """Get current asset allocation percentages."""
        return AllocationResponse(
            stocks=60.0,
            bonds=25.0,
            cash=10.0,
            crypto=5.0,
        )

    def get_returns(self, period: str = "ytd") -> float:
        """Get portfolio returns for a time period.

        Query params: period (ytd, mtd, 1y, 3y, 5y)
        """
        returns = {"ytd": 8.5, "mtd": 1.2, "1y": 15.3}
        return returns.get(period, 0.0)

    def list_holdings(self, limit: int = 10) -> list[dict]:
        """List portfolio holdings sorted by value."""
        return [
            {"symbol": "AAPL", "value": 15000, "pct": 12.0},
            {"symbol": "MSFT", "value": 12000, "pct": 9.6},
        ][:limit]


# Create FastAPI app
app = FastAPI(title="Portfolio API")

# Convert service to router
portfolio = PortfolioService(user_id="user_123")
router = router_from_object(
    portfolio,
    prefix="/portfolio",
    tags=["Portfolio"],
    auth_required=True,  # Requires JWT authentication
)
app.include_router(router)

# Generated endpoints:
# GET  /portfolio/total-value   -> 125432.50
# GET  /portfolio/allocation    -> {"stocks": 60.0, ...}
# GET  /portfolio/returns?period=ytd -> 8.5
# GET  /portfolio/holdings?limit=5   -> [...]
```

### HTTP Verb Inference

The `get_*` and `list_*` prefixes automatically map to GET:

| Method | Inferred | Endpoint |
|--------|----------|----------|
| `get_total_value()` | GET | `/total-value` |
| `get_allocation()` | GET | `/allocation` |
| `list_holdings()` | GET | `/holdings` |

---

## Pattern 2: CRUD Service

Standard create/read/update/delete pattern.

```python
from pydantic import BaseModel
from svc_infra.api.fastapi import router_from_object, endpoint_exclude


class CreateUserRequest(BaseModel):
    name: str
    email: str


class User(BaseModel):
    id: str
    name: str
    email: str


class UserService:
    """User management service."""

    def __init__(self):
        self.users: dict[str, User] = {}

    def create_user(self, name: str, email: str) -> User:
        """Create a new user account."""
        user_id = f"user_{len(self.users) + 1}"
        user = User(id=user_id, name=name, email=email)
        self.users[user_id] = user
        return user

    def get_user(self, user_id: str) -> User:
        """Get user by ID."""
        if user_id not in self.users:
            raise KeyError(f"User {user_id} not found")
        return self.users[user_id]

    def list_users(self, limit: int = 100) -> list[User]:
        """List all users."""
        return list(self.users.values())[:limit]

    def update_user(self, user_id: str, name: str | None = None, email: str | None = None) -> User:
        """Update user details."""
        if user_id not in self.users:
            raise KeyError(f"User {user_id} not found")

        user = self.users[user_id]
        if name:
            user = User(id=user.id, name=name, email=user.email)
        if email:
            user = User(id=user.id, name=user.name, email=email)
        self.users[user_id] = user
        return user

    def delete_user(self, user_id: str) -> dict:
        """Delete a user account."""
        if user_id not in self.users:
            raise KeyError(f"User {user_id} not found")
        del self.users[user_id]
        return {"deleted": user_id}

    @endpoint_exclude
    def _validate_email(self, email: str) -> bool:
        """Internal validation - not exposed."""
        return "@" in email


# Create router
router = router_from_object(
    UserService(),
    prefix="/users",
    tags=["Users"],
)

# Generated endpoints:
# POST   /users/user         -> Create user  (create_user)
# GET    /users/user/{user_id} -> Get user   (get_user)
# GET    /users/users        -> List users   (list_users)
# PUT    /users/user/{user_id} -> Update     (update_user)
# DELETE /users/user/{user_id} -> Delete     (delete_user)
```

### Path Parameters

Parameters ending with `_id` or named `id` automatically become path parameters:

```python
def get_user(self, user_id: str) -> User:
    # user_id becomes path param: /user/{user_id}
    ...

def get_order_item(self, order_id: str, item_id: str) -> Item:
    # Both become path params: /order-item/{order_id}/{item_id}
    ...
```

---

## Pattern 3: Multi-Service Composition

Combine multiple services into a single API.

```python
from fastapi import FastAPI
from svc_infra.api.fastapi import router_from_object


class AccountService:
    """Bank account operations."""

    def get_balance(self, account_id: str) -> float:
        """Get account balance."""
        return 5432.10

    def list_accounts(self) -> list[dict]:
        """List all accounts."""
        return [{"id": "ACC001", "type": "checking", "balance": 5432.10}]


class TransferService:
    """Fund transfer operations."""

    def create_transfer(
        self,
        from_account: str,
        to_account: str,
        amount: float,
    ) -> dict:
        """Initiate a fund transfer."""
        return {
            "transfer_id": "TRF001",
            "status": "pending",
            "amount": amount,
        }

    def get_transfer(self, transfer_id: str) -> dict:
        """Get transfer status."""
        return {"transfer_id": transfer_id, "status": "completed"}


class PaymentService:
    """Payment processing."""

    def create_payment(self, amount: float, recipient: str) -> dict:
        """Process a payment."""
        return {"payment_id": "PAY001", "status": "completed"}

    def list_payments(self, limit: int = 10) -> list[dict]:
        """List recent payments."""
        return [{"payment_id": "PAY001", "amount": 100.00}]


# Create FastAPI app with multiple service routers
app = FastAPI(title="Banking API")

app.include_router(
    router_from_object(AccountService(), prefix="/accounts", tags=["Accounts"])
)
app.include_router(
    router_from_object(TransferService(), prefix="/transfers", tags=["Transfers"])
)
app.include_router(
    router_from_object(PaymentService(), prefix="/payments", tags=["Payments"])
)

# API structure:
# /accounts/balance/{account_id}  GET
# /accounts/accounts              GET
# /transfers/transfer             POST
# /transfers/transfer/{transfer_id} GET
# /payments/payment               POST
# /payments/payments              GET
```

---

## Pattern 4: Custom HTTP Verbs

Override automatic verb inference when needed.

```python
from svc_infra.api.fastapi import router_from_object, endpoint


class AnalyticsService:
    """Analytics with custom HTTP mappings."""

    # Override: compute_metrics should be GET, not POST
    @endpoint(method="GET", path="/metrics", summary="Compute analytics metrics")
    def compute_metrics(self, start_date: str, end_date: str) -> dict:
        """Compute metrics for a date range (read-only operation)."""
        return {"visits": 1000, "conversions": 50}

    # Override: clear should be DELETE, not POST
    @endpoint(method="DELETE", path="/cache", summary="Clear analytics cache")
    def clear_cache(self) -> dict:
        """Clear the analytics cache."""
        return {"cleared": True}

    # Default inference works fine
    def get_dashboard(self) -> dict:
        """Get dashboard data."""
        return {"widgets": ["chart", "table"]}


# The methods parameter can also override verbs
router = router_from_object(
    AnalyticsService(),
    prefix="/analytics",
    methods={
        "compute_metrics": "GET",  # Alternative to @endpoint decorator
        "clear_cache": "DELETE",
    },
)
```

---

## Pattern 5: Exception Handling

Map domain exceptions to proper HTTP status codes.

```python
from svc_infra.api.fastapi import router_from_object, map_exception_to_http


# Define domain-specific exceptions
class InsufficientFundsError(Exception):
    """Raised when account has insufficient funds."""
    pass


class AccountLockedError(Exception):
    """Raised when account is locked."""
    pass


class TransactionLimitError(Exception):
    """Raised when transaction exceeds limits."""
    pass


# Custom exception mapping
BANKING_EXCEPTIONS = {
    InsufficientFundsError: 400,  # Bad Request
    AccountLockedError: 403,       # Forbidden
    TransactionLimitError: 422,    # Unprocessable Entity
}


class BankingService:
    """Banking operations with domain exceptions."""

    def withdraw(self, account_id: str, amount: float) -> dict:
        """Withdraw funds from an account."""
        # These exceptions map to proper HTTP codes
        if amount > 10000:
            raise TransactionLimitError("Withdrawal exceeds daily limit")
        if amount > 5000:  # Simulating insufficient funds
            raise InsufficientFundsError("Insufficient funds")

        return {"status": "completed", "amount": amount}


# Router with custom exception handlers
router = router_from_object(
    BankingService(),
    prefix="/banking",
    exception_handlers=BANKING_EXCEPTIONS,
)

# Response on InsufficientFundsError:
# HTTP 400: {"title": "Validation Error", "detail": "Insufficient funds"}

# Response on AccountLockedError:
# HTTP 403: {"title": "Forbidden", "detail": "Account is locked"}
```

### Using map_exception_to_http Directly

```python
from svc_infra.api.fastapi import map_exception_to_http, DEFAULT_EXCEPTION_MAP

# Use in custom error handlers
try:
    process_transaction()
except Exception as e:
    status, title, detail = map_exception_to_http(e, BANKING_EXCEPTIONS)
    # status=400, title="Validation Error", detail="Insufficient funds"
```

---

## Pattern 6: Authentication

Control which endpoints require authentication.

```python
from fastapi import FastAPI
from svc_infra.api.fastapi import router_from_object


class PublicService:
    """Public endpoints (no auth)."""

    def get_status(self) -> dict:
        """Get system status (public)."""
        return {"status": "operational"}

    def list_products(self) -> list[dict]:
        """List available products (public)."""
        return [{"id": "P1", "name": "Widget"}]


class PrivateService:
    """Protected endpoints (auth required)."""

    def get_profile(self) -> dict:
        """Get current user profile."""
        return {"name": "Alice", "email": "alice@example.com"}

    def update_settings(self, notifications: bool = True) -> dict:
        """Update user settings."""
        return {"notifications": notifications}


app = FastAPI()

# Public router - no authentication
app.include_router(
    router_from_object(
        PublicService(),
        prefix="/public",
        auth_required=False,
    )
)

# Protected router - requires JWT token
app.include_router(
    router_from_object(
        PrivateService(),
        prefix="/api/v1",
        auth_required=True,  # Uses svc-infra user_router
    )
)

# /public/status       - No auth required
# /public/products     - No auth required
# /api/v1/profile      - Requires Authorization: Bearer <token>
# /api/v1/settings     - Requires Authorization: Bearer <token>
```

---

## Pattern 7: WebSocket Endpoints

Add real-time streaming alongside REST endpoints.

```python
import asyncio
from svc_infra.api.fastapi import (
    router_from_object,
    router_from_object_with_websocket,
    websocket_endpoint,
)


class StreamingService:
    """Service with both REST and WebSocket endpoints."""

    def get_current_price(self, symbol: str) -> float:
        """Get current price (REST endpoint)."""
        return 150.25

    def list_symbols(self) -> list[str]:
        """List available symbols (REST endpoint)."""
        return ["AAPL", "GOOGL", "MSFT"]

    @websocket_endpoint(path="/prices/stream")
    async def stream_prices(self, symbols: list[str]):
        """Stream real-time price updates (WebSocket).

        Yields price updates every second.
        """
        while True:
            for symbol in symbols:
                yield {"symbol": symbol, "price": 150.25 + (hash(symbol) % 10)}
            await asyncio.sleep(1.0)


# Create combined router with REST + WebSocket
router = router_from_object_with_websocket(
    StreamingService(),
    prefix="/market",
)

# REST endpoints:
# GET /market/current-price?symbol=AAPL -> 150.25
# GET /market/symbols                    -> ["AAPL", ...]

# WebSocket endpoint:
# WS /market/prices/stream
# Connect and receive: {"symbol": "AAPL", "price": 152.25}
```

---

## Pattern 8: Domain Package Integration

How domain packages like fin-infra or robo-infra should wrap the utility.

```python
# In fin-infra/src/fin_infra/integrations/svc_infra.py

from svc_infra.api.fastapi import (
    router_from_object,
    endpoint_exclude,
    map_exception_to_http,
    DEFAULT_EXCEPTION_MAP,
)

# Re-export for convenience
__all__ = [
    "router_from_object",
    "endpoint_exclude",
    "map_exception_to_http",
    "DEFAULT_EXCEPTION_MAP",
    "FIN_EXCEPTION_MAP",
    "portfolio_to_router",
]

# Domain-specific exception mapping
FIN_EXCEPTION_MAP = {
    **DEFAULT_EXCEPTION_MAP,
    InsufficientFundsError: 400,
    InvalidAccountError: 404,
    TransactionLimitError: 422,
    ComplianceBlockError: 403,
}


def portfolio_to_router(
    portfolio_service,
    *,
    prefix: str = "/portfolio",
    auth_required: bool = True,
):
    """Create a router from a portfolio service.

    Domain-specific wrapper that:
    - Sets appropriate tags
    - Configures financial exception mapping
    - Enforces authentication by default

    Args:
        portfolio_service: Portfolio service instance
        prefix: URL prefix (default: /portfolio)
        auth_required: Require JWT auth (default: True)

    Returns:
        FastAPI router with portfolio endpoints
    """
    return router_from_object(
        portfolio_service,
        prefix=prefix,
        tags=["Portfolio", "Finance"],
        auth_required=auth_required,
        exception_handlers=FIN_EXCEPTION_MAP,
    )
```

Usage:

```python
from fin_infra.integrations.svc_infra import portfolio_to_router

app.include_router(
    portfolio_to_router(my_portfolio_service)
)
```

---

## Best Practices

### 1. Use Pydantic for Complex Types

```python
from pydantic import BaseModel


class OrderRequest(BaseModel):
    items: list[str]
    quantity: int
    notes: str | None = None


class Order(BaseModel):
    id: str
    items: list[str]
    status: str


class OrderService:
    # ❌ Dict in, dict out - poor OpenAPI schema
    def create_order_bad(self, data: dict) -> dict:
        ...

    # ✅ Pydantic models - great OpenAPI schema
    def create_order(self, items: list[str], quantity: int) -> Order:
        ...
```

### 2. Name Methods for Correct Verb Inference

```python
class Service:
    # ✅ GET - reading data
    def get_user(self, user_id: str): ...
    def list_orders(self): ...
    def fetch_metrics(self): ...

    # ✅ POST - creating resources
    def create_order(self, items: list[str]): ...
    def add_item(self, item: str): ...

    # ✅ PUT - full updates
    def update_user(self, user_id: str, name: str): ...

    # ✅ DELETE - removing resources
    def delete_order(self, order_id: str): ...
    def remove_item(self, item_id: str): ...

    # ✅ POST - actions (default)
    def process_payment(self): ...
    def send_notification(self): ...
```

### 3. Document for OpenAPI

```python
class Service:
    def create_order(
        self,
        items: list[str],
        priority: str = "normal",
    ) -> Order:
        """Create a new order in the system.

        Creates an order with the specified items and priority level.
        The order starts in 'pending' status.

        Args:
            items: List of item SKUs to include in the order.
            priority: Order priority - 'low', 'normal', or 'high'.

        Returns:
            The created Order with generated ID and status.

        Raises:
            ValueError: If items list is empty.
            KeyError: If any item SKU is invalid.
        """
        ...
```

### 4. Use endpoint_exclude for Internal Methods

```python
from svc_infra.api.fastapi import endpoint_exclude


class Service:
    def public_action(self) -> str:
        """This becomes an endpoint."""
        return self._do_work()

    @endpoint_exclude
    def _do_work(self) -> str:
        """Internal helper - not exposed."""
        return "internal"

    @endpoint_exclude
    def admin_only_action(self) -> str:
        """Explicitly excluded from router."""
        return "admin"
```

### 5. Configure Exception Handlers

```python
# Define all domain exceptions
DOMAIN_EXCEPTIONS = {
    ResourceNotFoundError: 404,
    ValidationError: 400,
    PermissionDeniedError: 403,
    RateLimitError: 429,
    ServiceUnavailableError: 503,
}

router = router_from_object(
    service,
    exception_handlers=DOMAIN_EXCEPTIONS,
)
```

---

## See Also

- [Object Router Reference](object-router.md) — Complete API documentation
- [FastAPI Integration](api.md) — svc-infra FastAPI utilities
- [ai-infra Integration Patterns](../../ai-infra/docs/integration-patterns.md) — AI tools patterns
