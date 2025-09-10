from typing import Optional, Sequence


class MongoResource:
    def __init__(
        self,
        *,
        collection: str,
        read_schema,
        create_schema,
        update_schema,
        search_fields: Optional[Sequence[str]] = None,
        prefix: str,
        tags: list[str] | None = None,
    ):
        self.collection = collection
        self.read_schema = read_schema
        self.create_schema = create_schema
        self.update_schema = update_schema
        self.search_fields = search_fields
        self.prefix = prefix
        self.tags = tags
