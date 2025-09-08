from typing import Any, Dict
from fastapi import HTTPException
from fastapi_users.password import PasswordHelper
from sqlalchemy import func

from svc_infra.api.fastapi.db.service_hooks import ServiceWithHooks
from svc_infra.api.fastapi.db.repository import Repository

_pwd = PasswordHelper()

def _user_pre_create(data: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(data)
    # normalize + map fields
    if "password" in data:
        data["password_hash"] = _pwd.hash(data.pop("password"))
    if "metadata" in data:
        data["extra"] = data.pop("metadata")

    # BEFORE insert: application-level guard (nice error)
    # case-insensitive email; handle tenant/null logic the same way as your unique index
    email = data.get("email")
    tenant_id = data.get("tenant_id")
    if email:
        where = [func.lower(Repository.model.email) == func.lower(email)]
        if tenant_id is None:
            where.append(Repository.model.tenant_id.is_(None))
        else:
            where.append(Repository.model.tenant_id == tenant_id)

        # use a small “exists” helper on the repo if you have it
        async def _exists(session):
            return await Repository.exists(session, where=where)

        data["_precreate_exists_check"] = _exists  # stash callable for service.create to run

    return data

def _user_pre_update(data: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(data)
    if "password" in data:
        data["password_hash"] = _pwd.hash(data.pop("password"))
    if "metadata" in data:
        data["extra"] = data.pop("metadata")
    return data

def make_default_user_service(repo: Repository):
    class _Svc(ServiceWithHooks):
        async def create(self, session, data):
            exists_cb = data.pop("_precreate_exists_check", None)
            if exists_cb and await exists_cb(session):
                raise HTTPException(status_code=409, detail="User with this email already exists.")
            return await super().create(session, data)
    return _Svc(repo, pre_create=_user_pre_create, pre_update=_user_pre_update)