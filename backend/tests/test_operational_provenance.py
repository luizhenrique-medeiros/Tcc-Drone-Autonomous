from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.enums import OperationalSource
from app.modules.telemetry.models import TelemetryLog
from app.modules.telemetry.service import telemetry_is_stale
from app.modules.vehicles.models import VehicleHealthSnapshot
from app.modules.vehicles.schemas import VehicleHealthInput
from app.modules.vehicles.service import _critical_hash, health_to_read


def test_health_preserves_unreceived_mavlink_values_as_null(
    client: TestClient,
    gateway_headers: dict[str, str],
    admin_headers: dict[str, str],
) -> None:
    response = client.post(
        "/api/v1/gateway/heartbeat",
        headers=gateway_headers,
        json={
            "gateway_id": "gateway-sitl-null",
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

    health = client.get(
        f"/api/v1/admin/vehicles/{body['vehicle']['id']}/health",
        headers=admin_headers,
    )
    assert health.status_code == 200, health.text
    assert health.json()["gps_fix_type"] is None
    assert health.json()["received_at"]


def test_unknown_source_blocks_authorization_and_changes_critical_hash(
    client: TestClient, gateway_headers: dict[str, str]
) -> None:
    base_payload = {
        "gateway_id": "gateway-source-check",
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
