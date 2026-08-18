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

from app.core.enums import OperationalSource, VehicleStatus
from app.database.base import Base, TimestampMixin, utc_now


class Vehicle(TimestampMixin, Base):
    __tablename__ = "vehicles"
    __table_args__ = (UniqueConstraint("identifier", name="uq_vehicles_identifier"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    identifier: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    autopilot_system: Mapped[str] = mapped_column(String(80), nullable=False)
    autopilot_version: Mapped[str | None] = mapped_column(String(120))
    operational_source: Mapped[OperationalSource] = mapped_column(
        Enum(OperationalSource, name="operational_source", native_enum=False),
        default=OperationalSource.UNKNOWN,
        nullable=False,
    )
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
    source: Mapped[OperationalSource] = mapped_column(
        Enum(OperationalSource, name="operational_source", native_enum=False),
        default=OperationalSource.UNKNOWN,
        nullable=False,
    )
    gps_fix_type: Mapped[int | None] = mapped_column(Integer)
    satellites: Mapped[int | None] = mapped_column(Integer)
    ekf_ok: Mapped[bool | None] = mapped_column(Boolean)
    battery_percent: Mapped[float | None] = mapped_column(Float)
    battery_voltage: Mapped[float | None] = mapped_column(Float)
    flight_mode: Mapped[str | None] = mapped_column(String(40))
    armed: Mapped[bool | None] = mapped_column(Boolean)
    preflight_ok: Mapped[bool | None] = mapped_column(Boolean)
    rtl_configured: Mapped[bool | None] = mapped_column(Boolean)
    geofence_enabled: Mapped[bool | None] = mapped_column(Boolean)
    origin_latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    origin_longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    connection_state: Mapped[str | None] = mapped_column(String(40))
    connection_mode: Mapped[str | None] = mapped_column(String(40))
    connection_topology: Mapped[str | None] = mapped_column(String(80))
    connection_endpoint: Mapped[str | None] = mapped_column(String(240))
    serial_port: Mapped[str | None] = mapped_column(String(100))
    connection_baud: Mapped[int | None] = mapped_column(Integer)
    mavlink_system_id: Mapped[int | None] = mapped_column(Integer)
    mavlink_component_id: Mapped[int | None] = mapped_column(Integer)
    heartbeat_age_seconds: Mapped[float | None] = mapped_column(Float)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    current_longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    current_altitude_m: Mapped[float | None] = mapped_column(Float)
    mission_upload_enabled: Mapped[bool | None] = mapped_column(Boolean)
    flight_commands_enabled: Mapped[bool | None] = mapped_column(Boolean)
    mission_start_enabled: Mapped[bool | None] = mapped_column(Boolean)
    connection_error: Mapped[str | None] = mapped_column(String(2000))
    critical_state_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
