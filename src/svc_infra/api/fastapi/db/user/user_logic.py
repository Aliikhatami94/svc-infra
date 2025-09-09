from typing import Any, Dict
from fastapi_users.password import PasswordHelper

_pwd = PasswordHelper()

def user_pre_create(data: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(data)
    if "password" in data:
        data["password_hash"] = _pwd.hash(data.pop("password"))
    if "metadata" in data:
        data["extra"] = data.pop("metadata")
    data.setdefault("roles", [])
    return data

def user_pre_update(data: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(data)
    if "password" in data:
        data["password_hash"] = _pwd.hash(data.pop("password"))
    if "metadata" in data:
        data["extra"] = data.pop("metadata")
    return data