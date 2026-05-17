from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+asyncpg://oebb:oebb@localhost:5432/oebb"
    api_key: str = "dev-insecure-key"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8002


def get_settings() -> Settings:
    return Settings()
