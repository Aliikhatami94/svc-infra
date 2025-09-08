from typing import Any, Dict
from fastapi_users.password import PasswordHelper

from svc_infra.api.fastapi.db.service_hooks import ServiceWithHooks
from svc_infra.api.fastapi.db.repository import Repository

_pwd = PasswordHelper()

def _pre_create(data: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(data)
    if "password" in data:
        data["password_hash"] = _pwd.hash(data.pop("password"))
    if "metadata" in data:   # pydantic alias -> model column "metadata" (extra)
        data["extra"] = data.pop("metadata")
    data.setdefault("roles", [])
    return data

def _pre_update(data: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(data)
    if "password" in data:
        data["password_hash"] = _pwd.hash(data.pop("password"))
    if "metadata" in data:
        data["extra"] = data.pop("metadata")
    return data

def make_default_user_service(repo: Repository):
    return ServiceWithHooks(repo, pre_create=_pre_create, pre_update=_pre_update)