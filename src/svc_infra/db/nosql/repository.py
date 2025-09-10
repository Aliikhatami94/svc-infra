from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


class NoSqlRepository:
    """
    Very small async repository for Mongo-like document stores.
    Works with Motor (AsyncIOMotorDatabase).
    """

    def __init__(self, *, collection_name: str, id_field: str = "_id"):
        self.collection_name = collection_name
        self.id_field = id_field

    async def list(
        self, db, *, limit: int = 50, offset: int = 0, filter: Optional[Dict] = None
    ) -> List[Dict]:
        cursor = db[self.collection_name].find(filter or {}).skip(offset).limit(limit)
        return [doc async for doc in cursor]

    async def count(self, db, *, filter: Optional[Dict] = None) -> int:
        return await db[self.collection_name].count_documents(filter or {})

    async def get(self, db, id_value: Any) -> Dict | None:
        return await db[self.collection_name].find_one({self.id_field: id_value})

    async def create(self, db, data: Dict[str, Any]) -> Dict[str, Any]:
        res = await db[self.collection_name].insert_one(data)
        return {**data, self.id_field: res.inserted_id}

    async def update(self, db, id_value: Any, data: Dict[str, Any]) -> Dict | None:
        await db[self.collection_name].update_one({self.id_field: id_value}, {"$set": data})
        return await self.get(db, id_value)

    async def delete(self, db, id_value: Any) -> bool:
        res = await db[self.collection_name].delete_one({self.id_field: id_value})
        return res.deleted_count > 0

    async def search(
        self, db, *, q: str, fields: Sequence[str], limit: int, offset: int
    ) -> List[Dict]:
        regex = {"$regex": q, "$options": "i"}
        or_filter = [{f: regex} for f in fields]
        cursor = db[self.collection_name].find({"$or": or_filter}).skip(offset).limit(limit)
        return [doc async for doc in cursor]

    async def exists(self, db, *, filter: Dict[str, Any]) -> bool:
        doc = await db[self.collection_name].find_one(filter, projection={self.id_field: 1})
        return doc is not None
