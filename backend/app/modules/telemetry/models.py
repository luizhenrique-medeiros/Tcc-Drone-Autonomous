from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import OperationalSource
from app.database.base import Base, utc_now


class TelemetryLog(Base):
    __tablename__ = "telemetry_logs"
    __table_args__ = (UniqueConstraint("event_id", name="uq_telemetry_logs_event_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    mission_id: Mapped[UUID] = mapped_column(
        ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vehicle_id: Mapped[UUID] = mapped_column(
        ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[OperationalSource] = mapped_column(
        Enum(OperationalSource, name="operational_source", native_enum=False),
        default=OperationalSource.UNKNOWN,
        nullable=False,
    )
    latitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    relative_altitude_m: Mapped[float] = mapped_column(Float, nullable=False)
    ground_speed_m_s: Mapped[float] = mapped_column(Float, nullable=False)
    battery_percent: Mapped[float | None] = mapped_column(Float)
    gps_fix_type: Mapped[int | None] = mapped_column(Integer)
    satellites: Mapped[int | None] = mapped_column(Integer)
    flight_mode: Mapped[str | None] = mapped_column(String(40))
    armed: Mapped[bool | None] = mapped_column(Boolean)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
