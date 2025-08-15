from pydantic import BaseModel


class ApiConfig(BaseModel):
    version: str = "/v0"
    routers_path: str | None = None
    cors_origins: list[str] | None = None