"""Add operational provenance, receipt timestamps, and safety reasons.

Revision ID: 0002_operational_provenance
Revises: 0001_initial
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_operational_provenance"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("vehicles") as batch_op:
        batch_op.add_column(sa.Column("autopilot_version", sa.String(120)))
        batch_op.add_column(
            sa.Column(
                "operational_source",
                sa.String(20),
                nullable=False,
                server_default="UNKNOWN",
            )
        )

    with op.batch_alter_table("vehicle_health_snapshots") as batch_op:
        batch_op.add_column(
            sa.Column("source", sa.String(20), nullable=False, server_default="UNKNOWN")
        )
        batch_op.add_column(
            sa.Column(
                "received_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.current_timestamp(),
            )
        )
        for column_name, existing_type in (
            ("gps_fix_type", sa.Integer()),
            ("satellites", sa.Integer()),
            ("ekf_ok", sa.Boolean()),
            ("battery_percent", sa.Float()),
            ("flight_mode", sa.String(40)),
            ("armed", sa.Boolean()),
            ("preflight_ok", sa.Boolean()),
            ("rtl_configured", sa.Boolean()),
            ("geofence_enabled", sa.Boolean()),
        ):
            batch_op.alter_column(column_name, existing_type=existing_type, nullable=True)
        batch_op.create_index(
            "ix_vehicle_health_snapshots_received_at", ["received_at"], unique=False
        )
    op.execute("UPDATE vehicle_health_snapshots SET received_at = captured_at")

    with op.batch_alter_table("telemetry_logs") as batch_op:
        batch_op.add_column(
            sa.Column("source", sa.String(20), nullable=False, server_default="UNKNOWN")
        )
        batch_op.add_column(
            sa.Column(
                "received_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.current_timestamp(),
            )
        )
        batch_op.add_column(
            sa.Column("is_stale", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        for column_name, existing_type in (
            ("battery_percent", sa.Float()),
            ("gps_fix_type", sa.Integer()),
            ("satellites", sa.Integer()),
            ("flight_mode", sa.String(40)),
            ("armed", sa.Boolean()),
        ):
            batch_op.alter_column(column_name, existing_type=existing_type, nullable=True)
        batch_op.create_index("ix_telemetry_logs_received_at", ["received_at"], unique=False)
        batch_op.create_index("ix_telemetry_logs_is_stale", ["is_stale"], unique=False)
    op.execute("UPDATE telemetry_logs SET received_at = recorded_at")

    with op.batch_alter_table("gateway_commands") as batch_op:
        batch_op.add_column(sa.Column("reason", sa.Text()))


def downgrade() -> None:
    with op.batch_alter_table("gateway_commands") as batch_op:
        batch_op.drop_column("reason")

    with op.batch_alter_table("telemetry_logs") as batch_op:
        batch_op.drop_index("ix_telemetry_logs_is_stale")
        batch_op.drop_index("ix_telemetry_logs_received_at")
    # The legacy schema was NOT NULL and represented missing MAVLink data with
    # placeholders. A downgrade therefore has to restore those legacy values.
    op.execute(
        "UPDATE telemetry_logs SET "
        "battery_percent = COALESCE(battery_percent, 0), "
        "gps_fix_type = COALESCE(gps_fix_type, 0), "
        "satellites = COALESCE(satellites, 0), "
        "flight_mode = COALESCE(flight_mode, 'UNKNOWN'), "
        "armed = COALESCE(armed, FALSE)"
    )
    with op.batch_alter_table("telemetry_logs") as batch_op:
        for column_name, existing_type in (
            ("battery_percent", sa.Float()),
            ("gps_fix_type", sa.Integer()),
            ("satellites", sa.Integer()),
            ("flight_mode", sa.String(40)),
            ("armed", sa.Boolean()),
        ):
            batch_op.alter_column(column_name, existing_type=existing_type, nullable=False)
        batch_op.drop_column("is_stale")
        batch_op.drop_column("received_at")
        batch_op.drop_column("source")

    with op.batch_alter_table("vehicle_health_snapshots") as batch_op:
        batch_op.drop_index("ix_vehicle_health_snapshots_received_at")
    # Same unavoidable compatibility coercion for rollback to revision 0001.
    op.execute(
        "UPDATE vehicle_health_snapshots SET "
        "gps_fix_type = COALESCE(gps_fix_type, 0), "
        "satellites = COALESCE(satellites, 0), "
        "ekf_ok = COALESCE(ekf_ok, FALSE), "
        "battery_percent = COALESCE(battery_percent, 0), "
        "flight_mode = COALESCE(flight_mode, 'UNKNOWN'), "
        "armed = COALESCE(armed, FALSE), "
        "preflight_ok = COALESCE(preflight_ok, FALSE), "
        "rtl_configured = COALESCE(rtl_configured, FALSE), "
        "geofence_enabled = COALESCE(geofence_enabled, FALSE)"
    )
    with op.batch_alter_table("vehicle_health_snapshots") as batch_op:
        for column_name, existing_type in (
            ("gps_fix_type", sa.Integer()),
            ("satellites", sa.Integer()),
            ("ekf_ok", sa.Boolean()),
            ("battery_percent", sa.Float()),
            ("flight_mode", sa.String(40)),
            ("armed", sa.Boolean()),
            ("preflight_ok", sa.Boolean()),
            ("rtl_configured", sa.Boolean()),
            ("geofence_enabled", sa.Boolean()),
        ):
            batch_op.alter_column(column_name, existing_type=existing_type, nullable=False)
        batch_op.drop_column("received_at")
        batch_op.drop_column("source")

    with op.batch_alter_table("vehicles") as batch_op:
        batch_op.drop_column("operational_source")
        batch_op.drop_column("autopilot_version")
