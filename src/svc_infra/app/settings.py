from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel

class ApiConfig(BaseModel):
    version: str = "/v0"
    routers_path: str | None = None
    cors_origins: list[str] | None = None
    mcp_paths: list[dict] | None = None

class AppSettings(BaseSettings):
    # flat = easy env overrides
    name: str = "Service Infrastructure App"
    version: str = "0.0.1"

    model_config = SettingsConfigDict(
        env_prefix="APP_",            # APP_NAME, APP_VERSION
        extra="ignore",
    )

@lru_cache
def get_app_settings(**kwargs) -> AppSettings:
    # Only include kwargs that are not None, so defaults in AppSettings are used
    filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}
    return AppSettings(**filtered_kwargs)
