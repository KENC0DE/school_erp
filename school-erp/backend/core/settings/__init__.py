"""Typed, layered school settings (ARCH §5.10)."""

from core.settings.models import Setting
from core.settings.router import router
from core.settings.schema import SettingField, field_specs, flatten_values, validate_value
from core.settings.service import (
    all_settings,
    clear_setting,
    effective_map,
    module_settings,
    set_setting,
)

__all__ = [
    "Setting",
    "SettingField",
    "all_settings",
    "clear_setting",
    "effective_map",
    "field_specs",
    "flatten_values",
    "module_settings",
    "router",
    "set_setting",
    "validate_value",
]
