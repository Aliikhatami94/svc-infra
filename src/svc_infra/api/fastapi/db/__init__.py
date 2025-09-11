from svc_infra.api.fastapi.db.nosql import add_mongo_db, add_mongo_health, add_mongo_resources
from svc_infra.api.fastapi.db.sql import add_sql_db, add_sql_health, add_sql_resources

__all__ = [
    # SQL
    "add_sql_health",
    "add_sql_db",
    "add_sql_resources",
    # NoSQL
    "add_mongo_resources",
    "add_mongo_db",
    "add_mongo_health",
]
