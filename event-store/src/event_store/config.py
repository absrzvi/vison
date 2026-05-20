from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EVENT_STORE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_path: str = "/data/events.db"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8001
    cursor_page_size: int = 100

    # AC8: X-API-Key authentication. None = dev-mode bypass (startup WARN emitted).
    # Production: set EVENT_STORE_API_KEY env var. Use SecretStr so the value is
    # not accidentally rendered in logs / repr.
    api_key: SecretStr | None = None


settings = Settings()
