from __future__ import annotations

from pydantic import BaseModel


class RedisPoolConfig(BaseModel):
    max_connections: int = 50
    socket_timeout: float | None = 5.0
    socket_connect_timeout: float | None = 5.0
