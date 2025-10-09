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
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep
from svc_infra.api.fastapi.dual import protected_router, public_router, service_router, user_router
from svc_infra.api.fastapi.dual.router import DualAPIRouter


# --- deps ---
async def get_service(session: SqlSessionDep) -> PaymentsService:
    # No provider forced here; PaymentsService lazy-loads when needed
    return PaymentsService(session=session)


# --- routers grouped by auth posture (same prefix is fine; FastAPI merges) ---
def build_payments_routers(prefix: str = "/payments") -> list[DualAPIRouter]:
    routers: list[DualAPIRouter] = []

    # USER endpoints (require logged-in user)
    user = user_router(prefix=prefix, tags=["payments"])

    @user.post("/customers", response_model=CustomerOut, name="payments_upsert_customer")
    async def upsert_customer(data: CustomerUpsertIn, svc: PaymentsService = Depends(get_service)):
        out = await svc.ensure_customer(data)
        await svc.session.flush()
        return out

    @user.post("/intents", response_model=IntentOut, name="payments_create_intent")
    async def create_intent(data: IntentCreateIn, svc: PaymentsService = Depends(get_service)):
        # If your RequireUser principal exposes user id somewhere (e.g., request.state.principal.user.id),
        # you can plumb it here. For now, let provider/customer flows attach user_id later.
        out = await svc.create_intent(user_id=None, data=data)
        await svc.session.flush()
        return out

    routers.append(user)

    # PROTECTED endpoints (user OR api key)
    prot = protected_router(prefix=prefix, tags=["payments"])

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
                status=e.status,
                provider=e.provider,
                provider_ref=e.provider_ref or "",
                user_id=e.user_id,
            )
            for e in rows
        ]

    routers.append(prot)

    # SERVICE endpoints (api key only)
    svc_router = service_router(prefix=prefix, tags=["payments"])

    @svc_router.get(
        "/statements/daily", response_model=list[StatementRow], name="payments_daily_statements"
    )
    async def daily_statements():
        # Implement rollups later
        return []

    routers.append(svc_router)

    # PUBLIC webhooks
    pub = public_router(prefix=prefix, tags=["payments"])

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
