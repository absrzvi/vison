from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    vehicle_id: str = "OBB-TEST"
    snmp_host: str = "localhost"
    snmp_port: int = 161
    snmp_community: str = "public"
    snmp_speed_oid: str = "1.3.6.1.4.1.12345.1.1.1.0"
    event_store_url: str = "http://event-store:8001"
    fusion_url: str = "http://fusion:8003"
    inference_url: str = "http://inference:8004"
    rtsp_ingest_url: str = "http://rtsp-ingest:8005"
    station_approach_window_s: int = 120
    snmp_poll_interval_s: float = 5.0
    apc_url: str = "http://apc-mock:8010"
    pis_url: str = "http://pis-mock:8011"
    reservation_url: str = "http://reservation-mock:8012"
    apc_poll_interval_s: float = 5.0
    pis_poll_interval_s: float = 5.0
    reservation_poll_interval_s: float = 30.0
    car_ids: list[str] = ["car-1", "car-2", "car-3", "car-4", "car-5"]


settings = Settings()
