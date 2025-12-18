from __future__ import annotations

from typing import Any

from bson import ObjectId
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema


class PyObjectId(ObjectId):
    """Pydantic v2-compatible ObjectId type."""

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: Any, _handler: GetCoreSchemaHandler):
        def validate(v: Any) -> ObjectId:
            if isinstance(v, ObjectId):
                return v
            if isinstance(v, str):
                try:
                    return ObjectId(v)
                except Exception as e:
                    raise ValueError(f"Invalid ObjectId: {v}") from e
            raise ValueError("ObjectId required")

        return core_schema.no_info_after_validator_function(validate, core_schema.any_schema())
