from __future__ import annotations

from typing import Optional, Tuple

from sqlalchemy import ForeignKeyConstraint
from sqlalchemy.sql.type_api import TypeEngine

from svc_infra.db.sql.base import ModelBase
from svc_infra.db.sql.types import GUID


def _find_auth_mapper() -> Optional[Tuple[str, TypeEngine, str]]:
    """
    Returns (table_name, pk_sqlatype, pk_name) for the auth user model.
    Looks for any mapped class with __svc_infra_auth_user__ = True that
    is already registered on ModelBase.registry (your env imports handle this).
    """
    try:
        for mapper in list(ModelBase.registry.mappers):
            cls = mapper.class_
            if getattr(cls, "__svc_infra_auth_user__", False):
                table = mapper.local_table or getattr(cls, "__table__", None)
                if table is None:
                    continue
                pk_cols = list(table.primary_key.columns)
                if len(pk_cols) != 1:
                    continue  # require single-column PK
                pk_col = pk_cols[0]
                return (table.name, pk_col.type, pk_col.name)
    except Exception:
        pass
    return None


def resolve_auth_table_pk() -> Tuple[str, TypeEngine, str]:
    """
    Single source of truth for the auth table and PK.
    Falls back to ('users', GUID(), 'id') if nothing is marked.
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
    return pk_type


def user_fk_constraint(
    column_name: str = "user_id", *, ondelete: str = "SET NULL"
) -> ForeignKeyConstraint:
    """
    Returns a table-level ForeignKeyConstraint([...], [<auth_table>.<pk>]) for the given column.
    """
    table, _pk_type, pk_name = resolve_auth_table_pk()
    return ForeignKeyConstraint([column_name], [f"{table}.{pk_name}"], ondelete=ondelete)
