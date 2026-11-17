from __future__ import annotations

from app.settings import Settings
from fastapi import Request

from core.files.storage import Storage


def get_storage(request: Request) -> Storage:
    return request.app.state.storage


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


__all__ = ["get_app_settings", "get_storage"]
