from __future__ import annotations

import uuid
from datetime import datetime

from core.db.base import Base, JSONType, UUIDPrimaryKeyMixin
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column


class ActionProposal(UUIDPrimaryKeyMixin, Base):
    """A mutating action proposed by the AI, awaiting human confirmation."""

    __tablename__ = "ai_proposals"

    user_id: Mapped[uuid.UUID | None] = mapped_column()
    action_key: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONType)
    preview: Mapped[dict] = mapped_column(JSONType)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
