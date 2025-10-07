from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, Request
from starlette.responses import JSONResponse

from svc_infra.apf_payments.schemas import (
    CustomerOut,
    CustomerUpsertIn,
    IntentCreateIn,
    IntentOut,
    RefundIn,
    StatementRow,
    TransactionRow,
)
from svc_infra.apf_payments.service import PaymentsService
from svc_infra.api.fastapi.auth.security import RequireIdentity, RequireService, RequireUser
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep
from svc_infra.api.fastapi.dual.router import DualAPIRouter
from svc_infra.api.fastapi.openapi.apply import apply_default_responses, apply_default_security
from svc_infra.api.fastapi.openapi.responses import (
    DEFAULT_PROTECTED,
    DEFAULT_PUBLIC,
    DEFAULT_SERVICE,
    DEFAULT_USER,
)


# --- deps ---
async def get_service(session: SqlSessionDep) -> PaymentsService:
    return PaymentsService(session=session)


# --- router helpers using your DX conventions ---
def _user_router(**kw) -> DualAPIRouter:
    r = DualAPIRouter(dependencies=[RequireUser()], **kw)
    apply_default_security(
        r, default_security=[{"OAuth2PasswordBearer": []}, {"SessionCookie": []}]
    )
    apply_default_responses(r, DEFAULT_USER)
    return r


def _protected_router(**kw) -> DualAPIRouter:
    r = DualAPIRouter(dependencies=[RequireIdentity], **kw)
    apply_default_security(
        r,
        default_security=[
            {"OAuth2PasswordBearer": []},
            {"SessionCookie": []},
            {"APIKeyHeader": []},
        ],
    )
    apply_default_responses(r, DEFAULT_PROTECTED)
    return r


def _service_router(**kw) -> DualAPIRouter:
    r = DualAPIRouter(dependencies=[RequireService()], **kw)
    apply_default_security(r, default_security=[{"APIKeyHeader": []}])
    apply_default_responses(r, DEFAULT_SERVICE)
    return r


def _public_router(**kw) -> DualAPIRouter:
    r = DualAPIRouter(**kw)
    apply_default_security(r, default_security=[])  # lock icon off
    apply_default_responses(r, DEFAULT_PUBLIC)
    return r


# --- routers grouped by auth posture (same prefix is fine; FastAPI merges) ---
def build_payments_routers(prefix: str = "/payments") -> list[DualAPIRouter]:
    routers: list[DualAPIRouter] = []

    # USER endpoints (require logged-in user)
    user = _user_router(prefix=prefix, tags=["payments"])

    @user.post("/customers", response_model=CustomerOut, name="payments_upsert_customer")
    async def upsert_customer(data: CustomerUpsertIn, svc: PaymentsService = Depends(get_service)):
        # Prefer identity user id if caller didn't set it
        if not data.user_id:
            # RequireUser ensures a principal with .user exists; pull id in your project’s user model
            # If your user id type differs, coerce as needed
            # no direct dependency exposure here; your RequireUser already validated
            pass
        out = await svc.ensure_customer(data)
        await svc.session.flush()
        return out

    @user.post("/intents", response_model=IntentOut, name="payments_create_intent")
    async def create_intent(
        data: IntentCreateIn, svc: PaymentsService = Depends(get_service), req: Request = None
    ):
        # Best-effort: user id from RequireUser principal on request.state if you stash it there.
        # If your RequireUser returns a Principal via dependency, you can inject it and read .user.id
        user_id = getattr(getattr(req, "principal", None), "user", None)
        user_id = str(getattr(user_id, "id", "")) if user_id else None
        out = await svc.create_intent(user_id=user_id, data=data)
        await svc.session.flush()
        return out

    routers.append(user)

    # PROTECTED endpoints (user OR api key)
    prot = _protected_router(prefix=prefix, tags=["payments"])

    @prot.post(
        "/intents/{provider_intent_id}/confirm",
        response_model=IntentOut,
        name="payments_confirm_intent",
    )
    async def confirm_intent(provider_intent_id: str, svc: PaymentsService = Depends(get_service)):
        out = await svc.confirm_intent(provider_intent_id)
        await svc.session.flush()
        return out

    @prot.post(
        "/intents/{provider_intent_id}/cancel",
        response_model=IntentOut,
        name="payments_cancel_intent",
    )
    async def cancel_intent(provider_intent_id: str, svc: PaymentsService = Depends(get_service)):
        out = await svc.cancel_intent(provider_intent_id)
        await svc.session.flush()
        return out

    @prot.post(
        "/intents/{provider_intent_id}/refund",
        response_model=IntentOut,
        name="payments_refund_intent",
    )
    async def refund_intent(
        provider_intent_id: str, data: RefundIn, svc: PaymentsService = Depends(get_service)
    ):
        out = await svc.refund(provider_intent_id, data)
        await svc.session.flush()
        return out

    @prot.get(
        "/transactions", response_model=list[TransactionRow], name="payments_list_transactions"
    )
    async def list_transactions(svc: PaymentsService = Depends(get_service)):
        from sqlalchemy import select

        from svc_infra.apf_payments.models import LedgerEntry

        rows = (await svc.session.execute(select(LedgerEntry))).scalars().all()
        return [
            TransactionRow(
                id=e.id,
                ts=e.ts.isoformat(),
                type="payment",
                amount=e.amount,
                currency=e.currency,
                status="posted",
                provider=e.provider,
                provider_ref=e.provider_ref or "",
                user_id=e.user_id,
            )
            for e in rows
        ]

    routers.append(prot)

    # SERVICE endpoints (api key only)
    svc_router = _service_router(prefix=prefix, tags=["payments"])

    @svc_router.get(
        "/statements/daily", response_model=list[StatementRow], name="payments_daily_statements"
    )
    async def daily_statements():
        # Implement rollups later
        return []

    routers.append(svc_router)

    # PUBLIC webhooks
    pub = _public_router(prefix=prefix, tags=["payments"])

    @pub.post("/webhooks/{provider}", name="payments_webhook")
    async def webhooks(
        provider: str,
        request: Request,
        svc: PaymentsService = Depends(get_service),
        signature: Optional[str] = Header(None, alias="Stripe-Signature"),
    ):
        payload = await request.body()
        out = await svc.handle_webhook(provider.lower(), signature, payload)
        await svc.session.flush()
        return JSONResponse(out)

    routers.append(pub)
    return routers
