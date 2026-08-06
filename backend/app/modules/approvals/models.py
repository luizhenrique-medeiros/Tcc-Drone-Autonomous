from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import AdminDecisionType, AuthorizationStatus
from app.database.base import Base, utc_now


class AdminDecision(Base):
    __tablename__ = "admin_decisions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    administrator_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    decision: Mapped[AdminDecisionType] = mapped_column(
        Enum(AdminDecisionType, name="admin_decision_type", native_enum=False), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class FlightAuthorization(Base):
    __tablename__ = "flight_authorizations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    mission_id: Mapped[UUID] = mapped_column(
        ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    administrator_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    vehicle_health_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("vehicle_health_snapshots.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[AuthorizationStatus] = mapped_column(
        Enum(AuthorizationStatus, name="authorization_status", native_enum=False),
        default=AuthorizationStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    mission_version: Mapped[int] = mapped_column(Integer, nullable=False)
    mission_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    checklist: Mapped[dict[str, bool | str | float]] = mapped_column(JSON, nullable=False)
    controlled_area_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    operator_name: Mapped[str] = mapped_column(String(120), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
