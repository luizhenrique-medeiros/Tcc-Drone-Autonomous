from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import GatewayCommandStatus, GatewayCommandType, MissionStatus
from app.database.base import Base, TimestampMixin, utc_now
from app.database.types import GeographyPoint


class Mission(TimestampMixin, Base):
    __tablename__ = "missions"
    __table_args__ = (UniqueConstraint("order_id", name="uq_missions_order_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    vehicle_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("vehicles.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[MissionStatus] = mapped_column(
        Enum(MissionStatus, name="mission_status", native_enum=False),
        default=MissionStatus.DRAFT,
        nullable=False,
        index=True,
    )
    origin_latitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    origin_longitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    origin: Mapped[str] = mapped_column(GeographyPoint(), nullable=False)
    destination_latitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    destination_longitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    destination: Mapped[str] = mapped_column(GeographyPoint(), nullable=False)
    takeoff_altitude_m: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    estimated_distance_m: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    mission_file: Mapped[str] = mapped_column(Text, nullable=False)
    mission_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(Text)
    claimed_by_gateway: Mapped[str | None] = mapped_column(String(120))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    waypoints: Mapped[list[MissionWaypoint]] = relationship(
        back_populates="mission",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="MissionWaypoint.sequence",
    )


class MissionWaypoint(Base):
    __tablename__ = "mission_waypoints"
    __table_args__ = (UniqueConstraint("mission_id", "sequence", name="uq_waypoint_sequence"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    mission_id: Mapped[UUID] = mapped_column(
        ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    command: Mapped[int] = mapped_column(Integer, nullable=False)
    frame: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    current: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    autocontinue: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    param1: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    param2: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    param3: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    param4: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    latitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    altitude_m: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False)

    mission: Mapped[Mission] = relationship(back_populates="waypoints")


class GatewayCommand(Base):
    __tablename__ = "gateway_commands"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    mission_id: Mapped[UUID] = mapped_column(
        ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    command: Mapped[GatewayCommandType] = mapped_column(
        Enum(GatewayCommandType, name="gateway_command_type", native_enum=False), nullable=False
    )
    status: Mapped[GatewayCommandStatus] = mapped_column(
        Enum(GatewayCommandStatus, name="gateway_command_status", native_enum=False),
        default=GatewayCommandStatus.PENDING,
        nullable=False,
        index=True,
    )
    gateway_id: Mapped[str | None] = mapped_column(String(120))
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_detail: Mapped[str | None] = mapped_column(Text)
