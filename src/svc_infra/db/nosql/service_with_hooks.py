from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .service import NoSqlService

PreHook = Callable[[dict[str, Any]], dict[str, Any]]


class NoSqlServiceWithHooks(NoSqlService):
    def __init__(
        self,
        repo,
        pre_create: PreHook | None = None,
        pre_update: PreHook | None = None,
    ):
        super().__init__(repo)
        self._pre_create = pre_create
        self._pre_update = pre_update

    async def pre_create(self, data: dict[str, Any]) -> dict[str, Any]:
        return self._pre_create(data) if self._pre_create else data

    async def pre_update(self, data: dict[str, Any]) -> dict[str, Any]:
        return self._pre_update(data) if self._pre_update else data
