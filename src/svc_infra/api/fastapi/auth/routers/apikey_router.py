from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from svc_infra.api.fastapi.auth.security import Identity
from svc_infra.api.fastapi.db.sql.session import SqlSessionDep
from svc_infra.api.fastapi.dual.protected import user_router
from svc_infra.api.fastapi.openapi.responses import CONFLICT, NOT_FOUND
from svc_infra.api.fastapi.paths.auth import (
    CREATE_KEY_PATH,
    DELETE_KEY_PATH,
    LIST_KEYS_PATH,
    REVOKE_KEY_PATH,
)
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


def _to_uuid(val):
    return val if isinstance(val, UUID) else UUID(str(val))


def apikey_router():
    r = user_router()
    ApiKey = get_apikey_model()

    @r.post(
        CREATE_KEY_PATH,
        response_model=ApiKeyOut,
        status_code=201,
        responses={409: CONFLICT},
        description="Create a new API key. The plaintext key is shown only once, at creation time.",
    )
    async def create_key(sess: SqlSessionDep, payload: ApiKeyCreateIn, p: Identity):
        caller_id: UUID = getattr(p.user, "id")
        owner_id: UUID = _to_uuid(payload.user_id) if payload.user_id else caller_id

        if owner_id != caller_id and not getattr(p.user, "is_superuser", False):
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
            key=plaintext,  # shown once
            key_prefix=row.key_prefix,
            scopes=row.scopes,
            active=row.active,
            expires_at=row.expires_at,
            last_used_at=row.last_used_at,
        )

    @r.get(
        LIST_KEYS_PATH,
        response_model=list[ApiKeyOut],
        description="List API keys. Non-superusers see only their own keys.",
    )
    async def list_keys(sess: SqlSessionDep, p: Identity):
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

    @r.post(
        REVOKE_KEY_PATH,
        status_code=204,
        responses={404: NOT_FOUND},
        description="Revoke an API key",
    )
    async def revoke_key(key_id: str, sess: SqlSessionDep, p: Identity):
        row = await sess.get(ApiKey, key_id)
        if not row:
            raise HTTPException(404, "not_found")

        caller_id: UUID = getattr(p.user, "id")
        if not (getattr(p.user, "is_superuser", False) or row.user_id == caller_id):
            raise HTTPException(403, "forbidden")

        row.active = False
        await sess.commit()
        return  # 204

    @r.delete(
        DELETE_KEY_PATH,
        status_code=204,
        responses={404: NOT_FOUND},
        description="Delete an API key. If the key is active, you must first revoke it or pass force=true.",
    )
    async def delete_key(
        key_id: str,
        sess: SqlSessionDep,
        p: Identity,
        force: bool = Query(False, description="Allow deleting an active key if True"),
    ):
        row = await sess.get(ApiKey, key_id)
        if not row:
            return  # 204

        caller_id: UUID = getattr(p.user, "id")
        if not (getattr(p.user, "is_superuser", False) or row.user_id == caller_id):
            raise HTTPException(403, "forbidden")

        if row.active and not force and not getattr(p.user, "is_superuser", False):
            # 400 is already part of DEFAULT_USER via 422/500; if you want explicit 400 doc, add it:
            # responses={400: ref("ValidationError"), ...}
            raise HTTPException(400, "key_active; revoke first or pass force=true")

        await sess.delete(row)
        await sess.commit()
        return  # 204

    return r
