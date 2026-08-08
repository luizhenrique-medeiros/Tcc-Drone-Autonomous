"""Normalize names left by legacy create-all databases.

Revision ID: 0003_schema_names
Revises: 0002_operational_provenance
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_schema_names"
down_revision: str | None = "0002_operational_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


INDEX_RENAMES = (
    ("admin_decisions", "ix_admin_decisions_admin", "ix_admin_decisions_administrator_id"),
    ("admin_decisions", "ix_admin_decisions_order", "ix_admin_decisions_order_id"),
    ("delivery_points", "ix_delivery_points_user", "ix_delivery_points_user_id"),
    (
        "flight_authorizations",
        "ix_authorizations_mission",
        "ix_flight_authorizations_mission_id",
    ),
    (
        "flight_authorizations",
        "ix_authorizations_status",
        "ix_flight_authorizations_status",
    ),
    ("gateway_commands", "ix_gateway_commands_mission", "ix_gateway_commands_mission_id"),
    ("mission_waypoints", "ix_waypoints_mission", "ix_mission_waypoints_mission_id"),
    ("missions", "ix_missions_order", "ix_missions_order_id"),
    ("missions", "ix_missions_vehicle", "ix_missions_vehicle_id"),
    ("order_items", "ix_order_items_order", "ix_order_items_order_id"),
    ("orders", "ix_orders_customer", "ix_orders_customer_id"),
    ("orders", "ix_orders_point", "ix_orders_delivery_point_id"),
    ("telemetry_logs", "ix_telemetry_event", "ix_telemetry_logs_event_id"),
    ("telemetry_logs", "ix_telemetry_mission", "ix_telemetry_logs_mission_id"),
    ("telemetry_logs", "ix_telemetry_recorded", "ix_telemetry_logs_recorded_at"),
    ("telemetry_logs", "ix_telemetry_vehicle", "ix_telemetry_logs_vehicle_id"),
    (
        "vehicle_health_snapshots",
        "ix_health_captured",
        "ix_vehicle_health_snapshots_captured_at",
    ),
    (
        "vehicle_health_snapshots",
        "ix_health_vehicle",
        "ix_vehicle_health_snapshots_vehicle_id",
    ),
)

UNIQUE_RENAMES = (
    ("missions", "missions_order_id_key", "uq_missions_order_id"),
    ("system_events", "system_events_event_id_key", "uq_system_events_event_id"),
    ("telemetry_logs", "telemetry_logs_event_id_key", "uq_telemetry_logs_event_id"),
    ("users", "users_email_key", "uq_users_email"),
    ("vehicles", "vehicles_identifier_key", "uq_vehicles_identifier"),
)


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _rename_index(table_name: str, old_name: str, new_name: str) -> None:
    inspector = sa.inspect(op.get_bind())
    names = {item["name"] for item in inspector.get_indexes(table_name)}
    if old_name in names and new_name not in names:
        op.execute(sa.text(f"ALTER INDEX {_quote(old_name)} RENAME TO {_quote(new_name)}"))


def _rename_unique(table_name: str, old_name: str, new_name: str) -> None:
    inspector = sa.inspect(op.get_bind())
    names = {
        item["name"]
        for item in inspector.get_unique_constraints(table_name)
        if item["name"] is not None
    }
    if old_name in names and new_name not in names:
        op.execute(
            sa.text(
                f"ALTER TABLE {_quote(table_name)} "
                f"RENAME CONSTRAINT {_quote(old_name)} TO {_quote(new_name)}"
            )
        )


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table_name, old_name, new_name in INDEX_RENAMES:
        _rename_index(table_name, old_name, new_name)
    for table_name, old_name, new_name in UNIQUE_RENAMES:
        _rename_unique(table_name, old_name, new_name)


def downgrade() -> None:
    # The previous revision is compatible with both name sets. Reintroducing
    # legacy names would create drift for databases originally built by 0001,
    # so this compatibility-only normalization is intentionally retained.
    pass
