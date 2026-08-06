from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import EventSeverity
from app.database.base import Base, utc_now


class SystemEvent(Base):
    __tablename__ = "system_events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_system_events_event_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_id: Mapped[str | None] = mapped_column(String(120), index=True)
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    actor_type: Mapped[str] = mapped_column(String(30), nullable=False)
    order_id: Mapped[UUID | None] = mapped_column(ForeignKey("orders.id"), index=True)
    mission_id: Mapped[UUID | None] = mapped_column(ForeignKey("missions.id"), index=True)
    vehicle_id: Mapped[UUID | None] = mapped_column(ForeignKey("vehicles.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[EventSeverity] = mapped_column(
        Enum(EventSeverity, name="event_severity", native_enum=False), nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    event_metadata: Mapped[dict[str, str | int | float | bool | None]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
