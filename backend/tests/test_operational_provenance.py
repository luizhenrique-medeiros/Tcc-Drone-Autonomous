from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.enums import OperationalSource
from app.modules.telemetry.models import TelemetryLog
from app.modules.telemetry.schemas import TelemetryCreate
from app.modules.telemetry.service import telemetry_is_stale
from app.modules.vehicles.models import VehicleHealthSnapshot
from app.modules.vehicles.schemas import VehicleHealthInput
from app.modules.vehicles.service import _critical_hash, health_to_read


def test_gateway_authentication_binds_key_and_configured_identity(
    client: TestClient,
) -> None:
    payload = {
        "gateway_id": "gateway-sitl-1",
        "vehicle_identifier": "identity-check-vehicle",
        "source": "SITL",
        "connected": True,
        "heartbeat": True,
    }
    missing_identity = client.post(
        "/api/v1/gateway/heartbeat",
        headers={"X-Gateway-API-Key": "test-gateway-key"},
        json=payload,
    )
    assert missing_identity.status_code == 401

    forged_identity = client.post(
        "/api/v1/gateway/heartbeat",
        headers={
            "X-Gateway-API-Key": "test-gateway-key",
            "X-Gateway-ID": "outro-gateway",
        },
        json={**payload, "gateway_id": "outro-gateway"},
    )
    assert forged_identity.status_code == 401

    mismatched_body = client.post(
        "/api/v1/gateway/heartbeat",
        headers={
            "X-Gateway-API-Key": "test-gateway-key",
            "X-Gateway-ID": "gateway-sitl-1",
        },
        json={**payload, "gateway_id": "outro-gateway"},
    )
    assert mismatched_body.status_code == 403


