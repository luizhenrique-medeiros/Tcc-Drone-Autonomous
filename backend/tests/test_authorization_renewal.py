from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.core.enums import GatewayCommandStatus, GatewayCommandType
from app.database.session import SessionLocal
from app.modules.approvals.models import FlightAuthorization
from app.modules.missions.models import GatewayCommand, Mission


@pytest.fixture
def verified(client, customer_headers, admin_headers, gateway_headers, valid_point_payload):
    point = client.post(
        "/api/v1/delivery-points", headers=customer_headers, json=valid_point_payload
    ).json()
    product = client.get("/api/v1/products", headers=customer_headers).json()[0]
    order = client.post(
        "/api/v1/orders",
        headers=customer_headers,
        json={
            "delivery_point_id": point["id"],
            "payment_method": "PIX",
            "items": [{"product_id": product["id"], "quantity": 1}],
        },
    ).json()
    assert (
        client.post(f"/api/v1/orders/{order['id']}/submit", headers=customer_headers).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/admin/orders/{order['id']}/approve", headers=admin_headers, json={}
        ).status_code
        == 200
    )
    mission = client.post(
        f"/api/v1/admin/orders/{order['id']}/prepare-mission", headers=admin_headers
    ).json()
    path = f"/api/v1/admin/missions/{mission['id']}"
    assert client.get(path + "/export", headers=admin_headers).status_code == 200
    assert client.post(path + "/mark-under-review", headers=admin_headers).status_code == 200
    assert client.post(path + "/mark-reviewed", headers=admin_headers, json={}).status_code == 200
    health = {
        "gateway_id": "gateway-sitl-1",
        "vehicle_identifier": "renewal-test",
        "vehicle_name": "SITL fixture",
        "autopilot_system": "ArduPilot",
        "source": "SITL",
        "connected": True,
        "heartbeat": True,
        "gps_fix_type": 3,
        "satellites": 14,
        "ekf_ok": True,
        "battery_percent": 90,
        "battery_voltage": 16,
        "flight_mode": "STABILIZE",
        "armed": False,
        "preflight_ok": True,
        "rtl_configured": True,
        "geofence_enabled": True,
        "origin_latitude": -23.1175,
        "origin_longitude": -46.5502,
        "flight_commands_enabled": True,
        "mission_start_enabled": True,
        "vehicle_arm_enabled": True,
    }
    snapshot = client.post("/api/v1/gateway/heartbeat", headers=gateway_headers, json=health)
    assert snapshot.status_code == 200, snapshot.text
    payload = {
        "vehicle_id": snapshot.json()["vehicle"]["id"],
        "operator_name": "Luiz Teste",
        "controlled_area_confirmed": True,
        "checklist": {
            "area_and_conditions_clear": True,
            "aircraft_and_payload_inspected": True,
            "operator_ready": True,
        },
    }
    auth = client.post(path + "/authorize-flight", headers=admin_headers, json=payload)
    assert auth.status_code == 200, auth.text
    gateway_path = f"/api/v1/gateway/missions/{mission['id']}"
    claim = client.post(
        gateway_path + "/claim", headers=gateway_headers, json={"gateway_id": "gateway-sitl-1"}
    )
    assert claim.status_code == 200, claim.text
    for state in ("UPLOADED", "VERIFIED"):
        result = client.post(
            gateway_path + "/upload-status",
            headers=gateway_headers,
            json={"event_id": str(uuid4()), "status": state},
        )
        assert result.status_code == 200, result.text
    with SessionLocal() as session:
        record = session.get(FlightAuthorization, UUID(auth.json()["authorization"]["id"]))
        record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    return path, gateway_path, payload, health, claim.json()


