"""Runtime configuration for the inference container.

All settings sourced via pydantic-settings (env vars / .env file).
No os.environ.get() calls anywhere in this module — Rule 8.
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFERENCE_", env_file=".env", extra="ignore")

    cameras_json_path: str = "cameras.json"
    event_store_url: str = "http://event-store:8001"
    event_store_api_key: str = ""
    context_push_port: int = 8081

    occupancy_threshold_pct: float = 0.80
    occupancy_capacity_default: int = 200

    tops_total: float = 26.0
    tops_budget_pct_threshold: float = 0.90

    # E4-S5: expanded to include suitcase (door obstruction) and bicycle (accessibility).
    detection_classes: list[str] = ["person", "suitcase", "bicycle"]
    model_hef_path: str = "/models/yolox_s_leaky.hef"

    # E10-S1: model provenance (AC5) + heartbeat cadence (AC7).
    # git_sha is injected via ARG GIT_SHA in the Dockerfile; empty at startup is fatal.
    git_sha: str = ""
    model_labels_path: str = "/models/yolov8m.labels"
    heartbeat_interval_s: float = Field(default=60.0, gt=0.0)

    fusion_url: str = "http://fusion:8090"
    accessibility_confidence_threshold: float = 0.80
    door_obstruction_min_frames: int = 2
    vestibule_congestion_threshold: int = 8
    vestibule_congestion_score_threshold: float = 0.75
    slip_fall_height_collapse_threshold: float = 0.5
    slip_fall_velocity_threshold: float = 50.0
    # Per-stream counting frame rate. Door-line tripwire counting needs 5 FPS
    # (a passenger spends ~1–2 s crossing a threshold) — see camera-allocation
    # bench case 2026-06-07 and architecture §Hailo-8 Capacity Budget. NOT video
    # frame rate; the 10fps P1 ceiling is the schedule cap, not the counting need.
    pipeline_fps: float = Field(default=5.0, gt=0.0)
    # Single multiplexed hailonet batches across the round-robin'd sources
    # (architecture: N sources → hailoroundrobin → ONE hailonet batch_size=8).
    pipeline_batch_size: int = Field(default=8, gt=0)

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
