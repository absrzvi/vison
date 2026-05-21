"""Runtime configuration for the fusion container.

All settings sourced via pydantic-settings (env vars / .env file).
No os.environ.get() calls anywhere in this module — Rule 8.

``Settings.journey_id`` was deliberately REMOVED in code-review patch
(2026-05-20 decision against synthetic placeholders in real envelopes). The
envelope journey_id comes from ``ContextState.journey_id`` only — when that
is ``None``, emits are skipped with a WARN log.
"""
from __future__ import annotations

from pydantic import Field
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

    # E4-S9: closed-ledger reconciliation (ADR-17).
    # Threshold must be >= 0 — negative values silently disable drift detection
    # by making the within-threshold check unsatisfiable (review P10).
    ledger_drift_threshold: int = Field(default=3, ge=0)
    ledger_drift_bucket_size: int = Field(default=3, ge=1)
    ledger_db_path: str = "/var/lib/fusion/coach_ledger.db"
    ledger_pending_timeout_s: float = Field(default=10.0, gt=0.0)

    # E4-S10: Coach Comfort Index — emit on |Δoccupancy_pct| > threshold or
    # on station_approach false→true edge.
    comfort_index_pct_threshold: float = Field(default=0.10, ge=0.0, le=1.0)
