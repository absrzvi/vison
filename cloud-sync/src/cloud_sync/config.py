"""Runtime configuration for the cloud-sync container.

All settings sourced via pydantic-settings (env vars / .env file).
No os.environ.get() calls anywhere in this module — Rule 8.

Empty / whitespace-only secret coercion (code-review 2026-05-20):
  Any of the three secret fields, if set to an empty or whitespace-only
  string, are normalised to ``None`` at config-load time. Closes the Docker
  compose placeholder footgun where ``CLOUD_SYNC_MQTT_PASSWORD=`` or
  ``CLOUD_SYNC_MQTT_PASSWORD="   "`` would otherwise look "configured" but
  authenticate against the broker with garbage.

Positive-int constraints on ``publish_rate_per_sec`` and ``pull_batch_size``
prevent zero/negative values from crashing the lifespan (TokenBucket
raises ValueError on rate <= 0) or burning DEFAULT_RETRY budget on a
permanent 422 from event-store.
"""
from __future__ import annotations

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CLOUD_SYNC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Upstream event-store (HTTP)
    event_store_url: str = "http://event-store:8001"
    event_store_api_key: SecretStr | None = None

    # Landside Mosquitto broker
    mqtt_host: str = "mosquitto.landside.local"
    mqtt_port: int = 1883
    mqtt_username: SecretStr | None = None
    mqtt_password: SecretStr | None = None
    mqtt_topic_prefix: str = "oebb/events"

    # Local queue
    queue_db_path: str = "/var/lib/cloud-sync/queue.db"

    # HTTP /health
    host: str = "0.0.0.0"
    port: int = 8082

    # Loop behavior — Field constraints guard against config typos.
    pull_batch_size: int = Field(default=200, ge=1, le=500)
    pull_poll_interval_s: float = Field(default=1.0, gt=0)
    publish_rate_per_sec: int = Field(default=500, gt=0)
    ack_interval_s: float = Field(default=30.0, gt=0)

    @field_validator(
        "event_store_api_key", "mqtt_username", "mqtt_password", mode="after"
    )
    @classmethod
    def _coerce_empty_to_none(cls, v: SecretStr | None) -> SecretStr | None:
        """Empty / whitespace-only secret → None (code-review 2026-05-20 patch)."""
        if v is None:
            return None
        value = v.get_secret_value()
        if value == "" or value.strip() == "":
            return None
        return v
