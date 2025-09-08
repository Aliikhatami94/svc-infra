from typing import Any, Dict
from fastapi import HTTPException
from fastapi_users.password import PasswordHelper
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from svc_infra.api.fastapi.db.service_hooks import ServiceWithHooks
from svc_infra.api.fastapi.db.repository import Repository

_pwd = PasswordHelper()

def make_default_user_service(repo: Repository):
    Model = repo.model  # capture the mapped class

    def _user_pre_create(data: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(data)
        # normalize + map fields
        if "password" in data:
            data["password_hash"] = _pwd.hash(data.pop("password"))
        if "metadata" in data:
            data["extra"] = data.pop("metadata")
        data.setdefault("roles", [])

        # attach existence checker (case-insensitive email, tenant scoped)
        email = data.get("email")
        tenant_id = data.get("tenant_id")
        if email is not None:
            where = [func.lower(Model.email) == func.lower(email)]
            if hasattr(Model, "tenant_id"):
                if tenant_id is None:
                    where.append(Model.tenant_id.is_(None))
                else:
                    where.append(Model.tenant_id == tenant_id)

            async def _exists(session):
                return await repo.exists(session, where=where)

            data["_precreate_exists_check"] = _exists
        return data

    def _user_pre_update(data: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(data)
        if "password" in data:
            data["password_hash"] = _pwd.hash(data.pop("password"))
        if "metadata" in data:
            data["extra"] = data.pop("metadata")

        # optional: protect email change too
        email = data.get("email")
        tenant_id = data.get("tenant_id")
        if email is not None:
            where = [func.lower(Model.email) == func.lower(email)]
            if hasattr(Model, "tenant_id"):
                if tenant_id is None:
                    where.append(Model.tenant_id.is_(None))
                else:
                    where.append(Model.tenant_id == tenant_id)

            async def _exists(session):
                return await repo.exists(session, where=where)

            data["_preupdate_exists_check"] = _exists
        return data

    class _Svc(ServiceWithHooks):
        async def create(self, session, data):
            # IMPORTANT: run pre_create first
            data = await self.pre_create(data)
            exists_cb = data.pop("_precreate_exists_check", None)
            if exists_cb and await exists_cb(session):
                raise HTTPException(status_code=409, detail="User with this email already exists.")
            try:
                return await self.repo.create(session, data)
            except IntegrityError as e:
                # race-safety / fallback
                if "uq_users_tenant_id" in str(e.orig) or "ci_email" in str(e.orig):
                    raise HTTPException(status_code=409, detail="User with this email already exists.") from e
                raise

        async def update(self, session, id_value, data):
            data = await self.pre_update(data)
            exists_cb = data.pop("_preupdate_exists_check", None)
            if exists_cb and await exists_cb(session):
                raise HTTPException(status_code=409, detail="User with this email already exists.")
            try:
                return await self.repo.update(session, id_value, data)
            except IntegrityError as e:
                if "uq_users_tenant_id" in str(e.orig) or "ci_email" in str(e.orig):
                    raise HTTPException(status_code=409, detail="User with this email already exists.") from e
                raise

    return _Svc(repo, pre_create=_user_pre_create, pre_update=_user_pre_update)