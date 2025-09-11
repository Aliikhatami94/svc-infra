from typing import Any, Callable, Optional

from svc_infra.db.sql.service import SqlService

PreHook = Callable[[dict[str, Any]], dict[str, Any]]


class SqlServiceWithHooks(SqlService):
    def __init__(
        self,
        repo,
        pre_create: Optional[PreHook] = None,
        pre_update: Optional[PreHook] = None,
    ):
        super().__init__(repo)
        self._pre_create = pre_create
        self._pre_update = pre_update

    async def pre_create(self, data: dict[str, Any]) -> dict[str, Any]:
        return self._pre_create(data) if self._pre_create else data

    async def pre_update(self, data: dict[str, Any]) -> dict[str, Any]:
        return self._pre_update(data) if self._pre_update else data
