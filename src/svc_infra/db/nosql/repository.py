from __future__ import annotations

import builtins
from collections.abc import Iterable, Sequence
from datetime import UTC
from typing import Any, cast

try:
    from bson import ObjectId

    _HAS_BSON = True
except ModuleNotFoundError:
    # `bson` is provided by the optional `pymongo` dependency.
    # Keep imports working for non-mongo users/tests; runtime Mongo usage still
    # requires installing pymongo.
    _HAS_BSON = False

    class ObjectId:  # type: ignore[no-redef]
        pass


class NoSqlRepository:
    """
    Very small async repository for Mongo-like document stores (Motor).
    Mirrors SqlRepository capabilities:
      - list / count / get / create / update / delete
      - optional soft delete with timestamp + flag field
      - search (regex OR across fields)
      - exists(filter)
      - basic sort support (list of (field, direction) tuples: 1 or -1)
    """

    def __init__(
        self,
        *,
        collection_name: str,
        id_field: str = "_id",
        soft_delete: bool = False,
        soft_delete_field: str = "deleted_at",
        soft_delete_flag_field: str | None = None,
        immutable_fields: set[str] | None = None,
    ):
        self.collection_name = collection_name
        self.id_field = id_field
        self.soft_delete = soft_delete
        self.soft_delete_field = soft_delete_field
        self.soft_delete_flag_field = soft_delete_flag_field
        self.immutable_fields: set[str] = set(
            immutable_fields or {self.id_field, "created_at", "updated_at"}
        )

    def _alive_filter(self) -> dict[str, Any]:
        """
        Build a filter that returns 'alive' docs when soft_delete is enabled.
        - deleted_at is either null or absent
        - optional boolean flag is either True or absent
        """
        if not self.soft_delete:
            return {}

        clauses: list[dict] = []

        if self.soft_delete_field:
            # keep docs where deleted_at is None OR does not exist
            clauses.append(
                {
                    "$or": [
                        {self.soft_delete_field: None},
                        {self.soft_delete_field: {"$exists": False}},
                    ]
                }
            )

        if self.soft_delete_flag_field:
            # keep docs where flag is True OR does not exist
            clauses.append(
                {
                    "$or": [
                        {self.soft_delete_flag_field: True},
                        {self.soft_delete_flag_field: {"$exists": False}},
                    ]
                }
            )

        if not clauses:
            return {}

        return clauses[0] if len(clauses) == 1 else {"$and": clauses}

    def _merge_and(self, *filters: dict[str, Any] | None) -> dict[str, Any]:
        parts = [f for f in filters if f]
        if not parts:
            return {}
        if len(parts) == 1:
            return parts[0]
        return {"$and": parts}

    def _normalize_id_value(self, val: Any) -> Any:
        """If we use Mongo’s _id and a string is passed, coerce to ObjectId when possible."""
        if not _HAS_BSON:
            return val
        if self.id_field == "_id" and isinstance(val, str):
            try:
                return ObjectId(val)
            except Exception:
                return val
        return val

    @staticmethod
    def _public_doc(doc: dict[str, Any]) -> dict[str, Any]:
        d = dict(doc)
        if "_id" in d and "id" not in d:
            _id = d.pop("_id", None)
            if _HAS_BSON and isinstance(_id, ObjectId):
                d["id"] = str(_id)
            else:
                d["id"] = _id
        return d

    async def list(
        self,
        db,
        *,
        limit: int,
        offset: int,
        sort: builtins.list[tuple[str, int]] | None = None,
        filter: dict[str, Any] | None = None,
    ) -> builtins.list[dict[str, Any]]:
        filt = self._merge_and(self._alive_filter(), filter)
        cursor = db[self.collection_name].find(filt).skip(offset).limit(limit)
        if sort:
            cursor = cursor.sort(sort)
        return [self._public_doc(doc) async for doc in cursor]

    async def count(self, db, *, filter: dict[str, Any] | None = None) -> int:
        filt = self._merge_and(self._alive_filter(), filter)
        return cast("int", await db[self.collection_name].count_documents(filt or {}))

    async def get(self, db, id_value: Any) -> dict | None:
        id_value = self._normalize_id_value(id_value)
        filt = self._merge_and(self._alive_filter(), {self.id_field: id_value})
        doc = await db[self.collection_name].find_one(filt)
        if doc is None:
            return None
        return self._public_doc(doc)

    async def create(self, db, data: dict[str, Any]) -> dict[str, Any]:
        # don't let clients supply soft-delete artifacts on create
        if self.soft_delete:
            data.pop(self.soft_delete_field, None)
            if self.soft_delete_flag_field:
                data[self.soft_delete_flag_field] = True
        res = await db[self.collection_name].insert_one(data)
        return self._public_doc({**data, "_id": res.inserted_id})

    async def update(self, db, id_value: Any, data: dict[str, Any]) -> dict | None:
        for k in list(data.keys()):
            if k in self.immutable_fields:
                data.pop(k, None)
        id_value = self._normalize_id_value(id_value)
        filt = self._merge_and(self._alive_filter(), {self.id_field: id_value})
        await db[self.collection_name].update_one(filt, {"$set": data})
        return await self.get(db, id_value)

    async def delete(self, db, id_value: Any) -> bool:
        id_value = self._normalize_id_value(id_value)
        if self.soft_delete:
            set_ops: dict[str, Any] = {}
            if self.soft_delete_flag_field:
                set_ops[self.soft_delete_flag_field] = False
            from datetime import datetime

            set_ops[self.soft_delete_field] = datetime.now(UTC)
            res = await db[self.collection_name].update_one(
                {self.id_field: id_value}, {"$set": set_ops}
            )
            return cast("int", res.modified_count) > 0

        res = await db[self.collection_name].delete_one({self.id_field: id_value})
        return cast("int", res.deleted_count) > 0

    async def search(
        self,
        db,
        *,
        q: str,
        fields: Sequence[str],
        limit: int,
        offset: int,
        sort: builtins.list[tuple[str, int]] | None = None,
    ) -> builtins.list[dict[str, Any]]:
        regex = {"$regex": q, "$options": "i"}
        or_filter = [{"$or": [{f: regex} for f in fields]}] if fields else []
        filt = (
            self._merge_and(self._alive_filter(), *or_filter) if or_filter else self._alive_filter()
        )
        cursor = db[self.collection_name].find(filt).skip(offset).limit(limit)
        if sort:
            cursor = cursor.sort(sort)
        return [self._public_doc(doc) async for doc in cursor]

    async def count_filtered(self, db, *, q: str, fields: Sequence[str]) -> int:
        regex = {"$regex": q, "$options": "i"}
        or_filter = {"$or": [{f: regex} for f in fields]} if fields else {}
        filt = self._merge_and(self._alive_filter(), or_filter)
        return cast("int", await db[self.collection_name].count_documents(filt or {}))

    async def exists(self, db, *, where: Iterable[dict[str, Any]]) -> bool:
        filt = self._merge_and(self._alive_filter(), *list(where))
        doc = await db[self.collection_name].find_one(filt, projection={self.id_field: 1})
        return doc is not None
