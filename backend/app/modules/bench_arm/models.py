from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class BenchArmRequest(Base):
    __tablename__ = "bench_arm_requests"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    vehicle_id: Mapped[UUID] = mapped_column(ForeignKey("vehicles.id"), index=True)
    requested_by_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    gateway_id: Mapped[str] = mapped_column(String(120))
    session_id: Mapped[UUID] = mapped_column()
    target_system: Mapped[int] = mapped_column()
    target_component: Mapped[int] = mapped_column()
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    transmitted: Mapped[bool | None] = mapped_column(Boolean)
    ack_result: Mapped[int | None] = mapped_column(BigInteger)
    confirmed_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_snapshot_id: Mapped[UUID | None] = mapped_column()
    detail: Mapped[str | None] = mapped_column(String(1000))
