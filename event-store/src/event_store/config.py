from __future__ import annotations

from pydantic import SecretStr, field_validator
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

    # AC8: X-API-Key authentication. None = dev-mode bypass (startup WARN
    # emitted). Production: set EVENT_STORE_API_KEY env var.
    # SecretStr so the value is not accidentally rendered in logs / repr.
    api_key: SecretStr | None = None

    # Edge-anonymisation HMAC key. Salts the track_id → opaque-token map applied
    # to events leaving the train via GET /api/v1/events (the cloud-sync pull
    # path). MUST never leave the edge — the emitted tokens are not reversible
    # without it. None = dev-mode bypass: a fixed dev key is used and a startup
    # WARN is emitted (so cloud egress is still anonymised, just not secret).
    anonymise_key: SecretStr | None = None

    @field_validator("api_key", "anonymise_key", mode="after")
    @classmethod
    def _coerce_empty_to_none(cls, v: SecretStr | None) -> SecretStr | None:
        """Treat an explicitly-empty secret env var (e.g. ``EVENT_STORE_API_KEY=""``)
        as None.

        Without this, ``SecretStr("")`` would be non-None → require_api_key
        compares against an empty expected key → every client request 401s.
        That creates a "looks configured but unreachable" Docker-compose
        footgun (code-review patch 2026-05-20).
        """
        if v is None:
            return None
        if v.get_secret_value() == "":
            return None
        return v


settings = Settings()
