from __future__ import annotations

from fastapi.testclient import TestClient


def _create_submitted_order(
    client: TestClient,
    customer_headers: dict[str, str],
    point_payload: dict[str, object],
) -> dict[str, object]:
    point = client.post("/api/v1/delivery-points", json=point_payload, headers=customer_headers)
    assert point.status_code == 201, point.text
    products = client.get("/api/v1/products", headers=customer_headers)
    assert products.status_code == 200
    order = client.post(
        "/api/v1/orders",
        headers=customer_headers,
        json={
            "delivery_point_id": point.json()["id"],
            "payment_method": "PIX",
            "items": [{"product_id": products.json()[0]["id"], "quantity": 1}],
        },
    )
    assert order.status_code == 201, order.text
    assert order.json()["status"] == "DRAFT"
    submitted = client.post(f"/api/v1/orders/{order.json()['id']}/submit", headers=customer_headers)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "PENDING_ADMIN_APPROVAL"
    return submitted.json()


def test_two_approvals_mission_claim_and_gateway_idempotency(
    client: TestClient,
    customer_headers: dict[str, str],
    admin_headers: dict[str, str],
    gateway_headers: dict[str, str],
    valid_point_payload: dict[str, object],
) -> None:
    order = _create_submitted_order(client, customer_headers, valid_point_payload)

    forbidden = client.post(
        f"/api/v1/admin/orders/{order['id']}/approve",
        headers=customer_headers,
        json={},
    )
    assert forbidden.status_code == 403

    approved = client.post(
        f"/api/v1/admin/orders/{order['id']}/approve",
        headers=admin_headers,
        json={"reason": "Área adequada para a demonstração"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"

    mission_response = client.post(
        f"/api/v1/admin/orders/{order['id']}/prepare-mission", headers=admin_headers
    )
    assert mission_response.status_code == 201, mission_response.text
    mission = mission_response.json()
    assert mission["status"] == "GENERATED"
    assert [waypoint["label"] for waypoint in mission["waypoints"]] == [
        "Origem",
        "Decolagem",
        "Destino",
        "Espera para entrega",
        "Entrega",
        "Retorno",
        "Pouso",
    ]

    export = client.get(f"/api/v1/admin/missions/{mission['id']}/export", headers=admin_headers)
    assert export.status_code == 200
    assert export.text.startswith("QGC WPL 110\n")
    assert export.headers["x-mission-sha256"] == mission["mission_sha256"]

    under_review = client.post(
        f"/api/v1/admin/missions/{mission['id']}/mark-under-review",
        headers=admin_headers,
    )
    assert under_review.status_code == 200, under_review.text
    reviewed = client.post(
        f"/api/v1/admin/missions/{mission['id']}/mark-reviewed",
        headers=admin_headers,
        json={"notes": "Rota conferida visualmente"},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "READY_FOR_AUTHORIZATION"

    heartbeat_payload = {
        "gateway_id": "gateway-sitl-1",
        "vehicle_identifier": "sitl-copter-1",
        "vehicle_name": "Copter SITL",
        "autopilot_system": "ArduPilot",
        "autopilot_version": "4.5.7",
        "source": "SITL",
        "connected": True,
        "heartbeat": True,
        "gps_fix_type": 3,
        "satellites": 14,
        "ekf_ok": True,
        "battery_percent": 88,
        "battery_voltage": 15.8,
        "flight_mode": "GUIDED",
        "armed": False,
        "preflight_ok": True,
        "rtl_configured": True,
        "geofence_enabled": True,
        "origin_latitude": -23.1175,
        "origin_longitude": -46.5502,
    }
    heartbeat = client.post(
        "/api/v1/gateway/heartbeat", headers=gateway_headers, json=heartbeat_payload
    )
    assert heartbeat.status_code == 200, heartbeat.text
    assert heartbeat.json()["authorization_eligible"] is True
    assert heartbeat.json()["health"]["source"] == "SITL"
    assert heartbeat.json()["health"]["is_stale"] is False
    assert heartbeat.json()["health"]["received_at"]
    assert heartbeat.json()["vehicle"]["operational_source"] == "SITL"
    vehicle_id = heartbeat.json()["vehicle"]["id"]

    authorization = client.post(
        f"/api/v1/admin/missions/{mission['id']}/authorize-flight",
        headers=admin_headers,
        json={
            "vehicle_id": vehicle_id,
            "operator_name": "Operador de teste",
            "controlled_area_confirmed": True,
            "checklist": {
                "mission_planner_reviewed": True,
                "controlled_area_secured": True,
                "operator_ready": True,
                "payload_secured": True,
                "weather_checked": True,
            },
        },
    )
    assert authorization.status_code == 200, authorization.text
    assert authorization.json()["mission"]["status"] == "AUTHORIZED"
    assert authorization.json()["authorization"]["status"] == "ACTIVE"

    available = client.get("/api/v1/gateway/missions/authorized", headers=gateway_headers)
    assert available.status_code == 200
    assert [item["id"] for item in available.json()] == [mission["id"]]

    claim = client.post(
        f"/api/v1/gateway/missions/{mission['id']}/claim",
        headers=gateway_headers,
        json={"gateway_id": "gateway-sitl-1"},
    )
    assert claim.status_code == 200, claim.text
    assert claim.json()["mission"]["status"] == "UPLOADING"
    assert claim.json()["mission_file"].startswith("QGC WPL 110")
    second_claim = client.post(
        f"/api/v1/gateway/missions/{mission['id']}/claim",
        headers=gateway_headers,
        json={"gateway_id": "gateway-sitl-1"},
    )
    assert second_claim.status_code == 200
    assert second_claim.json()["authorization_id"] == claim.json()["authorization_id"]

    uploaded = client.post(
        f"/api/v1/gateway/missions/{mission['id']}/upload-status",
        headers=gateway_headers,
        json={"event_id": "upload-event-001", "status": "UPLOADED"},
    )
    assert uploaded.status_code == 200, uploaded.text
    duplicate = client.post(
        f"/api/v1/gateway/missions/{mission['id']}/upload-status",
        headers=gateway_headers,
        json={"event_id": "upload-event-001", "status": "UPLOADED"},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["status"] == "UPLOADED"

    executing = client.post(
        f"/api/v1/gateway/missions/{mission['id']}/status",
        headers=gateway_headers,
        json={"event_id": "status-event-001", "status": "EXECUTING"},
    )
    assert executing.status_code == 200, executing.text

    telemetry_payload = {
        "event_id": "telemetry-event-001",
        "vehicle_id": vehicle_id,
        "source": "SITL",
        "latitude": -23.1173,
        "longitude": -46.5501,
        "relative_altitude_m": 8.5,
        "ground_speed_m_s": 3.2,
        "battery_percent": 80,
        "gps_fix_type": 3,
        "satellites": 14,
        "flight_mode": "AUTO",
        "armed": True,
    }
    telemetry = client.post(
        f"/api/v1/gateway/missions/{mission['id']}/telemetry",
        headers=gateway_headers,
        json=telemetry_payload,
    )
    assert telemetry.status_code == 200, telemetry.text
    assert telemetry.json()["source"] == "SITL"
    assert telemetry.json()["received_at"]
    assert telemetry.json()["recorded_at"]
    assert telemetry.json()["is_stale"] is False
    duplicate_telemetry = client.post(
        f"/api/v1/gateway/missions/{mission['id']}/telemetry",
        headers=gateway_headers,
        json=telemetry_payload,
    )
    assert duplicate_telemetry.status_code == 200
    assert duplicate_telemetry.json()["id"] == telemetry.json()["id"]

    abort_headers = {**admin_headers, "Idempotency-Key": "admin-abort-flow-001"}
    abort_request = client.post(
        f"/api/v1/admin/missions/{mission['id']}/abort",
        headers=abort_headers,
        json={"reason": "Intervenção de segurança do teste"},
    )
    assert abort_request.status_code == 202
    abort_replay = client.post(
        f"/api/v1/admin/missions/{mission['id']}/abort",
        headers=abort_headers,
        json={"reason": "Intervenção de segurança do teste"},
    )
    assert abort_replay.status_code == 202
    assert abort_replay.json() == abort_request.json()
    assert abort_replay.headers["idempotency-replayed"] == "true"
    abort_mismatch = client.post(
        f"/api/v1/admin/missions/{mission['id']}/abort",
        headers=abort_headers,
        json={"reason": "Outro motivo"},
    )
    assert abort_mismatch.status_code == 409
    assert abort_mismatch.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    commands = client.get(
        "/api/v1/gateway/commands/pending?gateway_id=gateway-sitl-1",
        headers=gateway_headers,
    )
    assert commands.status_code == 200, commands.text
    assert len(commands.json()) == 1
    assert commands.json()[0]["command"] == "ABORT"
    assert commands.json()[0]["reason"] == "Intervenção de segurança do teste"
    command_id = commands.json()[0]["id"]
    ack = client.post(
        f"/api/v1/gateway/commands/{command_id}/ack",
        headers=gateway_headers,
        json={
            "event_id": "command-event-001",
            "gateway_id": "gateway-sitl-1",
            "status": "ACKNOWLEDGED",
        },
    )
    assert ack.status_code == 200, ack.text
    assert ack.json()["status"] == "ACKNOWLEDGED"


def test_rejection_requires_reason_and_is_audited(
    client: TestClient,
    customer_headers: dict[str, str],
    admin_headers: dict[str, str],
    valid_point_payload: dict[str, object],
) -> None:
    order = _create_submitted_order(client, customer_headers, valid_point_payload)
    missing_reason = client.post(
        f"/api/v1/admin/orders/{order['id']}/reject",
        headers=admin_headers,
        json={"reason": ""},
    )
    assert missing_reason.status_code == 422
    rejected = client.post(
        f"/api/v1/admin/orders/{order['id']}/reject",
        headers=admin_headers,
        json={"reason": "Há fios próximos ao ponto selecionado"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"
    assert rejected.json()["rejection_reason"].startswith("Há fios")
    events = client.get(f"/api/v1/admin/events?order_id={order['id']}", headers=admin_headers)
    assert events.status_code == 200
    assert "ORDER_REJECTED" in {event["event_type"] for event in events.json()}
