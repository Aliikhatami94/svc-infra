from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from svc_infra.api.fastapi.auth.security import current_principal
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep
from svc_infra.api.fastapi.dual.protected import user_router
from svc_infra.db.sql.apikey import get_apikey_model


class ApiKeyCreateIn(BaseModel):
    name: str
    user_id: Optional[str] = None
    scopes: List[str] = Field(default_factory=list)
    ttl_hours: Optional[int] = 24 * 365  # default 1y


class ApiKeyOut(BaseModel):
    id: str
    name: str
    user_id: Optional[str]
    key: Optional[str] = None
    key_prefix: str
    scopes: List[str]
    active: bool
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]


def apikey_router(prefix: str = "/auth/keys"):
    r = user_router(prefix=prefix, tags=["auth:apikeys"])
    ApiKey = get_apikey_model()

    @r.post("", response_model=ApiKeyOut)
    async def create_key(
        sess: SqlSessionDep, payload: ApiKeyCreateIn, p=Depends(current_principal)
    ):
        owner_id = payload.user_id or getattr(p.user, "id", None)
        if owner_id != getattr(p.user, "id") and not getattr(p.user, "is_superuser", False):
            raise HTTPException(403, "forbidden")
        plaintext, prefix, hashed = ApiKey.make_secret()
        expires = (
            (datetime.now(timezone.utc) + timedelta(hours=payload.ttl_hours))
            if payload.ttl_hours
            else None
        )
        row = ApiKey(
            user_id=owner_id,
            name=payload.name,
            key_prefix=prefix,
            key_hash=hashed,
            scopes=payload.scopes,
            active=True,
            expires_at=expires,
        )
        sess.add(row)
        await sess.flush()
        return ApiKeyOut(
            id=str(row.id),
            name=row.name,
            user_id=str(row.user_id) if row.user_id else None,
            key=plaintext,  # show once
            key_prefix=row.key_prefix,
            scopes=row.scopes,
            active=row.active,
            expires_at=row.expires_at,
            last_used_at=row.last_used_at,
        )

    @r.get("", response_model=list[ApiKeyOut])
    async def list_keys(sess: SqlSessionDep, p=Depends(current_principal)):
        q = select(ApiKey)
        if not getattr(p.user, "is_superuser", False):
            q = q.where(ApiKey.user_id == p.user.id)
        rows = (await sess.execute(q)).scalars().all()
        return [
            ApiKeyOut(
                id=str(x.id),
                name=x.name,
                user_id=str(x.user_id) if x.user_id else None,
                key=None,
                key_prefix=x.key_prefix,
                scopes=x.scopes,
                active=x.active,
                expires_at=x.expires_at,
                last_used_at=x.last_used_at,
            )
            for x in rows
        ]

    @r.post("/{key_id}/revoke")
    async def revoke_key(key_id: str, sess: SqlSessionDep, p=Depends(current_principal)):
        if not getattr(p.user, "is_superuser", False):
            raise HTTPException(403, "forbidden")
        row = await sess.get(ApiKey, key_id)
        if not row:
            raise HTTPException(404, "not_found")
        if row.user_id != getattr(p.user, "id", None) and not getattr(
            p.user, "is_superuser", False
        ):
            raise HTTPException(403, "forbidden")
        row.active = False
        await sess.commit()
        return {"ok": True}

    return r
