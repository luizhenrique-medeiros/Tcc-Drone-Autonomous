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

from app.core.enums import VehicleStatus
from app.database.base import Base, TimestampMixin, utc_now


class Vehicle(TimestampMixin, Base):
    __tablename__ = "vehicles"
    __table_args__ = (UniqueConstraint("identifier", name="uq_vehicles_identifier"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    identifier: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    autopilot_system: Mapped[str] = mapped_column(String(80), nullable=False)
    gateway_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    status: Mapped[VehicleStatus] = mapped_column(
        Enum(VehicleStatus, name="vehicle_status", native_enum=False),
        default=VehicleStatus.UNKNOWN,
        nullable=False,
        index=True,
    )
    last_communication_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VehicleHealthSnapshot(Base):
    __tablename__ = "vehicle_health_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    vehicle_id: Mapped[UUID] = mapped_column(
        ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    connected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    heartbeat: Mapped[bool] = mapped_column(Boolean, nullable=False)
    gps_fix_type: Mapped[int] = mapped_column(Integer, nullable=False)
    satellites: Mapped[int] = mapped_column(Integer, nullable=False)
    ekf_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    battery_percent: Mapped[float] = mapped_column(Float, nullable=False)
    battery_voltage: Mapped[float | None] = mapped_column(Float)
    flight_mode: Mapped[str] = mapped_column(String(40), nullable=False)
    armed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    preflight_ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rtl_configured: Mapped[bool] = mapped_column(Boolean, nullable=False)
    geofence_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    origin_latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    origin_longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    critical_state_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
