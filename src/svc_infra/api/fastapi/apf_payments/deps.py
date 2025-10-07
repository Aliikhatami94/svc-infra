from __future__ import annotations

from typing import Optional

from fastapi import Header

from svc_infra.apf_payments.service import PaymentsService
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep


async def get_service(session: SqlSessionDep, provider: Optional[str] = None) -> PaymentsService:
    return PaymentsService(session=session, provider_name=provider)


# Optional enforcement of Idempotency-Key via middleware already present.
async def IdempotencyKey(
    idem: Optional[str] = Header(None, alias="Idempotency-Key")
) -> Optional[str]:
    return idem
