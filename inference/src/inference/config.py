"""Runtime configuration for the inference container.

All settings sourced via pydantic-settings (env vars / .env file).
No os.environ.get() calls anywhere in this module — Rule 8.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFERENCE_", env_file=".env", extra="ignore")

    cameras_json_path: str = "cameras.json"
    event_store_url: str = "http://event-store:8000"
    context_push_port: int = 8081

    occupancy_threshold_pct: float = 0.80
    occupancy_capacity_default: int = 200

    tops_total: float = 26.0
    tops_budget_pct_threshold: float = 0.90

    detection_classes: list[str] = ["person", "suitcase", "bicycle"]
    model_hef_path: str = "/models/yolov8m.hef"

    journey_id: str = "unknown"
    vehicle_id: str = "OBB-TEST"
    schema_version: int = 1
