from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ControllerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.getenv("ENV_FILE", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "School ERP Control Plane"
    app_env: str = "development"
    app_version: str = "0.0.0"
    api_version: str = "v1"

    controller_database_url: str = "sqlite+aiosqlite:///./data/controller.db"
    auto_create_schema: bool = True
    controller_secret_key: str = "controller-dev-only-change-me-0123456789"
    controller_public_base_url: str = "http://localhost:8100"
    controller_api_base_url: str = "http://localhost:8100"

    directory_private_key: str = ""
    directory_public_key: str = ""
    directory_kid: str = "k1"

    license_private_key: str = ""
    license_public_key: str = ""
    license_kid: str = "l1"
    license_valid_days: int = 30
    license_grace_days: int = 14

    access_token_minutes: int = 60
    cors_origins: str = "http://localhost:5174,http://localhost:8081"
    support_session_minutes: int = 10
    directory_rate_limit_per_minute: int = 30

    # Audit vault suspicious-pattern thresholds (P1-12)
    vault_mass_delete_threshold: int = 10
    vault_mass_delete_window_minutes: int = 10
    vault_off_hours_start: int = 22
    vault_off_hours_end: int = 6
    vault_off_hours_threshold: int = 5

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_controller_settings() -> ControllerSettings:
    return ControllerSettings()
