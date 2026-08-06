"""Initial modular domain with PostGIS delivery and mission points.

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.database.types import GeographyPoint

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "role",
            sa.Enum("CUSTOMER", "ADMIN", name="user_role", native_enum=False),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("phone", sa.String(30)),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
        *_timestamps(),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("operation", sa.String(160), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_sha256", sa.String(64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "operation", "idempotency_key", name="uq_idempotency_scope"),
    )
    op.create_index("ix_idempotency_records_user_id", "idempotency_records", ["user_id"])

    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("image_url", sa.String(500)),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.CheckConstraint("price >= 0", name="ck_product_price_nonnegative"),
        *_timestamps(),
    )
    op.create_index("ix_products_category", "products", ["category"])
    op.create_index("ix_products_available", "products", ["available"])

    op.create_table(
        "vehicles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("identifier", sa.String(120), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("autopilot_system", sa.String(80), nullable=False),
        sa.Column("gateway_id", sa.String(120), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "UNKNOWN",
                "OFFLINE",
                "ONLINE",
                "BUSY",
                "ERROR",
                name="vehicle_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("last_communication_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("identifier", name="uq_vehicles_identifier"),
        *_timestamps(),
    )
    op.create_index("ix_vehicles_identifier", "vehicles", ["identifier"])
    op.create_index("ix_vehicles_gateway_id", "vehicles", ["gateway_id"])
    op.create_index("ix_vehicles_status", "vehicles", ["status"])

    op.create_table(
        "vehicle_health_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "vehicle_id",
            sa.Uuid(),
            sa.ForeignKey("vehicles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("connected", sa.Boolean(), nullable=False),
        sa.Column("heartbeat", sa.Boolean(), nullable=False),
        sa.Column("gps_fix_type", sa.Integer(), nullable=False),
        sa.Column("satellites", sa.Integer(), nullable=False),
        sa.Column("ekf_ok", sa.Boolean(), nullable=False),
        sa.Column("battery_percent", sa.Float(), nullable=False),
        sa.Column("battery_voltage", sa.Float()),
        sa.Column("flight_mode", sa.String(40), nullable=False),
        sa.Column("armed", sa.Boolean(), nullable=False),
        sa.Column("preflight_ok", sa.Boolean(), nullable=False),
        sa.Column("rtl_configured", sa.Boolean(), nullable=False),
        sa.Column("geofence_enabled", sa.Boolean(), nullable=False),
        sa.Column("origin_latitude", sa.Numeric(10, 7)),
        sa.Column("origin_longitude", sa.Numeric(10, 7)),
        sa.Column("critical_state_hash", sa.String(64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_vehicle_health_snapshots_vehicle_id",
        "vehicle_health_snapshots",
        ["vehicle_id"],
    )
    op.create_index(
        "ix_vehicle_health_snapshots_captured_at",
        "vehicle_health_snapshots",
        ["captured_at"],
    )

    op.create_table(
        "delivery_points",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("searched_address", sa.String(500)),
        sa.Column("address_reference", sa.String(500)),
        sa.Column(
            "selection_source",
            sa.Enum(
                "CURRENT_LOCATION",
                "ADDRESS_SEARCH",
                "SAVED_POINT",
                "MANUAL_MAP_SELECTION",
                name="selection_source",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("approximate_latitude", sa.Numeric(10, 7)),
        sa.Column("approximate_longitude", sa.Numeric(10, 7)),
        sa.Column("final_latitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("final_longitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("location", GeographyPoint(), nullable=False),
        sa.Column("label", sa.String(120)),
        sa.Column("instructions", sa.Text()),
        sa.Column("map_provider", sa.String(40), nullable=False),
        sa.Column("map_type", sa.String(30), nullable=False),
        sa.Column("accuracy_meters", sa.Numeric(8, 2)),
        sa.Column("region_confirmed", sa.Boolean(), nullable=False),
        sa.Column("exact_point_selected", sa.Boolean(), nullable=False),
        sa.Column("user_confirmed", sa.Boolean(), nullable=False),
        sa.Column("user_confirmed_safe_area", sa.Boolean(), nullable=False),
        sa.Column("distance_from_approximate_m", sa.Numeric(12, 2)),
        sa.Column("distance_from_base_m", sa.Numeric(12, 2), nullable=False),
        sa.CheckConstraint("final_latitude BETWEEN -90 AND 90", name="ck_point_final_latitude"),
        sa.CheckConstraint("final_longitude BETWEEN -180 AND 180", name="ck_point_final_longitude"),
        *_timestamps(),
    )
    op.create_index("ix_delivery_points_user_id", "delivery_points", ["user_id"])
    op.create_index(
        "ix_delivery_points_location_gist",
        "delivery_points",
        ["location"],
        postgresql_using="gist",
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "customer_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "delivery_point_id",
            sa.Uuid(),
            sa.ForeignKey("delivery_points.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                *[
                    s
                    for s in (
                        "DRAFT",
                        "PENDING_ADMIN_APPROVAL",
                        "APPROVED",
                        "REJECTED",
                        "MISSION_PREPARING",
                        "MISSION_READY",
                        "WAITING_FLIGHT_AUTHORIZATION",
                        "MISSION_UPLOADING",
                        "IN_TRANSIT",
                        "AT_DESTINATION",
                        "DELIVERED",
                        "RETURNING",
                        "COMPLETED",
                        "CANCELLED",
                        "FAILED",
                    )
                ],
                name="order_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "payment_method",
            sa.Enum("CREDIT_CARD", "PIX", name="payment_method", native_enum=False),
            nullable=False,
        ),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("delivery_fee", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount", sa.Numeric(12, 2), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "subtotal >= 0 AND delivery_fee >= 0 AND discount >= 0 AND total >= 0",
            name="ck_order_amounts_nonnegative",
        ),
        *_timestamps(),
    )
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"])
    op.create_index("ix_orders_delivery_point_id", "orders", ["delivery_point_id"])
    op.create_index("ix_orders_status", "orders", ["status"])

    op.create_table(
        "order_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "order_id", sa.Uuid(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "product_id",
            sa.Uuid(),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("product_name", sa.String(120), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("line_total", sa.Numeric(12, 2), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_order_item_quantity_positive"),
        sa.CheckConstraint(
            "unit_price >= 0 AND line_total >= 0", name="ck_order_item_values_nonnegative"
        ),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])

    op.create_table(
        "admin_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "order_id", sa.Uuid(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "administrator_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "decision",
            sa.Enum("APPROVED", "REJECTED", name="admin_decision_type", native_enum=False),
            nullable=False,
        ),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_admin_decisions_order_id", "admin_decisions", ["order_id"])
    op.create_index("ix_admin_decisions_administrator_id", "admin_decisions", ["administrator_id"])

    mission_values = (
        "DRAFT",
        "PENDING_VALIDATION",
        "GENERATED",
        "EXPORTED_TO_MISSION_PLANNER",
        "UNDER_REVIEW",
        "READY_FOR_AUTHORIZATION",
        "AUTHORIZED",
        "UPLOADING",
        "UPLOADED",
        "EXECUTING",
        "DESTINATION_REACHED",
        "DELIVERY_CONFIRMED",
        "RETURNING",
        "COMPLETED",
        "ABORTED",
        "FAILED",
    )
    op.create_table(
        "missions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "order_id",
            sa.Uuid(),
            sa.ForeignKey("orders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("vehicle_id", sa.Uuid(), sa.ForeignKey("vehicles.id", ondelete="RESTRICT")),
        sa.Column(
            "status",
            sa.Enum(*mission_values, name="mission_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("origin_latitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("origin_longitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("origin", GeographyPoint(), nullable=False),
        sa.Column("destination_latitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("destination_longitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("destination", GeographyPoint(), nullable=False),
        sa.Column("takeoff_altitude_m", sa.Numeric(8, 2), nullable=False),
        sa.Column("estimated_distance_m", sa.Numeric(12, 2), nullable=False),
        sa.Column("mission_file", sa.Text(), nullable=False),
        sa.Column("mission_sha256", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("exported_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_notes", sa.Text()),
        sa.Column("claimed_by_gateway", sa.String(120)),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("order_id", name="uq_missions_order_id"),
        *_timestamps(),
    )
    op.create_index("ix_missions_order_id", "missions", ["order_id"])
    op.create_index("ix_missions_vehicle_id", "missions", ["vehicle_id"])
    op.create_index("ix_missions_status", "missions", ["status"])

    op.create_table(
        "mission_waypoints",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "mission_id",
            sa.Uuid(),
            sa.ForeignKey("missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("command", sa.Integer(), nullable=False),
        sa.Column("frame", sa.Integer(), nullable=False),
        sa.Column("current", sa.Integer(), nullable=False),
        sa.Column("autocontinue", sa.Integer(), nullable=False),
        sa.Column("param1", sa.Float(), nullable=False),
        sa.Column("param2", sa.Float(), nullable=False),
        sa.Column("param3", sa.Float(), nullable=False),
        sa.Column("param4", sa.Float(), nullable=False),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("altitude_m", sa.Numeric(8, 2), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.UniqueConstraint("mission_id", "sequence", name="uq_waypoint_sequence"),
    )
    op.create_index("ix_mission_waypoints_mission_id", "mission_waypoints", ["mission_id"])

    op.create_table(
        "flight_authorizations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "mission_id",
            sa.Uuid(),
            sa.ForeignKey("missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "administrator_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "vehicle_health_snapshot_id",
            sa.Uuid(),
            sa.ForeignKey("vehicle_health_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "ACTIVE",
                "CONSUMED",
                "EXPIRED",
                "REVOKED",
                name="authorization_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("mission_version", sa.Integer(), nullable=False),
        sa.Column("mission_sha256", sa.String(64), nullable=False),
        sa.Column("checklist", sa.JSON(), nullable=False),
        sa.Column("controlled_area_confirmed", sa.Boolean(), nullable=False),
        sa.Column("operator_name", sa.String(120), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_flight_authorizations_mission_id", "flight_authorizations", ["mission_id"])
    op.create_index("ix_flight_authorizations_status", "flight_authorizations", ["status"])

    op.create_table(
        "gateway_commands",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "mission_id",
            sa.Uuid(),
            sa.ForeignKey("missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "requested_by_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "command",
            sa.Enum("ABORT", "RTL", name="gateway_command_type", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "ACKNOWLEDGED",
                "COMPLETED",
                "FAILED",
                name="gateway_command_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("gateway_id", sa.String(120)),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("result_detail", sa.Text()),
    )
    op.create_index("ix_gateway_commands_mission_id", "gateway_commands", ["mission_id"])
    op.create_index("ix_gateway_commands_status", "gateway_commands", ["status"])

    op.create_table(
        "telemetry_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_id", sa.String(120), nullable=False),
        sa.Column(
            "mission_id",
            sa.Uuid(),
            sa.ForeignKey("missions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "vehicle_id",
            sa.Uuid(),
            sa.ForeignKey("vehicles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("relative_altitude_m", sa.Float(), nullable=False),
        sa.Column("ground_speed_m_s", sa.Float(), nullable=False),
        sa.Column("battery_percent", sa.Float(), nullable=False),
        sa.Column("gps_fix_type", sa.Integer(), nullable=False),
        sa.Column("satellites", sa.Integer(), nullable=False),
        sa.Column("flight_mode", sa.String(40), nullable=False),
        sa.Column("armed", sa.Boolean(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id", name="uq_telemetry_logs_event_id"),
    )
    op.create_index("ix_telemetry_logs_event_id", "telemetry_logs", ["event_id"])
    op.create_index("ix_telemetry_logs_mission_id", "telemetry_logs", ["mission_id"])
    op.create_index("ix_telemetry_logs_vehicle_id", "telemetry_logs", ["vehicle_id"])
    op.create_index("ix_telemetry_logs_recorded_at", "telemetry_logs", ["recorded_at"])

    op.create_table(
        "system_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_id", sa.String(120)),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("actor_type", sa.String(30), nullable=False),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("orders.id")),
        sa.Column("mission_id", sa.Uuid(), sa.ForeignKey("missions.id")),
        sa.Column("vehicle_id", sa.Uuid(), sa.ForeignKey("vehicles.id")),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column(
            "severity",
            sa.Enum(
                "INFO", "WARNING", "ERROR", "CRITICAL", name="event_severity", native_enum=False
            ),
            nullable=False,
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id", name="uq_system_events_event_id"),
    )
    for column in (
        "event_id",
        "actor_user_id",
        "order_id",
        "mission_id",
        "vehicle_id",
        "event_type",
        "created_at",
    ):
        op.create_index(f"ix_system_events_{column}", "system_events", [column])


def downgrade() -> None:
    for table in (
        "system_events",
        "telemetry_logs",
        "gateway_commands",
        "flight_authorizations",
        "mission_waypoints",
        "missions",
        "admin_decisions",
        "order_items",
        "orders",
        "delivery_points",
        "vehicle_health_snapshots",
        "vehicles",
        "products",
        "idempotency_records",
        "users",
    ):
        op.drop_table(table)
