"""Bind a PX4 test authorization to the exact QGroundControl review."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_px4_review_binding"
down_revision: str | None = "0008_vehicle_position_amsl"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("flight_authorizations") as batch:
        batch.add_column(sa.Column("qgroundcontrol_review_event_id", sa.Uuid()))
        batch.add_column(sa.Column("qgroundcontrol_candidate_sha256", sa.String(64)))
        batch.create_foreign_key(
            "fk_flight_authorizations_qgc_review",
            "system_events",
            ["qgroundcontrol_review_event_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    with op.batch_alter_table("flight_authorizations") as batch:
        batch.drop_constraint("fk_flight_authorizations_qgc_review", type_="foreignkey")
        batch.drop_column("qgroundcontrol_candidate_sha256")
        batch.drop_column("qgroundcontrol_review_event_id")
