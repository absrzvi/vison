"""Runtime configuration for the cloud-sync container.

All settings sourced via pydantic-settings (env vars / .env file).
No os.environ.get() calls anywhere in this module — Rule 8.

Empty-string secret coercion (inherited from event-store 4-7 code-review
patch): any of the three secret fields, if set to an empty string, are
normalised to ``None`` at config-load time. This prevents the Docker-compose
default-placeholder footgun where ``CLOUD_SYNC_MQTT_PASSWORD=`` would
otherwise look "configured" but authenticate with an empty string.
"""
from __future__ import annotations

from pydantic import SecretStr, field_validator
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

    # Loop behavior
    pull_batch_size: int = 200
    pull_poll_interval_s: float = 1.0
    publish_rate_per_sec: int = 500
    ack_interval_s: float = 30.0
    truncate_retain_journeys: int = 3

    @field_validator(
        "event_store_api_key", "mqtt_username", "mqtt_password", mode="after"
    )
    @classmethod
    def _coerce_empty_to_none(cls, v: SecretStr | None) -> SecretStr | None:
        """Empty-string secret → None. Inherited from event-store 4-7 patch."""
        if v is None:
            return None
        if v.get_secret_value() == "":
            return None
        return v
