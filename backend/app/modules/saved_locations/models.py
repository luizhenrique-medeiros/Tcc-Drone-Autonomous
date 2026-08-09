from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin
from app.database.types import GeographyPoint


class SavedLocation(TimestampMixin, Base):
    __tablename__ = "saved_locations"
    __table_args__ = (
        CheckConstraint(
            "length(trim(name)) BETWEEN 1 AND 40",
            name="ck_saved_location_name_length",
        ),
        CheckConstraint(
            "final_latitude BETWEEN -90 AND 90",
            name="ck_saved_location_final_latitude",
        ),
        CheckConstraint(
            "final_longitude BETWEEN -180 AND 180",
            name="ck_saved_location_final_longitude",
        ),
        CheckConstraint(
            "accuracy_meters IS NULL OR accuracy_meters >= 0",
            name="ck_saved_location_accuracy_nonnegative",
        ),
        CheckConstraint(
            "map_type IN ('hybrid', 'satellite')",
            name="ck_saved_location_map_type",
        ),
        CheckConstraint(
            "region_confirmed AND exact_point_selected AND user_confirmed "
            "AND user_confirmed_safe_area",
            name="ck_saved_location_confirmations",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    final_latitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    final_longitude: Mapped[Decimal] = mapped_column(Numeric(10, 7), nullable=False)
    location: Mapped[str] = mapped_column(GeographyPoint(), nullable=False)
    address_reference: Mapped[str | None] = mapped_column(String(500))
    instructions: Mapped[str | None] = mapped_column(Text)
    accuracy_meters: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    map_provider: Mapped[str] = mapped_column(String(40), nullable=False)
    map_type: Mapped[str] = mapped_column(String(30), nullable=False)
    region_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    exact_point_selected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    user_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    user_confirmed_safe_area: Mapped[bool] = mapped_column(Boolean, nullable=False)
