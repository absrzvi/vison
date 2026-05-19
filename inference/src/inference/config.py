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

    # P-D1: occupancy story tracks person only. Suitcase/bicycle/wheelchair move to E4-S5.
    detection_classes: list[str] = ["person"]
    model_hef_path: str = "/models/yolov8m.hef"

    # P-D2: service_tier sourced via env INFERENCE_SERVICE_TIER, not hardcoded.
    service_tier: str = "standard"

    # journey_id must match {vehicle_id}_{trip_number}_{YYYYMMDD} per ADR-2 / EventEnvelope.
    # Default is a syntactically-valid placeholder; production sets via vlan-pollers context push
    # once a real trip is observed (same pattern as rtsp-ingest).
    vehicle_id: str = "OBB-TEST"
    journey_id: str = "OBB-TEST_unknown_19700101"
    schema_version: int = 1
