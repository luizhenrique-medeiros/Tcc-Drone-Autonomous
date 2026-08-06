from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import SelectionSource
from app.database.base import Base, TimestampMixin
from app.database.types import GeographyPoint


class DeliveryPoint(TimestampMixin, Base):
    __tablename__ = "delivery_points"
    __table_args__ = (
        CheckConstraint("final_latitude BETWEEN -90 AND 90", name="ck_point_final_latitude"),
        CheckConstraint("final_longitude BETWEEN -180 AND 180", name="ck_point_final_longitude"),
        Index(
            "ix_delivery_points_location_gist",
            "location",
            postgresql_using="gist",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    searched_address: Mapped[str | None] = mapped_column(String(500))
    address_reference: Mapped[str | None] = mapped_column(String(500))
    selection_source: Mapped[SelectionSource] = mapped_column(
        Enum(SelectionSource, name="selection_source", native_enum=False), nullable=False
    )
    approximate_latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    approximate_longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    final_latitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    final_longitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    location: Mapped[str] = mapped_column(GeographyPoint(), nullable=False)
    label: Mapped[str | None] = mapped_column(String(120))
    instructions: Mapped[str | None] = mapped_column(Text)
    map_provider: Mapped[str] = mapped_column(String(40), default="google_maps", nullable=False)
    map_type: Mapped[str] = mapped_column(String(30), default="satellite", nullable=False)
    accuracy_meters: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    region_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    exact_point_selected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    user_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    user_confirmed_safe_area: Mapped[bool] = mapped_column(Boolean, nullable=False)
    distance_from_approximate_m: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    distance_from_base_m: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