def test_renewal_preserves_verified_artifact_and_consumed_history(
    client, admin_headers, gateway_headers, verified
):
    path, gateway_path, payload, _, original = verified
    for action in ("arm", "commands/START"):
        body = {"reason": "Teste local de autorizacao"}
        if action == "arm":
            body.update(
                area_clear_confirmed=True,
                operator_present_confirmed=True,
                safety_switch_ready_confirmed=True,
            )
        blocked = client.post(
            path + "/" + action,
            headers={**admin_headers, "Idempotency-Key": "expired-" + action},
            json=body,
        )
        assert blocked.status_code == 409, blocked.text
        assert "expirou" in blocked.json()["detail"]
    headers = {**admin_headers, "Idempotency-Key": "renewal-attempt-001"}
    renewed = client.post(path + "/authorize-flight", headers=headers, json=payload)
    assert renewed.status_code == 200, renewed.text
    assert renewed.json()["mission"]["status"] == "VERIFIED"
    assert renewed.json()["authorization"]["status"] == "CONSUMED"
    assert renewed.json()["authorization"]["id"] != original["authorization_id"]
    replay = client.post(path + "/authorize-flight", headers=headers, json=payload)
    assert replay.json() == renewed.json()
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert (
        client.post(path + "/authorize-flight", headers=admin_headers, json=payload).status_code
        == 409
    )
    fresh = client.post(
        gateway_path + "/claim", headers=gateway_headers, json={"gateway_id": "gateway-sitl-1"}
    )
    assert fresh.status_code == 200, fresh.text
    assert fresh.json()["mission"]["status"] == "VERIFIED"
    assert fresh.json()["mission_file"] == original["mission_file"]
    assert fresh.json()["mission"]["mission_sha256"] == original["mission"]["mission_sha256"]
    assert fresh.json()["authorization_id"] == renewed.json()["authorization"]["id"]
    assert client.get("/api/v1/gateway/missions/authorized", headers=gateway_headers).json() == []
    assert (
        client.get(
            "/api/v1/gateway/commands/pending?gateway_id=gateway-sitl-1", headers=gateway_headers
        ).json()
        == []
    )
    with SessionLocal() as session:
        old = session.get(FlightAuthorization, UUID(original["authorization_id"]))
        assert old.status.value == "CONSUMED"
        expiry = old.expires_at.replace(tzinfo=UTC)
        assert expiry < datetime.now(UTC)


@pytest.mark.parametrize(
    "fault",
    [
        "armed",
        "preflight",
        "checklist",
        "vehicle",
        "version",
        "hash",
        "gateway",
        "pending",
        "acknowledged",
    ],
)
def test_renewal_fails_closed(client, admin_headers, gateway_headers, verified, fault):
    path, _, payload, health, original = verified
    if fault in ("armed", "preflight"):
        health["armed" if fault == "armed" else "preflight_ok"] = fault == "armed"
        client.post("/api/v1/gateway/heartbeat", headers=gateway_headers, json=health)
    elif fault == "checklist":
        payload["checklist"]["operator_ready"] = False
    elif fault == "vehicle":
        payload["vehicle_id"] = str(uuid4())
    else:
        with SessionLocal() as session:
            mission = session.get(Mission, UUID(original["mission"]["id"]))
            if fault == "version":
                mission.version += 1
            elif fault == "hash":
                mission.mission_sha256 = "0" * 64
            elif fault == "gateway":
                mission.claimed_by_gateway = "another-gateway"
            else:
                auth = session.get(FlightAuthorization, UUID(original["authorization_id"]))
                session.add(
                    GatewayCommand(
                        mission_id=mission.id,
                        requested_by_id=auth.administrator_id,
                        command=GatewayCommandType.ARM,
                        status=GatewayCommandStatus.PENDING
                        if fault == "pending"
                        else GatewayCommandStatus.ACKNOWLEDGED,
                    )
                )
            session.commit()
    result = client.post(path + "/authorize-flight", headers=admin_headers, json=payload)
    assert result.status_code == 409, result.text


def test_verified_mission_is_restored_on_customer_socket_reconnect(
    client, customer_headers, gateway_headers, verified
):
    _, _, _, _, original = verified
    mission = original["mission"]
    order_id = mission["order_id"]
    token = customer_headers["Authorization"].removeprefix("Bearer ")
    for _ in range(2):
        with client.websocket_connect(f"/api/v1/ws/orders/{order_id}") as websocket:
            websocket.send_json({"type": "AUTH", "token": token})
            assert websocket.receive_json()["type"] == "order.snapshot"
            # A missing mission snapshot returns pong, so the regression cannot hang.
            websocket.send_text("ping")
            snapshot = websocket.receive_json()
            assert snapshot["type"] == "mission.status"
            assert snapshot["data"]["id"] == mission["id"]
            assert snapshot["data"]["status"] == "VERIFIED"
            assert snapshot["data"]["mission_sha256"] == mission["mission_sha256"]
            assert snapshot["data"]["updated_at"]
            assert websocket.receive_json() == {"type": "pong"}
    assert (
        client.get(
            "/api/v1/gateway/commands/pending?gateway_id=gateway-sitl-1", headers=gateway_headers
        ).json()
        == []
    )
