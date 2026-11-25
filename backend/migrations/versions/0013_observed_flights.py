"""Persist passively observed flights and their administrative association."""

import sqlalchemy as sa
from alembic import op

revision = "0013_observed_flights"
down_revision = "0012_observed_ground_speed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vehicle_health_snapshots", sa.Column("px4_flight", sa.JSON()))
    op.create_table(
        "observed_flights",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "vehicle_id",
            sa.Uuid(),
            sa.ForeignKey("vehicles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("mission_id", sa.Uuid(), sa.ForeignKey("missions.id", ondelete="RESTRICT")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("evidence", sa.JSON(), nullable=False),
    )
    op.create_index("ix_observed_flights_vehicle_id", "observed_flights", ["vehicle_id"])
    op.create_index("ix_observed_flights_mission_id", "observed_flights", ["mission_id"])


def downgrade() -> None:
    op.drop_table("observed_flights")
    op.drop_column("vehicle_health_snapshots", "px4_flight")
