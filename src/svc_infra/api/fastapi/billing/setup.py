from __future__ import annotations

from fastapi import FastAPI

from .router import router as billing_router


def add_billing(app: FastAPI, *, prefix: str = "/_billing") -> None:
    # Mount under the chosen prefix; default is /_billing
    if prefix and prefix != "/_billing":
        # If a custom prefix is desired, clone router with new prefix
        from fastapi import APIRouter

        custom = APIRouter(prefix=prefix, tags=["Billing"])
        for route in billing_router.routes:
            custom.routes.append(route)
        app.include_router(custom)
    else:
        app.include_router(billing_router)
