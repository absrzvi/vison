from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    cameras_json_path: str = "cameras.json"
    vehicle_id: str = "OBB-TEST"
    tops_budget_pct_threshold: float = 0.90
    tops_total: float = 26.0
    p1_fps: float = 10.0
    p2_fps: float = 5.0
    p2_throttled_fps: float = 2.0
    p3_fps: float = 8.0
    station_speed_threshold_kmh: float = 20.0
    door_release_override_s: float = 120.0
    event_store_url: str = "http://event-store:8000"
    context_push_port: int = 8080


settings = Settings()
