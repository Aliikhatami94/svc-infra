from __future__ import annotations

import types
import uuid

import pytest
from fastapi import HTTPException

from svc_infra.api.fastapi.auth.security import Principal
from svc_infra.security.permissions import (
    PERMISSION_REGISTRY,
    get_permissions_for_roles,
    has_permission,
)


class DummyUser:
    def __init__(self, roles):
        self.id = uuid.uuid4()
        self.roles = roles


def make_principal(roles):
    return Principal(user=DummyUser(roles), scopes=[], via="jwt")


def test_role_permission_expansion():
    perms = get_permissions_for_roles(["admin"])  # baseline
    assert "user.read" in perms and "security.session.revoke" in perms


def test_has_permission_positive_negative():
    p = make_principal(["support"])  # support lacks user.write
    assert has_permission(p, "user.read") is True
    assert has_permission(p, "user.write") is False


def test_multiple_role_union():
    p = make_principal(["support", "auditor"])  # union of sets
    perms = get_permissions_for_roles(p.user.roles)
    assert "audit.read" in perms and "user.read" in perms
    assert "user.write" not in perms


def test_registry_extensibility():
    PERMISSION_REGISTRY.setdefault("experiment", set()).add("exp.toggle")
    p = make_principal(["experiment"])  # dynamic addition
    assert has_permission(p, "exp.toggle")
