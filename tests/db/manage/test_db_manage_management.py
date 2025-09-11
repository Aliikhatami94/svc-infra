from __future__ import annotations

from datetime import date, datetime

import pytest
from pydantic import BaseModel, ValidationError
from sqlalchemy import JSON, Boolean, Date, DateTime, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from svc_infra.db.sql.management import make_crud_schemas


class Base(DeclarativeBase):
    pass


class Thing(Base):
    __tablename__ = "things_mgmt"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # required, no defaults
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # nullable simple type
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # python default -> excluded from Create by heuristic
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # server default -> excluded from Create
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    # onupdate and well-known name -> excluded from Create
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True
    )
    # other types
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # explicit default value/callable -> excluded from Create
    code: Mapped[str] = mapped_column(String(10), nullable=False, default="X")
    uid: Mapped[str] = mapped_column(String(36), nullable=False, default=lambda: "gen")


def _field_names(M: type[BaseModel]) -> set[str]:
    # pydantic v2 stores fields in model_fields
    return set(M.model_fields.keys())


def test_make_crud_schemas_basic_shapes():
    Read, Create, Update = make_crud_schemas(Thing)

    # from_attributes enabled
    assert Read.model_config.get("from_attributes") is True
    assert Create.model_config.get("from_attributes") is True
    assert Update.model_config.get("from_attributes") is True

    # Read includes all columns; nullable are optional by default
    expected_read = {
        "id",
        "name",
        "description",
        "is_active",
        "created_at",
        "updated_at",
        "event_date",
        "meta",
        "code",
        "uid",
    }
    assert _field_names(Read) == expected_read

    # Create excludes pk, server/callable defaults, timestamps
    expected_create = {"name", "description", "event_date", "meta"}
    assert _field_names(Create) == expected_create

    # Behavior: name required, others optional
    with pytest.raises(ValidationError):
        Create()  # type: ignore[call-arg]
    c = Create(name="x")
    assert c.name == "x" and c.description is None and c.event_date is None and c.meta is None

    # Update has Optional[T] for all columns -> allow empty and partial
    u_empty = Update()
    assert isinstance(u_empty, Update)
    u = Update(name=None, description="new")
    assert u.description == "new"

    # validate types by instantiation on Read
    r = Read(
        id=1,
        name="n",
        description=None,
        is_active=True,
        created_at=datetime.now(),
        updated_at=None,
        event_date=None,
        meta={"a": 1},
        code="C",
        uid="U",
    )
    assert r.id == 1 and r.name == "n" and r.meta == {"a": 1}


def test_make_crud_schemas_name_overrides_and_excludes():
    Read, Create, Update = make_crud_schemas(
        Thing,
        read_name="ThingR",
        create_name="ThingC",
        update_name="ThingU",
        create_exclude=("id", "name"),  # add explicit exclude on top of heuristics
    )

    assert Read.__name__ == "ThingR"
    assert Create.__name__ == "ThingC"
    assert Update.__name__ == "ThingU"

    # name explicitly excluded from Create
    assert "name" not in _field_names(Create)
    # other previously expected Create fields still present unless heuristically excluded
    for fname in ("description", "event_date", "meta"):
        assert fname in _field_names(Create)


def test_make_crud_schemas_read_update_exclude():
    Read, Create, Update = make_crud_schemas(
        Thing,
        read_exclude=("meta", "code"),
        update_exclude=("uid",),
    )

    assert "meta" not in _field_names(Read)
    assert "code" not in _field_names(Read)

    assert "uid" not in _field_names(Update)
    # sanity: unrelated fields still present
    for f in ("name", "description", "created_at"):
        assert f in _field_names(Update)


def test_make_crud_schemas_nullable_fields():
    """Validate handling of nullable fields via runtime behavior."""
    Read, Create, Update = make_crud_schemas(Thing)

    # Create allows omitting nullable fields
    Create(name="ok")
    Create(name="ok", description=None, event_date=None, meta=None)

    # Create rejects missing non-nullable field
    with pytest.raises(ValidationError):
        Create()  # type: ignore[call-arg]

    # Update accepts empty payload and partials
    Update()
    Update(description="x")

    # Read contains all fields
    assert _field_names(Read) == {
        "id",
        "name",
        "description",
        "is_active",
        "created_at",
        "updated_at",
        "event_date",
        "meta",
        "code",
        "uid",
    }


def test_make_crud_schemas_pydantic_config():
    """Validate Pydantic config options in generated schemas."""
    Read, Create, Update = make_crud_schemas(Thing)

    assert Read.model_config.get("from_attributes") is True
    assert Create.model_config.get("from_attributes") is True
    assert Update.model_config.get("from_attributes") is True


def test_make_crud_schemas_exclude_params():
    """Validate behavior of explicit exclude parameters."""
    Read, Create, Update = make_crud_schemas(
        Thing,
        create_exclude=("id", "name"),
        update_exclude=("uid",),
    )

    assert "id" not in _field_names(Create)
    assert "name" not in _field_names(Create)
    assert "uid" not in _field_names(Update)

    # Other fields still present
    for fname in ("description", "event_date", "meta"):
        assert fname in _field_names(Create)
    for fname in ("name", "description", "created_at"):
        assert fname in _field_names(Update)
