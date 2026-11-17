from __future__ import annotations

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.db.base import BusinessModel, JSONType

CENTRAL = "central"
INSTANCE = "instance"
LAYERS = (CENTRAL, INSTANCE)


class Setting(BusinessModel):
    """One override at one layer. The code defaults live in the schema itself."""

    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("layer", "module", "key", name="uq_settings_layer_module_key"),)

    layer: Mapped[str] = mapped_column(String(20), nullable=False)
    module: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    value: Mapped[object] = mapped_column(JSONType, nullable=False)


__all__ = ["CENTRAL", "INSTANCE", "LAYERS", "Setting"]
