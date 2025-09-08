from typing import Any, Dict
from fastapi import HTTPException
from fastapi_users.password import PasswordHelper
from sqlalchemy import func

from svc_infra.api.fastapi.db.service_hooks import ServiceWithHooks
from svc_infra.api.fastapi.db.repository import Repository

_pwd = PasswordHelper()

def make_default_user_service(repo: Repository):
    Model = repo.model  # <-- capture the actual mapped model from the repo

    def _user_pre_create(data: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(data)
        # normalize + map fields
        if "password" in data:
            data["password_hash"] = _pwd.hash(data.pop("password"))
        if "metadata" in data:
            data["extra"] = data.pop("metadata")
        data.setdefault("roles", [])

        # BEFORE insert: app-level guard (nice 409) aligned with DB uniqueness
        email = data.get("email")
        tenant_id = data.get("tenant_id")
        if email is not None:
            # case-insensitive email; scope by tenant (NULL => global)
            where = [func.lower(Model.email) == func.lower(email)]
            if hasattr(Model, "tenant_id"):
                if tenant_id is None:
                    where.append(Model.tenant_id.is_(None))
                else:
                    where.append(Model.tenant_id == tenant_id)

            async def _exists(session):
                return await repo.exists(session, where=where)

            # stash the callback so Service.create can await it (has session)
            data["_precreate_exists_check"] = _exists

        return data

    def _user_pre_update(data: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(data)
        if "password" in data:
            data["password_hash"] = _pwd.hash(data.pop("password"))
        if "metadata" in data:
            data["extra"] = data.pop("metadata")

        # Optional: also protect email change from creating dupes
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

            data["_precreate_exists_check"] = _exists  # reuse same key

        return data

    class _Svc(ServiceWithHooks):
        async def create(self, session, data):
            exists_cb = data.pop("_precreate_exists_check", None)
            if exists_cb and await exists_cb(session):
                raise HTTPException(status_code=409, detail="User with this email already exists.")
            return await super().create(session, data)

        async def update(self, session, id_value, data):
            exists_cb = data.pop("_precreate_exists_check", None)
            if exists_cb and await exists_cb(session):
                raise HTTPException(status_code=409, detail="User with this email already exists.")
            return await super().update(session, id_value, data)

    return _Svc(repo, pre_create=_user_pre_create, pre_update=_user_pre_update)