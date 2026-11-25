"""Persist ground speed received by the passive vehicle observer."""

import sqlalchemy as sa
from alembic import op

revision = "0012_observed_ground_speed"
down_revision = "0011_bench_arm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vehicle_health_snapshots",
        sa.Column("current_ground_speed_m_s", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("vehicle_health_snapshots", "current_ground_speed_m_s")
