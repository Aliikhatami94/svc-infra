from __future__ import annotations

import os

from pydantic import AnyUrl, BaseModel, Field


class MongoSettings(BaseModel):
    url: AnyUrl = Field(default_factory=lambda: os.getenv("MONGO_URL", "mongodb://localhost:27017"))
    db_name: str = Field(default_factory=lambda: os.getenv("MONGO_DB", ""))
    appname: str = Field(default_factory=lambda: os.getenv("MONGO_APPNAME", "svc-infra"))
    min_pool_size: int = int(os.getenv("MONGO_MIN_POOL", "0"))
    max_pool_size: int = int(os.getenv("MONGO_MAX_POOL", "100"))