def test_health_preserves_unreceived_mavlink_values_as_null(
    client: TestClient,
    gateway_headers: dict[str, str],
    admin_headers: dict[str, str],
) -> None:
    response = client.post(
        "/api/v1/gateway/heartbeat",
        headers=gateway_headers,
        json={
            "gateway_id": "gateway-sitl-1",
            "vehicle_identifier": "sitl-null-values",
            "vehicle_name": "SITL aguardando dados",
            "autopilot_system": "ArduPilot",
            "source": "SITL",
            "connected": True,
            "heartbeat": True,
            "gps_fix_type": None,
            "satellites": None,
            "ekf_ok": None,
            "battery_percent": None,
            "battery_voltage": None,
            "flight_mode": None,
            "armed": None,
            "preflight_ok": None,
            "rtl_configured": None,
            "geofence_enabled": None,
            "origin_latitude": None,
            "origin_longitude": None,
            "connection_state": None,
            "connection_mode": None,
            "connection_topology": None,
            "connection_endpoint": None,
            "serial_port": None,
            "connection_baud": None,
            "mavlink_system_id": None,
            "mavlink_component_id": None,
            "heartbeat_age_seconds": None,
            "last_heartbeat_at": None,
            "current_latitude": None,
            "current_longitude": None,
            "current_altitude_m": None,
            "mission_upload_enabled": None,
            "flight_commands_enabled": None,
            "mission_start_enabled": None,
            "vehicle_arm_enabled": None,
            "connection_error": None,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["authorization_eligible"] is False
    assert "GPS_NOT_RECEIVED" in body["failures"]
    assert "BATTERY_NOT_RECEIVED" in body["failures"]
    assert body["health"]["gps_fix_type"] is None
    assert body["health"]["armed"] is None
    assert body["health"]["source"] == "SITL"
    assert body["health"]["is_stale"] is False
    assert body["health"]["received_at"] == body["health"]["captured_at"]
    assert body["health"]["connection_endpoint"] is None
    assert body["health"]["serial_port"] is None
    assert body["health"]["heartbeat_age_seconds"] is None
    assert body["health"]["mission_upload_enabled"] is None
    assert body["health"]["mission_start_enabled"] is None
    assert body["health"]["vehicle_arm_enabled"] is None

    health = client.get(
        f"/api/v1/admin/vehicles/{body['vehicle']['id']}/health",
        headers=admin_headers,
    )
    assert health.status_code == 200, health.text
    assert health.json()["gps_fix_type"] is None
    assert health.json()["received_at"]


def test_health_persists_and_exposes_sanitized_integration_diagnostics(
    client: TestClient,
    gateway_headers: dict[str, str],
    admin_headers: dict[str, str],
) -> None:
    last_heartbeat_at = datetime.now(UTC) - timedelta(milliseconds=400)
    response = client.post(
        "/api/v1/gateway/heartbeat",
        headers=gateway_headers,
        json={
            "gateway_id": "gateway-sitl-1",
            "vehicle_identifier": "pixhawk-6c-real",
            "vehicle_name": "Drone Pixhawk 6C",
            "autopilot_system": "ArduPilot",
            "autopilot_version": "ArduCopter 4.6",
            "source": "HARDWARE_REAL",
            "connected": True,
            "heartbeat": True,
            "gps_fix_type": 3,
            "satellites": 14,
            "ekf_ok": True,
            "battery_percent": 88,
            "battery_voltage": 15.7,
            "flight_mode": "GUIDED",
            "armed": False,
            "preflight_ok": True,
            "rtl_configured": True,
            "geofence_enabled": True,
            "origin_latitude": -23.1175,
            "origin_longitude": -46.5502,
            "connection_state": "CONNECTED",
            "connection_mode": "FORWARD",
            "connection_topology": "MISSION_PLANNER_FORWARDING",
            "connection_endpoint": "udp://operator:secret@127.0.0.1:14550?token=hidden",
            "serial_port": "COM7",
            "connection_baud": 57600,
            "mavlink_system_id": 1,
            "mavlink_component_id": 1,
            "heartbeat_age_seconds": 0.4,
            "last_heartbeat_at": last_heartbeat_at.isoformat(),
            "current_latitude": -23.11872,
            "current_longitude": -46.58131,
            "current_altitude_m": 12.5,
            "mission_upload_enabled": False,
            "flight_commands_enabled": False,
            "mission_start_enabled": False,
            "vehicle_arm_enabled": False,
            "connection_error": None,
        },
    )

    assert response.status_code == 200, response.text
    vehicle_id = response.json()["vehicle"]["id"]
    health = client.get(
        f"/api/v1/admin/vehicles/{vehicle_id}/health",
        headers=admin_headers,
    )

    assert health.status_code == 200, health.text
    body = health.json()
    assert body["connection_state"] == "CONNECTED"
    assert body["connection_mode"] == "FORWARD"
    assert body["connection_topology"] == "MISSION_PLANNER_FORWARDING"
    assert body["connection_endpoint"] == "udp://127.0.0.1:14550"
    assert body["serial_port"] == "COM7"
    assert body["connection_baud"] == 57600
    assert body["mavlink_system_id"] == 1
    assert body["mavlink_component_id"] == 1
    assert 0 <= body["heartbeat_age_seconds"] < 10
    assert body["last_heartbeat_at"]
    assert float(body["current_latitude"]) == -23.11872
    assert float(body["current_longitude"]) == -46.58131
    assert body["current_altitude_m"] == 12.5
    assert body["mission_upload_enabled"] is False
    assert body["flight_commands_enabled"] is False
    assert body["mission_start_enabled"] is False
    assert body["vehicle_arm_enabled"] is False
    assert body["connection_error"] is None
    vehicles = client.get("/api/v1/admin/vehicles", headers=admin_headers)
    assert vehicles.status_code == 200
    listed = next(item for item in vehicles.json() if item["id"] == vehicle_id)
    assert listed["gateway_id"] == "gateway-sitl-1"
    assert listed["autopilot_system"] == "ArduPilot"
    assert listed["autopilot_version"] == "ArduCopter 4.6"
    assert listed["operational_source"] == "HARDWARE_REAL"

    unauthorized = client.get(f"/api/v1/admin/vehicles/{vehicle_id}/health")
    assert unauthorized.status_code == 401


def test_unknown_source_blocks_authorization_and_changes_critical_hash(
    client: TestClient, gateway_headers: dict[str, str]
) -> None:
    base_payload = {
        "gateway_id": "gateway-sitl-1",
        "vehicle_identifier": "source-check-vehicle",
        "vehicle_name": "Source check",
        "autopilot_system": "ArduPilot",
        "connected": True,
        "heartbeat": True,
        "gps_fix_type": 3,
        "satellites": 14,
        "ekf_ok": True,
        "battery_percent": 90,
        "flight_mode": "AUTO",
        "armed": False,
        "preflight_ok": True,
        "rtl_configured": True,
        "geofence_enabled": True,
        "origin_latitude": -23.1175,
        "origin_longitude": -46.5502,
    }
    unknown = client.post("/api/v1/gateway/heartbeat", headers=gateway_headers, json=base_payload)
    assert unknown.status_code == 200, unknown.text
    assert "OPERATIONAL_SOURCE_UNKNOWN" in unknown.json()["failures"]

    unknown_model = VehicleHealthInput.model_validate(base_payload)
    sitl_model = VehicleHealthInput.model_validate({**base_payload, "source": "SITL"})
    assert _critical_hash(unknown_model) != _critical_hash(sitl_model)


def test_telemetry_freshness_is_recomputed_when_read() -> None:
    telemetry = TelemetryLog(
        received_at=datetime.now(UTC) - timedelta(seconds=11),
        is_stale=False,
    )
    settings = Settings(_env_file=None, heartbeat_timeout_seconds=10)

    assert telemetry_is_stale(telemetry, settings) is True


def test_health_and_telemetry_accept_all_standard_mavlink_gps_fix_types() -> None:
    health = VehicleHealthInput.model_validate(
        {
            "gateway_id": "gateway-gps-contract",
            "vehicle_identifier": "vehicle-gps-contract",
            "source": "SITL",
            "connected": True,
            "heartbeat": True,
            "gps_fix_type": 8,
        }
    )
    telemetry = TelemetryCreate(
        event_id="gps-fix-type-8",
        vehicle_id=uuid4(),
        source=OperationalSource.SITL,
        latitude=-23.1175,
        longitude=-46.5502,
        relative_altitude_m=0,
        ground_speed_m_s=0,
        gps_fix_type=8,
    )

    assert health.gps_fix_type == 8
    assert telemetry.gps_fix_type == 8


def test_health_contract_exposes_configured_authorization_limits() -> None:
    now = datetime.now(UTC)
    snapshot = VehicleHealthSnapshot(
        id=uuid4(),
        vehicle_id=uuid4(),
        connected=True,
        heartbeat=True,
        source=OperationalSource.SITL,
        gps_fix_type=3,
        satellites=20,
        ekf_ok=True,
        battery_percent=90,
        battery_voltage=15.8,
        flight_mode="GUIDED",
        armed=False,
        preflight_ok=True,
        rtl_configured=True,
        geofence_enabled=True,
        origin_latitude=-23.1175,
        origin_longitude=-46.5502,
        critical_state_hash="a" * 64,
        captured_at=now,
        received_at=now,
    )
    settings = Settings(
        _env_file=None,
        min_battery_percent=73,
        min_gps_satellites=19,
    )

    health = health_to_read(snapshot, settings)

    assert health.authorization_limits.model_dump() == {
        "min_battery_percent": 73.0,
        "battery_warning_percent": 83.0,
        "min_gps_satellites": 19,
    }
