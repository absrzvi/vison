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

    # E4-S5: expanded to include suitcase (door obstruction) and bicycle (accessibility).
    detection_classes: list[str] = ["person", "suitcase", "bicycle"]
    model_hef_path: str = "/models/yolov8m.hef"

    fusion_url: str = "http://fusion:8090"
    accessibility_confidence_threshold: float = 0.80
    door_obstruction_min_frames: int = 2
    vestibule_congestion_threshold: int = 8
    vestibule_congestion_score_threshold: float = 0.75
    slip_fall_height_collapse_threshold: float = 0.5
    slip_fall_velocity_threshold: float = 50.0
    pipeline_fps: float = 3.0

    # P-D2: service_tier sourced via env INFERENCE_SERVICE_TIER, not hardcoded.
    service_tier: str = "standard"

    # P-M10: symmetric count-based deadband on threshold crossings (party-mode verdict).
    # rising fires when count crosses threshold+deadband; falling at threshold-deadband.
    occupancy_deadband_count: int = 3

    # P-M20: bbox coordinate space — pixel-only with first-frame range assertion.
    # If hardware turns out to emit normalized bboxes, flip these to 1.0 and add
    # a multiplication. HARDWARE-VERIFY on first Hailo-8 day.
    frame_width: int = 640
    frame_height: int = 480

    # journey_id must match {vehicle_id}_{trip_number}_{YYYYMMDD} per ADR-2 / EventEnvelope.
    # Default is a syntactically-valid placeholder; production sets via vlan-pollers context push
    # once a real trip is observed (same pattern as rtsp-ingest).
    vehicle_id: str = "OBB-TEST"
    journey_id: str = "OBB-TEST_unknown_19700101"
    schema_version: int = 1
