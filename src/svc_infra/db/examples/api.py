from __future__ import annotations

import uuid
import datetime as dt
from typing import Optional, Sequence, Annotated

from fastapi import APIRouter, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_session, get_uow
from ..uow import UnitOfWork
from .models import Widget
from pydantic import BaseModel


class WidgetIn(BaseModel):
    name: str
    description: Optional[str] = None


class WidgetOut(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    created_at: dt.datetime
    updated_at: dt.datetime

    model_config = {
        "from_attributes": True,
    }


router = APIRouter(prefix="/examples/widgets", tags=["examples-widgets"])


@router.get("", response_model=list[WidgetOut])
async def list_widgets(session: Annotated[AsyncSession, Depends(get_session)]) -> Sequence[WidgetOut]:
    res = await session.execute(select(Widget))
    items = res.scalars().all()
    return [WidgetOut.model_validate(obj) for obj in items]


@router.post("", response_model=WidgetOut, status_code=status.HTTP_201_CREATED)
async def create_widget(data: WidgetIn, uow: Annotated[UnitOfWork, Depends(get_uow)]) -> WidgetOut:
    repo = uow.repo(Widget)
    obj = await repo.create(**data.model_dump())
    return WidgetOut.model_validate(obj)
