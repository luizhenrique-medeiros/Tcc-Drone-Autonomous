"""Add reusable customer saved locations.

Revision ID: 0004_saved_locations
Revises: 0003_schema_names
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.database.types import GeographyPoint

revision: str = "0004_saved_locations"
down_revision: str | None = "0003_schema_names"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saved_locations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(40), nullable=False),
        sa.Column("final_latitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("final_longitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("location", GeographyPoint(), nullable=False),
        sa.Column("address_reference", sa.String(500)),
        sa.Column("instructions", sa.Text()),
        sa.Column("accuracy_meters", sa.Numeric(8, 2)),
        sa.Column("map_provider", sa.String(40), nullable=False),
        sa.Column("map_type", sa.String(30), nullable=False),
        sa.Column("region_confirmed", sa.Boolean(), nullable=False),
        sa.Column("exact_point_selected", sa.Boolean(), nullable=False),
        sa.Column("user_confirmed", sa.Boolean(), nullable=False),
        sa.Column("user_confirmed_safe_area", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(trim(name)) BETWEEN 1 AND 40",
            name="ck_saved_location_name_length",
        ),
        sa.CheckConstraint(
            "final_latitude BETWEEN -90 AND 90",
            name="ck_saved_location_final_latitude",
        ),
        sa.CheckConstraint(
            "final_longitude BETWEEN -180 AND 180",
            name="ck_saved_location_final_longitude",
        ),
        sa.CheckConstraint(
            "accuracy_meters IS NULL OR accuracy_meters >= 0",
            name="ck_saved_location_accuracy_nonnegative",
        ),
        sa.CheckConstraint(
            "map_type IN ('hybrid', 'satellite')",
            name="ck_saved_location_map_type",
        ),
        sa.CheckConstraint(
            "region_confirmed AND exact_point_selected AND user_confirmed "
            "AND user_confirmed_safe_area",
            name="ck_saved_location_confirmations",
        ),
    )
    op.create_index("ix_saved_locations_user_id", "saved_locations", ["user_id"])


def downgrade() -> None:
    op.drop_table("saved_locations")
