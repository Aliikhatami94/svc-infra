from __future__ import annotations

from pydantic import BaseModel


class DocumentBase(BaseModel):
    """Marker base for Pydantic document models used for auto schema derivation."""

    model_config = {"from_attributes": True}
