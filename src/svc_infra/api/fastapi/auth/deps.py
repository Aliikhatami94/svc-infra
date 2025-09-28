from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request

from svc_infra.api.fastapi.auth.security import (
    Principal,
    resolve_api_key,
    resolve_bearer_or_cookie_principal,
)
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep


async def _current_principal(
    request: Request,
    session: SqlSessionDep,
    jwt_or_cookie: Optional[Principal] = Depends(resolve_bearer_or_cookie_principal),
    ak: Optional[Principal] = Depends(resolve_api_key),
) -> Principal:
    if jwt_or_cookie:
        return jwt_or_cookie
    if ak:
        return ak
    raise HTTPException(401, "Missing credentials")


async def _optional_principal(
    request: Request,
    session: SqlSessionDep,
    jwt_or_cookie: Optional[Principal] = Depends(resolve_bearer_or_cookie_principal),
    ak: Optional[Principal] = Depends(resolve_api_key),
) -> Optional[Principal]:
    return jwt_or_cookie or ak or None


# ---------- DX: types for endpoint params ----------
Identity = Annotated[Principal, Depends(_current_principal)]
OptionalIdentity = Annotated[Principal | None, Depends(_optional_principal)]

# ---------- DX: constants for router-level dependencies ----------
RequireIdentity = Depends(_current_principal)  # use inside router dependencies=[...]
AllowIdentity = Depends(_optional_principal)  # same, but optional
