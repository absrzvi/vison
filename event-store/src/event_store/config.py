from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    db_path: str = "/data/events.db"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8001
    cursor_page_size: int = 100


settings = Settings()
