from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "TaskNow API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite+aiosqlite:///./tasknow.db"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    create_tables_on_startup: bool = True
    secret_key: str = "change-this-secret-key-for-local-development"
    access_token_expire_minutes: int = 60 * 24
    jwt_algorithm: str = "HS256"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
