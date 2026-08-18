"""Add optional vehicle integration diagnostics.

Revision ID: 0005_integration_health
Revises: 0004_saved_locations
Create Date: 2026-08-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_integration_health"
down_revision: str | None = "0004_saved_locations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("vehicle_health_snapshots") as batch_op:
        batch_op.add_column(sa.Column("connection_state", sa.String(40)))
        batch_op.add_column(sa.Column("connection_mode", sa.String(40)))
        batch_op.add_column(sa.Column("connection_topology", sa.String(80)))
        batch_op.add_column(sa.Column("connection_endpoint", sa.String(240)))
        batch_op.add_column(sa.Column("serial_port", sa.String(100)))
        batch_op.add_column(sa.Column("connection_baud", sa.Integer()))
        batch_op.add_column(sa.Column("mavlink_system_id", sa.Integer()))
        batch_op.add_column(sa.Column("mavlink_component_id", sa.Integer()))
        batch_op.add_column(sa.Column("heartbeat_age_seconds", sa.Float()))
        batch_op.add_column(sa.Column("last_heartbeat_at", sa.DateTime(timezone=True)))
        batch_op.add_column(sa.Column("current_latitude", sa.Numeric(10, 7)))
        batch_op.add_column(sa.Column("current_longitude", sa.Numeric(10, 7)))
        batch_op.add_column(sa.Column("current_altitude_m", sa.Float()))
        batch_op.add_column(sa.Column("mission_upload_enabled", sa.Boolean()))
        batch_op.add_column(sa.Column("flight_commands_enabled", sa.Boolean()))
        batch_op.add_column(sa.Column("connection_error", sa.String(2000)))


def downgrade() -> None:
    with op.batch_alter_table("vehicle_health_snapshots") as batch_op:
        batch_op.drop_column("connection_error")
        batch_op.drop_column("flight_commands_enabled")
        batch_op.drop_column("mission_upload_enabled")
        batch_op.drop_column("current_altitude_m")
        batch_op.drop_column("current_longitude")
        batch_op.drop_column("current_latitude")
        batch_op.drop_column("last_heartbeat_at")
        batch_op.drop_column("heartbeat_age_seconds")
        batch_op.drop_column("mavlink_component_id")
        batch_op.drop_column("mavlink_system_id")
        batch_op.drop_column("connection_baud")
        batch_op.drop_column("serial_port")
        batch_op.drop_column("connection_endpoint")
        batch_op.drop_column("connection_topology")
        batch_op.drop_column("connection_mode")
        batch_op.drop_column("connection_state")
