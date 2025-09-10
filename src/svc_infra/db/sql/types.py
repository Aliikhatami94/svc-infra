from __future__ import annotations

import uuid as _uuid

from sqlalchemy.dialects import postgresql
from sqlalchemy.types import CHAR, TypeDecorator


class GUID(TypeDecorator):
    """Portable UUID.

    PG -> UUID(as_uuid=True)
    Others -> CHAR(36)
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, _uuid.UUID):
            return str(value)
        return str(_uuid.UUID(str(value)))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return _uuid.UUID(str(value))
