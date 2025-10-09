from __future__ import annotations

import importlib
import sys
from typing import Optional, Tuple

from sqlalchemy import ForeignKey
from sqlalchemy.sql.type_api import TypeEngine

from svc_infra.db.sql.base import ModelBase
from svc_infra.db.sql.types import GUID


def _best_effort_import_auth_models() -> None:
    """
    Ensure the app's auth model (marked with __svc_infra_auth_user__ = True)
    is imported so its mapper is registered. We avoid heavy filesystem scanning
    and try common module names that match the scaffold.
    """
    candidates = [
        # common scaffold locations
        "auth.models",
        "app.auth.models",
        "app.auth",  # if models are in __init__
        "models",  # monorepo/single-file pattern
    ]
    for mod in candidates:
        if mod in sys.modules:
            continue
        try:
            importlib.import_module(mod)
        except Exception:
            # ignore — Alembic env usually already imports app packages
            pass


def _find_auth_mapper() -> Optional[Tuple[str, TypeEngine, str]]:
    """
    Returns (table_name, pk_sqlatype, pk_name) for the auth user model.
    Looks for any mapped class with __svc_infra_auth_user__ = True.
    """
    _best_effort_import_auth_models()

    # Iterate over registered mappers and find the one flagged as the auth user
    try:
        for mapper in list(ModelBase.registry.mappers):
            cls = mapper.class_
            if getattr(cls, "__svc_infra_auth_user__", False):
                table = mapper.local_table or getattr(cls, "__table__", None)
                if table is None:
                    continue
                pk_cols = list(table.primary_key.columns)
                if len(pk_cols) != 1:
                    continue  # require a single-column PK
                pk_col = pk_cols[0]
                return (table.name, pk_col.type, pk_col.name)
    except Exception:
        pass
    return None


def resolve_auth_table_pk() -> Tuple[str, TypeEngine, str]:
    """
    Single source of truth for the auth table and PK.
    If no annotated auth model is found, we fall back to ('users', GUID(), 'id').
    """
    found = _find_auth_mapper()
    if found is not None:
        return found
    return ("users", GUID(), "id")


def user_id_type() -> TypeEngine:
    """
    Returns a SQLAlchemy TypeEngine matching the auth user PK type.
    """
    _, pk_type, _ = resolve_auth_table_pk()
    # Most SA types are fine to reuse directly; if your PK type is a Variant
    # that requires .copy(), you can switch to pk_type.copy() here.
    return pk_type


def user_fk(ondelete: str = "SET NULL") -> ForeignKey:
    """
    Returns a ForeignKey object pointing to <auth_table>.<pk_name>.
    """
    table, _, pk_name = resolve_auth_table_pk()
    return ForeignKey(f"{table}.{pk_name}", ondelete=ondelete)
