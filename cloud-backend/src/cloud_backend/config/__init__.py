from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # "prod" (default) or "test". Only the test env may lower bcrypt_rounds below
    # the prod floor (see the bcrypt_rounds validator) — so the cheap test cost
    # can never escape into a deployment via a stray env var (E11-S2 D6).
    app_env: str = "prod"

    database_url: str = "postgresql+asyncpg://oebb:oebb@localhost:5432/oebb"
    # DEAD for human-facing routing after the E11-S1 JWT cutover, BUT still live:
    # require_api_key guards the machine-to-machine `POST /api/v1/events` ingest
    # (11-1 D1 / ADR-23 — an unattended producer; a human JWT is the wrong model).
    # E11-S3 removed the preferences-keying reason for it (operator_preferences is
    # now FK'd to users.user_id, Alembic 0011), but the ingest service-token
    # remains. Replacing it with proper per-producer service identity is Phase-2
    # (tracked in deferred-work.md). NOT removed here.
    api_key: str = "dev-insecure-key"
    # NOTE: cc_admin_key (the E10-S1 shared X-Admin-Key for the kill-switch) was
    # REMOVED by E11-S4 — that router now uses require_role("admin") (JWT). It had
    # no remaining reader once require_admin_key was deleted.
    # E11-S1 (ADR-23): self-contained JWT. jwt_secret MUST come from env
    # JWT_SECRET; empty default fails closed (no token mints or verifies — AC7),
    # mirroring cc_admin_key. issuer/algorithm/key are config-driven so an
    # external IdP (RS256/JWKS) swaps in without touching get_current_user's
    # callers (the AC4 seam). Never bake a secret in here.
    jwt_secret: str = ""
    jwt_issuer: str = "oebb-cloud-backend"
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_minutes: int = 60
    # bcrypt work factor for password hashing (E11-S2 D6). Default 12 (prod). The
    # test env drops this to 4 so the real-path integration suite (which creates
    # users through the actual bcrypt) isn't taxed ~250ms/hash. Fail-closed floor
    # below mirrors the cc_admin_key/jwt_secret "don't trust env hygiene" posture:
    # a value < 10 is REJECTED at Settings load unless app_env == "test", so a
    # cost-4 prod (which would weaken every credential) cannot happen by accident.
    bcrypt_rounds: int = 12
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8002

    @field_validator("bcrypt_rounds")
    @classmethod
    def _enforce_bcrypt_floor(cls, v: int, info: object) -> int:
        # info.data carries already-validated fields; app_env is declared before
        # bcrypt_rounds so it is present here.
        app_env = getattr(info, "data", {}).get("app_env", "prod")
        if v < 10 and app_env != "test":
            raise ValueError(
                f"bcrypt_rounds={v} is below the prod floor (10); "
                "only app_env='test' may use a lower cost"
            )
        return v


def get_settings() -> Settings:
    return Settings()
