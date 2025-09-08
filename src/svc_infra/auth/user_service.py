from typing import Any, Dict
from fastapi_users.password import PasswordHelper

from svc_infra.api.fastapi.db.service_hooks import ServiceWithHooks
from svc_infra.api.fastapi.db.repository import Repository

_pwd = PasswordHelper()

def _user_pre_create(data: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(data)  # don’t mutate caller’s dict
    # map payload fields -> model columns
    if "password" in data:
        data["password_hash"] = _pwd.hash(data.pop("password"))
    if "metadata" in data:          # pydantic uses alias "metadata" for model column "extra"
        data["extra"] = data.pop("metadata")
    # roles default if missing
    data.setdefault("roles", [])
    # booleans default come from model; fine to ignore if absent
    return data

def _user_pre_update(data: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(data)
    # allow password change via generic update too (optional)
    if "password" in data:
        data["password_hash"] = _pwd.hash(data.pop("password"))
    if "metadata" in data:
        data["extra"] = data.pop("metadata")
    return data

def make_user_service(repo: Repository):
    return ServiceWithHooks(repo, pre_create=_user_pre_create, pre_update=_user_pre_update)