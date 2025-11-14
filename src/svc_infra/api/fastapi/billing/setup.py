from __future__ import annotations

from fastapi import FastAPI

from .router import router as billing_router


def add_billing(app: FastAPI, *, prefix: str = "/_billing") -> None:
    # Register scoped docs for _billing prefix (only once)
    if not getattr(app.state, "_billing_docs_registered", False):
        from svc_infra.api.fastapi.docs.scoped import add_prefixed_docs

        add_prefixed_docs(
            app, prefix="/_billing", title="Billing & Usage", auto_exclude_from_root=True
        )
        app.state._billing_docs_registered = True

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
