from typing import Any, Dict
from fastapi_users.password import PasswordHelper

from svc_infra.api.fastapi.db.repository import Repository
from svc_infra.db.uniq_hooks import dedupe_service

_pwd = PasswordHelper()

def make_default_user_service(repo: Repository):

    def _user_pre_create(data: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(data)
        if "password" in data:
            data["password_hash"] = _pwd.hash(data.pop("password"))
        if "metadata" in data:
            data["extra"] = data.pop("metadata")
        data.setdefault("roles", [])
        return data

    def _user_pre_update(data: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(data)
        if "password" in data:
            data["password_hash"] = _pwd.hash(data.pop("password"))
        if "metadata" in data:
            data["extra"] = data.pop("metadata")
        return data

    # First wrap with the general uniqueness service
    SvcUniq = dedupe_service(
        repo,
        unique_ci=["email"],
        tenant_field="tenant_id",
    )

    # Then inject your prehooks by subclassing once
    class _Svc(SvcUniq.__class__):  # keep the uniqueness behavior
        async def pre_create(self, data):  # type: ignore[override]
            return _user_pre_create(data)

        async def pre_update(self, data):  # type: ignore[override]
            return _user_pre_update(data)

    # Instantiate with the same repo
    return _Svc(repo)