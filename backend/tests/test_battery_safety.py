import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.modules.vehicles.schemas import VehicleHealthInput
from app.modules.vehicles.service import _critical_hash


def battery_payload(percentage: float | None) -> dict[str, object]:
    return {
        "gateway_id": "gateway-sitl-1",
        "vehicle_identifier": "battery-contract-test",
        "source": "HARDWARE_REAL",
        "connected": True,
        "heartbeat": True,
        "gps_fix_type": 3,
        "satellites": 16,
        "ekf_ok": True,
        "battery_percent": percentage,
        "battery_voltage": 15.5,
        "flight_mode": "STABILIZE",
        "armed": False,
        "preflight_ok": True,
        "rtl_configured": True,
        "geofence_enabled": True,
        "origin_latitude": -23.1175,
        "origin_longitude": -46.5502,
    }


@pytest.mark.parametrize(
    "percentage",
    [None, 0, 10, 20, 25, 39.9, 40, 100],
)
def test_heartbeat_preserves_battery_without_site_block(
    client: TestClient,
    gateway_headers: dict[str, str],
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    percentage: float | None,
) -> None:
    monkeypatch.setattr(get_settings(), "min_battery_percent", 40)
    response = client.post(
        "/api/v1/gateway/heartbeat",
        headers=gateway_headers,
        json=battery_payload(percentage),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["health"]["battery_percent"] == percentage
    assert body["authorization_eligible"] is False
    assert body["failures"] == ["HARDWARE_OBSERVATION_ONLY"]
    health = client.get(
        f"/api/v1/admin/vehicles/{body['vehicle']['id']}/health", headers=admin_headers
    )
    assert health.status_code == 200
    assert health.json()["battery_percent"] == percentage
    assert health.json()["authorization_limits"]["min_battery_percent"] == 40


@pytest.mark.parametrize("percentage", [-1, 101, float("nan"), float("inf")])
def test_invalid_battery_cannot_be_replaced_with_full_charge(percentage: float) -> None:
    with pytest.raises(ValidationError):
        VehicleHealthInput.model_validate(battery_payload(percentage))


def test_default_battery_threshold_is_restored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MIN_BATTERY_PERCENT", raising=False)
    assert Settings(_env_file=None).min_battery_percent == 40


def test_battery_changes_do_not_invalidate_site_health_hash() -> None:
    payload = VehicleHealthInput.model_validate(battery_payload(90))
    assert _critical_hash(payload) == _critical_hash(
        payload.model_copy(update={"battery_percent": None})
    )
