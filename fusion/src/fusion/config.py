"""Runtime configuration for the fusion container.

All settings sourced via pydantic-settings (env vars / .env file).
No os.environ.get() calls anywhere in this module — Rule 8.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FUSION_", env_file=".env", extra="ignore")

    event_store_url: str = "http://event-store:8000"
    vehicle_id: str = "OBB-TEST"
    schema_version: int = 1

    host: str = "0.0.0.0"
    port: int = 8090

    # R4: ACCESSIBILITY_DETECTED → RAMP_DEPLOYED correlation TTL (seconds).
    accessibility_recent_window_s: float = 60.0

    # ADR-15: camera is authoritative. APC drift > threshold logs WARNING only.
    calibration_drift_threshold: float = 0.10

    # ADR-2 / EventEnvelope placeholder until vlan-pollers pushes a real journey_id.
    journey_id: str = "OBB-TEST_unknown_19700101"
