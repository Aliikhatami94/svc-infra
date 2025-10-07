from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, Request
from sqlalchemy import select
from starlette.responses import JSONResponse

from svc_infra.apf_payments.models import LedgerEntry  # for /transactions listing
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
from svc_infra.api.fastapi.auth.security import Identity
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep
from svc_infra.api.fastapi.dual.protected import protected_router, service_router, user_router
from svc_infra.api.fastapi.dual.public import public_router


# ---------- deps ----------
async def get_service(session: SqlSessionDep) -> PaymentsService:
    return PaymentsService(session=session)


# ---------- routers (posture-specific) ----------
def build_payments_routers(prefix: str = "/payments"):
    routers = []

    # USER-ONLY endpoints (JWT/cookie user; no API key-only)
    r_user = user_router(prefix=prefix, tags=["payments"])

    @r_user.post("/customers", response_model=CustomerOut, name="payments_upsert_customer")
    async def upsert_customer(
        data: CustomerUpsertIn,
        p: Identity,  # your Principal (guaranteed user)
        svc: PaymentsService = Depends(get_service),
    ):
        user_id = data.user_id or str(getattr(p.user, "id"))
        out = await svc.ensure_customer(data.model_copy(update={"user_id": user_id}))
        await svc.session.flush()
        return out

    @r_user.post("/intents", response_model=IntentOut, name="payments_create_intent")
    async def create_intent(
        data: IntentCreateIn,
        p: Identity,
        svc: PaymentsService = Depends(get_service),
    ):
        user_id = str(getattr(p.user, "id"))
        out = await svc.create_intent(user_id=user_id, data=data)
        await svc.session.flush()
        return out

    routers.append(r_user)

    # PROTECTED endpoints (user OR API key)
    r_prot = protected_router(prefix=prefix, tags=["payments"])

    @r_prot.post(
        "/intents/{provider_intent_id}/confirm",
        response_model=IntentOut,
        name="payments_confirm_intent",
    )
    async def confirm_intent(provider_intent_id: str, svc: PaymentsService = Depends(get_service)):
        out = await svc.confirm_intent(provider_intent_id)
        await svc.session.flush()
        return out

    @r_prot.post(
        "/intents/{provider_intent_id}/cancel",
        response_model=IntentOut,
        name="payments_cancel_intent",
    )
    async def cancel_intent(provider_intent_id: str, svc: PaymentsService = Depends(get_service)):
        out = await svc.cancel_intent(provider_intent_id)
        await svc.session.flush()
        return out

    @r_prot.post(
        "/intents/{provider_intent_id}/refund",
        response_model=IntentOut,
        name="payments_refund_intent",
    )
    async def refund_intent(
        provider_intent_id: str,
        data: RefundIn,
        svc: PaymentsService = Depends(get_service),
    ):
        out = await svc.refund(provider_intent_id, data)
        await svc.session.flush()
        return out

    @r_prot.get(
        "/transactions", response_model=list[TransactionRow], name="payments_list_transactions"
    )
    async def list_transactions(svc: PaymentsService = Depends(get_service)):
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

    routers.append(r_prot)

    # SERVICE endpoints (API key required)
    r_svc = service_router(prefix=prefix, tags=["payments"])

    @r_svc.get(
        "/statements/daily", response_model=list[StatementRow], name="payments_daily_statements"
    )
    async def daily_statements():
        # placeholder rollup; implement via SQL later
        return []

    routers.append(r_svc)

    # PUBLIC webhooks (no auth; provider verifies via signatures)
    r_pub = public_router(prefix=prefix, tags=["payments"])

    @r_pub.post("/webhooks/{provider}", name="payments_webhook")
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

    routers.append(r_pub)
    return routers
