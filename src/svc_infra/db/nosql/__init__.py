from svc_infra.db.nosql.resource import MongoResource

from .repository import NoSqlRepository

__all__ = [
    "MongoResource",
    "NoSqlRepository",
]
