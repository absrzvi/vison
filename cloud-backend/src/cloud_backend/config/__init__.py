from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql+asyncpg://oebb:oebb@localhost:5432/oebb"
    # DEAD for routing after the E11-S1 JWT cutover; kept because preferences.py
    # still keys operator_preferences by this string until E11-S3 re-keys it, and
    # require_api_key remains importable. Removed when E11-S3 lands.
    api_key: str = "dev-insecure-key"
    # E10-S1 AC12: admin key for the alert-class kill-switch endpoints.
    # MUST come from env CC_ADMIN_KEY; empty default fails closed (all admin
    # requests 401). Never bake a value in here. (E11-S4 swaps this for JWT role.)
    cc_admin_key: str = ""
    # E11-S1 (ADR-23): self-contained JWT. jwt_secret MUST come from env
    # JWT_SECRET; empty default fails closed (no token mints or verifies — AC7),
    # mirroring cc_admin_key. issuer/algorithm/key are config-driven so an
    # external IdP (RS256/JWKS) swaps in without touching get_current_user's
    # callers (the AC4 seam). Never bake a secret in here.
    jwt_secret: str = ""
    jwt_issuer: str = "oebb-cloud-backend"
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_minutes: int = 60
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8002


def get_settings() -> Settings:
    return Settings()
