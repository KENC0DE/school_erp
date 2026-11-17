from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.getenv("ENV_FILE", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "School ERP"
    app_env: str = "development"
    dev_mode: bool = True
    api_version: str = "v1"
    app_version: str = "0.0.0"
    min_client_version: str = "0.0.0"

    database_url: str = "sqlite+aiosqlite:///./data/erp_demo.db"
    auto_create_schema: bool = True
    redis_url: str = "redis://localhost:6379/0"

    secret_key: str = "dev-only-change-me-please-0123456789abcdef"
    refresh_secret: str = "dev-only-change-me-too-0123456789abcdef"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    cors_origins: str = "http://localhost:5173,http://localhost:8081"
    public_base_url: str = "http://localhost:8000"

    storage_driver: str = "local"
    storage_dir: str = "./data/storage"

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    mail_from: str = "no-reply@demo.school"

    controller_url: str = "http://localhost:8100"
    controller_public_key: str = ""
    instance_id: str = ""
    enrollment_token: str = ""
    heartbeat_seconds: int = 60
    audit_ship_batch: int = 100

    idempotency_enabled: bool = True
    idempotency_ttl_seconds: int = 86_400

    ai_provider: str = "fake"
    ai_model: str = "fake-echo"
    ai_api_key: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
