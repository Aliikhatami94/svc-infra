from __future__ import annotations
import os
from pydantic import BaseModel, Field

class MongoSettings(BaseModel):
    url: str = Field(default_factory=lambda: os.getenv("MONGO_URL", "mongodb://localhost:27017/app"))
    db_name: str = Field(default_factory=lambda: os.getenv("MONGO_DB", "app"))
    appname: str = Field(default_factory=lambda: os.getenv("MONGO_APPNAME", "svc-infra"))
    min_pool_size: int = int(os.getenv("MONGO_MIN_POOL", "0"))
    max_pool_size: int = int(os.getenv("MONGO_MAX_POOL", "100"))