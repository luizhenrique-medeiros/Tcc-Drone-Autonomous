"""Persist standalone bench ARM requests and bind them to a connection session."""

import sqlalchemy as sa
from alembic import op

revision = "0011_bench_arm"
down_revision = "0010_px4_health_diagnostics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vehicle_health_snapshots", sa.Column("bench_arm_session_id", sa.Uuid()))
    op.create_table(
        "bench_arm_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("vehicle_id", sa.Uuid(), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("requested_by_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("gateway_id", sa.String(120), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("target_system", sa.Integer(), nullable=False),
        sa.Column("target_component", sa.Integer(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("transmitted", sa.Boolean()),
        sa.Column("ack_result", sa.BigInteger()),
        sa.Column("confirmed_heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("confirmed_snapshot_id", sa.Uuid()),
        sa.Column("detail", sa.String(1000)),
    )
    op.create_index("ix_bench_arm_requests_vehicle_id", "bench_arm_requests", ["vehicle_id"])


def downgrade() -> None:
    op.drop_index("ix_bench_arm_requests_vehicle_id", table_name="bench_arm_requests")
    op.drop_table("bench_arm_requests")
    op.drop_column("vehicle_health_snapshots", "bench_arm_session_id")
