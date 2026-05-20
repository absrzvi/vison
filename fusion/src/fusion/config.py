"""Runtime configuration for the fusion container.

All settings sourced via pydantic-settings (env vars / .env file).
No os.environ.get() calls anywhere in this module — Rule 8.

``Settings.journey_id`` was deliberately REMOVED in code-review patch
(2026-05-20 decision against synthetic placeholders in real envelopes). The
envelope journey_id comes from ``ContextState.journey_id`` only — when that
is ``None``, emits are skipped with a WARN log.
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
