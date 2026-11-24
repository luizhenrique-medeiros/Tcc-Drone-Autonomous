"""Persist the current vehicle altitude above mean sea level for QGC drafts."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_vehicle_position_amsl"
down_revision: str | None = "0007_vehicle_arm_command"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("vehicle_health_snapshots") as batch_op:
        batch_op.add_column(sa.Column("current_amsl_m", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("vehicle_health_snapshots") as batch_op:
        batch_op.drop_column("current_amsl_m")
