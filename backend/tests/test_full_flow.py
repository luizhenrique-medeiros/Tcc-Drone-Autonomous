from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from app.core.enums import AuthorizationStatus, MissionStatus
from app.database.session import SessionLocal
from app.modules.approvals.models import FlightAuthorization
from app.modules.missions.models import Mission


def _as_utc_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


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

    blank_operator = client.post(
        f"/api/v1/admin/missions/{mission['id']}/authorize-flight",
        headers={**admin_headers, "Idempotency-Key": "flight-authorization-blank"},
        json={
            "vehicle_id": vehicle_id,
            "operator_name": "   ",
            "controlled_area_confirmed": True,
            "checklist": {
                "area_and_conditions_clear": True,
                "aircraft_and_payload_inspected": True,
                "operator_ready": True,
            },
        },
    )
    assert blank_operator.status_code == 422

    authorization = client.post(
        f"/api/v1/admin/missions/{mission['id']}/authorize-flight",
        headers={**admin_headers, "Idempotency-Key": "flight-authorization-001"},
        json={
            "vehicle_id": vehicle_id,
            "operator_name": "Operador de teste",
            "controlled_area_confirmed": True,
            "checklist": {
                "area_and_conditions_clear": True,
                "aircraft_and_payload_inspected": True,
                "operator_ready": True,
            },
        },
    )
    assert authorization.status_code == 200, authorization.text
    assert authorization.json()["mission"]["status"] == "AUTHORIZED"
    assert authorization.json()["authorization"]["status"] == "ACTIVE"
    admin_identity = client.get("/api/v1/auth/me", headers=admin_headers)
    assert admin_identity.status_code == 200
    embedded_authorization = authorization.json()["mission"]["authorization"]
    assert embedded_authorization == {
        "id": authorization.json()["authorization"]["id"],
        "administrator_id": admin_identity.json()["id"],
        "administrator_name": admin_identity.json()["name"],
        "operator_name": "Operador de teste",
        "status": "ACTIVE",
        "mission_version": mission["version"],
        "issued_at": authorization.json()["authorization"]["issued_at"],
        "expires_at": authorization.json()["authorization"]["expires_at"],
        "used_at": None,
    }

    mission_after_reload = client.get(
        f"/api/v1/admin/missions/{mission['id']}", headers=admin_headers
    )
    assert mission_after_reload.status_code == 200
    assert mission_after_reload.json()["authorization"] == embedded_authorization
    mission_in_list = client.get("/api/v1/admin/missions", headers=admin_headers)
    assert mission_in_list.status_code == 200
    listed_mission = next(item for item in mission_in_list.json() if item["id"] == mission["id"])
    assert listed_mission["authorization"] == embedded_authorization

    authorization_replay = client.post(
        f"/api/v1/admin/missions/{mission['id']}/authorize-flight",
        headers={**admin_headers, "Idempotency-Key": "flight-authorization-001"},
        json={
            "vehicle_id": vehicle_id,
            "operator_name": "Operador de teste",
            "controlled_area_confirmed": True,
            "checklist": {
                "area_and_conditions_clear": True,
                "aircraft_and_payload_inspected": True,
                "operator_ready": True,
            },
        },
    )
    assert authorization_replay.status_code == 200
    assert authorization_replay.headers["idempotency-replayed"] == "true"
    assert (
        authorization_replay.json()["authorization"]["id"]
        == authorization.json()["authorization"]["id"]
    )

    duplicate_authorization = client.post(
        f"/api/v1/admin/missions/{mission['id']}/authorize-flight",
        headers={**admin_headers, "Idempotency-Key": "flight-authorization-002"},
        json={
            "vehicle_id": vehicle_id,
            "operator_name": "Operador de teste",
            "controlled_area_confirmed": True,
            "checklist": {
                "area_and_conditions_clear": True,
                "aircraft_and_payload_inspected": True,
                "operator_ready": True,
            },
        },
    )
    assert duplicate_authorization.status_code == 409

    with SessionLocal() as session:
        stored_mission = session.get(Mission, UUID(mission["id"]))
        assert stored_mission is not None
        stored_mission.version += 1
        session.commit()

    invalidated_claim = client.post(
        f"/api/v1/gateway/missions/{mission['id']}/claim",
        headers=gateway_headers,
        json={"gateway_id": "gateway-sitl-1"},
    )
    assert invalidated_claim.status_code == 409
    assert invalidated_claim.json()["detail"] == "A missão mudou após a autorização"

    with SessionLocal() as session:
        stored_mission = session.get(Mission, UUID(mission["id"]))
        stored_authorization = session.get(
            FlightAuthorization,
            UUID(authorization.json()["authorization"]["id"]),
        )
        assert stored_mission is not None
        assert stored_mission.status == MissionStatus.READY_FOR_AUTHORIZATION
    assert stored_authorization is not None
    assert stored_authorization.status == AuthorizationStatus.REVOKED

    invalidated_detail = client.get(
        f"/api/v1/admin/missions/{mission['id']}", headers=admin_headers
    )
    assert invalidated_detail.status_code == 200
    assert invalidated_detail.json()["authorization"]["status"] == "REVOKED"

    revocation_events = client.get(
        f"/api/v1/admin/events?mission_id={mission['id']}", headers=admin_headers
    )
    assert revocation_events.status_code == 200
    revoked = next(
        event
        for event in revocation_events.json()
        if event["event_type"] == "FLIGHT_AUTHORIZATION_REVOKED"
    )
    assert revoked["metadata"]["reason"] == "MISSION_VERSION_CHANGED"

    reauthorization = client.post(
        f"/api/v1/admin/missions/{mission['id']}/authorize-flight",
        headers={**admin_headers, "Idempotency-Key": "flight-authorization-003"},
        json={
            "vehicle_id": vehicle_id,
            "operator_name": "Operador de teste",
            "controlled_area_confirmed": True,
            "checklist": {
                "area_and_conditions_clear": True,
                "aircraft_and_payload_inspected": True,
                "operator_ready": True,
            },
        },
    )
    assert reauthorization.status_code == 200, reauthorization.text
    assert (
        reauthorization.json()["authorization"]["id"] != authorization.json()["authorization"]["id"]
    )
    reauthorized_detail = client.get(
        f"/api/v1/admin/missions/{mission['id']}", headers=admin_headers
    )
    assert reauthorized_detail.status_code == 200
    assert (
        reauthorized_detail.json()["authorization"]["id"]
        == (reauthorization.json()["authorization"]["id"])
    )
    assert reauthorized_detail.json()["authorization"]["status"] == "ACTIVE"

    wrong_gateway_claim = client.post(
        f"/api/v1/gateway/missions/{mission['id']}/claim",
        headers=gateway_headers,
        json={"gateway_id": "gateway-nao-vinculado"},
    )
    assert wrong_gateway_claim.status_code == 403

    available = client.get("/api/v1/gateway/missions/authorized", headers=gateway_headers)
    assert available.status_code == 200
    assert [item["id"] for item in available.json()] == [mission["id"]]

    # Mudanças normais de telemetria não revogam uma autorização enquanto
    # todas as condições técnicas continuam dentro dos limites seguros.
    changed_healthy_heartbeat = client.post(
        "/api/v1/gateway/heartbeat",
        headers=gateway_headers,
        json={**heartbeat_payload, "battery_percent": 87.5, "satellites": 15},
    )
    assert changed_healthy_heartbeat.status_code == 200
    assert changed_healthy_heartbeat.json()["authorization_eligible"] is True

    claim = client.post(
        f"/api/v1/gateway/missions/{mission['id']}/claim",
        headers=gateway_headers,
        json={"gateway_id": "gateway-sitl-1"},
    )
    assert claim.status_code == 200, claim.text
    assert claim.json()["mission"]["status"] == "UPLOADING"
    assert claim.json()["mission_file"].startswith("QGC WPL 110")
    consumed_detail = client.get(f"/api/v1/admin/missions/{mission['id']}", headers=admin_headers)
    assert consumed_detail.status_code == 200
    assert consumed_detail.json()["authorization"]["status"] == "CONSUMED"
    assert consumed_detail.json()["authorization"]["used_at"] is not None
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

    incompatible_upload_replay = client.post(
        f"/api/v1/gateway/missions/{mission['id']}/upload-status",
        headers=gateway_headers,
        json={"event_id": "upload-event-001", "status": "VERIFIED"},
    )
    assert incompatible_upload_replay.status_code == 409
    assert incompatible_upload_replay.json()["code"] == "EVENT_ID_REUSED"

    unverified_execution = client.post(
        f"/api/v1/gateway/missions/{mission['id']}/status",
        headers=gateway_headers,
        json={"event_id": "status-before-verification-001", "status": "EXECUTING"},
    )
    assert unverified_execution.status_code == 409
    assert unverified_execution.json()["code"] == "INVALID_STATE"

    verified = client.post(
        f"/api/v1/gateway/missions/{mission['id']}/upload-status",
        headers=gateway_headers,
        json={"event_id": "upload-event-verified-001", "status": "VERIFIED"},
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["status"] == "VERIFIED"
    order_after_verification = client.get(
        f"/api/v1/orders/{mission['order_id']}", headers=customer_headers
    )
    assert order_after_verification.status_code == 200
    assert order_after_verification.json()["status"] == "MISSION_UPLOADING"
    assert "MISSION_VERIFIED" in {
        milestone["event_type"] for milestone in order_after_verification.json()["milestones"]
    }

    arm_payload = {
        "reason": "Ensaio presencial em bancada isolada",
        "area_clear_confirmed": True,
        "operator_present_confirmed": True,
        "safety_switch_ready_confirmed": True,
    }
    arm_health_payload = {
        **heartbeat_payload,
        "flight_mode": "STABILIZE",
        "flight_commands_enabled": True,
        "mission_start_enabled": True,
        "vehicle_arm_enabled": True,
    }
    for gate, blocker in (
        ("vehicle_arm_enabled", "VEHICLE_ARM_DISABLED"),
        ("flight_commands_enabled", "FLIGHT_COMMANDS_DISABLED"),
        ("mission_start_enabled", "MISSION_START_DISABLED"),
    ):
        disabled_arm_heartbeat = client.post(
            "/api/v1/gateway/heartbeat",
            headers=gateway_headers,
            json={**arm_health_payload, gate: False},
        )
        assert disabled_arm_heartbeat.status_code == 200
        disabled_arm = client.post(
            f"/api/v1/admin/missions/{mission['id']}/arm",
            headers={**admin_headers, "Idempotency-Key": f"arm-disabled-{gate}-001"},
            json=arm_payload,
        )
        assert disabled_arm.status_code == 409
        assert blocker in disabled_arm.json()["fields"]["preflight"]

    invalid_mode_heartbeat = client.post(
        "/api/v1/gateway/heartbeat",
        headers=gateway_headers,
        json={**arm_health_payload, "flight_mode": "GUIDED"},
    )
    assert invalid_mode_heartbeat.status_code == 200
    invalid_mode_arm = client.post(
        f"/api/v1/admin/missions/{mission['id']}/arm",
        headers={**admin_headers, "Idempotency-Key": "arm-invalid-mode-001"},
        json=arm_payload,
    )
    assert invalid_mode_arm.status_code == 409
    assert "ARMING_MODE_NOT_ALLOWED" in invalid_mode_arm.json()["fields"]["preflight"]

    arm_ready_heartbeat = client.post(
        "/api/v1/gateway/heartbeat",
        headers=gateway_headers,
        json=arm_health_payload,
    )
    assert arm_ready_heartbeat.status_code == 200, arm_ready_heartbeat.text
    assert arm_ready_heartbeat.json()["health"]["vehicle_arm_enabled"] is True

    probe_arm = client.post(
        f"/api/v1/admin/missions/{mission['id']}/arm",
        headers={**admin_headers, "Idempotency-Key": "mission-arm-abort-probe-001"},
        json=arm_payload,
    )
    assert probe_arm.status_code == 202, probe_arm.text
    blocked_prequeued_start = client.post(
        f"/api/v1/admin/missions/{mission['id']}/commands/START",
        headers={**admin_headers, "Idempotency-Key": "start-while-arm-open-001"},
        json={"reason": "START não pode ficar atrás de ARM pendente"},
    )
    assert blocked_prequeued_start.status_code == 409
    cancel_pending_arm = client.post(
        f"/api/v1/admin/missions/{mission['id']}/abort",
        headers={**admin_headers, "Idempotency-Key": "abort-pending-arm-001"},
        json={"reason": "Cancelar ARM ainda não reconhecido"},
    )
    assert cancel_pending_arm.status_code == 202, cancel_pending_arm.text
    cancelled_probe = client.get(
        (f"/api/v1/admin/missions/{mission['id']}/commands/{probe_arm.json()['command']['id']}"),
        headers=admin_headers,
    )
    assert cancelled_probe.status_code == 200
    assert cancelled_probe.json()["status"] == "FAILED"
    assert "cancelado" in cancelled_probe.json()["result_detail"]
    pending_abort = client.get(
        "/api/v1/gateway/commands/pending?gateway_id=gateway-sitl-1",
        headers=gateway_headers,
    )
    assert pending_abort.status_code == 200
    assert [command["command"] for command in pending_abort.json()] == ["ABORT"]
    close_probe_abort = client.post(
        f"/api/v1/gateway/commands/{pending_abort.json()[0]['id']}/ack",
        headers=gateway_headers,
        json={
            "event_id": "abort-pending-arm-failed-001",
            "gateway_id": "gateway-sitl-1",
            "status": "FAILED",
            "detail": "Abortamento preventivo registrado sem ação MAVLink",
        },
    )
    assert close_probe_abort.status_code == 200, close_probe_abort.text

    start_while_disarmed = client.post(
        f"/api/v1/admin/missions/{mission['id']}/commands/START",
        headers={**admin_headers, "Idempotency-Key": "start-while-disarmed-001"},
        json={"reason": "START deve exigir armamento confirmado"},
    )
    assert start_while_disarmed.status_code == 409
    assert "VEHICLE_NOT_ARMED" in start_while_disarmed.json()["fields"]["preflight"]

    generic_arm = client.post(
        f"/api/v1/admin/missions/{mission['id']}/commands/ARM",
        headers={**admin_headers, "Idempotency-Key": "generic-arm-blocked-001"},
        json={"reason": "Tentativa pelo contrato genérico"},
    )
    assert generic_arm.status_code == 409

    missing_idempotency_key = client.post(
        f"/api/v1/admin/missions/{mission['id']}/arm",
        headers=admin_headers,
        json=arm_payload,
    )
    assert missing_idempotency_key.status_code == 422
    customer_arm = client.post(
        f"/api/v1/admin/missions/{mission['id']}/arm",
        headers={**customer_headers, "Idempotency-Key": "customer-arm-blocked-001"},
        json=arm_payload,
    )
    assert customer_arm.status_code == 403
    unsafe_arm_payload = client.post(
        f"/api/v1/admin/missions/{mission['id']}/arm",
        headers={**admin_headers, "Idempotency-Key": "arm-extra-field-001"},
        json={**arm_payload, "force": True},
    )
    assert unsafe_arm_payload.status_code == 422
    missing_confirmation = client.post(
        f"/api/v1/admin/missions/{mission['id']}/arm",
        headers={**admin_headers, "Idempotency-Key": "arm-confirmation-001"},
        json={**arm_payload, "area_clear_confirmed": False},
    )
    assert missing_confirmation.status_code == 422
    coerced_confirmation = client.post(
        f"/api/v1/admin/missions/{mission['id']}/arm",
        headers={**admin_headers, "Idempotency-Key": "arm-confirmation-type-001"},
        json={**arm_payload, "area_clear_confirmed": 1},
    )
    assert coerced_confirmation.status_code == 422

    arm_headers = {**admin_headers, "Idempotency-Key": "mission-arm-flow-001"}
    arm_request = client.post(
        f"/api/v1/admin/missions/{mission['id']}/arm",
        headers=arm_headers,
        json=arm_payload,
    )
    assert arm_request.status_code == 202, arm_request.text
    assert arm_request.json()["mission"]["id"] == mission["id"]
    assert arm_request.json()["command"]["command"] == "ARM"
    assert arm_request.json()["command"]["status"] == "PENDING"
    arm_replay = client.post(
        f"/api/v1/admin/missions/{mission['id']}/arm",
        headers=arm_headers,
        json=arm_payload,
    )
    assert arm_replay.status_code == 202
    assert arm_replay.headers["Idempotency-Replayed"] == "true"
    arm_mismatch = client.post(
        f"/api/v1/admin/missions/{mission['id']}/arm",
        headers=arm_headers,
        json={**arm_payload, "reason": "Justificativa incompatível no replay"},
    )
    assert arm_mismatch.status_code == 409

    pending_arm = client.get(
        "/api/v1/gateway/commands/pending?gateway_id=gateway-sitl-1",
        headers=gateway_headers,
    )
    assert pending_arm.status_code == 200
    arm_command = pending_arm.json()[0]
    assert arm_command["command"] == "ARM"
    assert arm_command["id"] == arm_request.json()["command"]["id"]

    wrong_gateway_arm_ack = client.post(
        f"/api/v1/gateway/commands/{arm_command['id']}/ack",
        headers=gateway_headers,
        json={
            "event_id": "arm-wrong-gateway-001",
            "gateway_id": "gateway-nao-vinculado",
            "status": "ACKNOWLEDGED",
        },
    )
    assert wrong_gateway_arm_ack.status_code == 403
    pre_ack_armed_heartbeat = client.post(
        "/api/v1/gateway/heartbeat",
        headers=gateway_headers,
        json={
            **arm_health_payload,
            "armed": True,
            "last_heartbeat_at": datetime.now(UTC).isoformat(),
        },
    )
    assert pre_ack_armed_heartbeat.status_code == 200, pre_ack_armed_heartbeat.text
    arm_ack = client.post(
        f"/api/v1/gateway/commands/{arm_command['id']}/ack",
        headers=gateway_headers,
        json={
            "event_id": "arm-command-ack-001",
            "gateway_id": "gateway-sitl-1",
            "status": "ACKNOWLEDGED",
        },
    )
    assert arm_ack.status_code == 200, arm_ack.text

    abort_after_arm_ack = client.post(
        f"/api/v1/admin/missions/{mission['id']}/abort",
        headers={**admin_headers, "Idempotency-Key": "abort-acknowledged-arm-001"},
        json={"reason": "Não mascarar resultado físico incerto"},
    )
    assert abort_after_arm_ack.status_code == 409

    premature_arm_complete = client.post(
        f"/api/v1/gateway/commands/{arm_command['id']}/ack",
        headers=gateway_headers,
        json={
            "event_id": "arm-command-premature-001",
            "gateway_id": "gateway-sitl-1",
            "status": "COMPLETED",
        },
    )
    assert premature_arm_complete.status_code == 409
    assert "heartbeat novo" in premature_arm_complete.json()["detail"]

    armed_heartbeat = client.post(
        "/api/v1/gateway/heartbeat",
        headers=gateway_headers,
        json={
            **arm_health_payload,
            "armed": True,
            "last_heartbeat_at": datetime.now(UTC).isoformat(),
        },
    )
    assert armed_heartbeat.status_code == 200, armed_heartbeat.text
    assert armed_heartbeat.json()["health"]["armed"] is True
    arm_complete_payload = {
        "event_id": "arm-command-complete-001",
        "gateway_id": "gateway-sitl-1",
        "status": "COMPLETED",
        "detail": "ACK aceito e heartbeat confirmou armed=true",
    }
    arm_complete = client.post(
        f"/api/v1/gateway/commands/{arm_command['id']}/ack",
        headers=gateway_headers,
        json=arm_complete_payload,
    )
    assert arm_complete.status_code == 200, arm_complete.text
    assert arm_complete.json()["status"] == "COMPLETED"
    admin_arm_result = client.get(
        f"/api/v1/admin/missions/{mission['id']}/commands/{arm_command['id']}",
        headers=admin_headers,
    )
    assert admin_arm_result.status_code == 200
    assert admin_arm_result.json()["status"] == "COMPLETED"
    assert admin_arm_result.json()["result_detail"] == arm_complete_payload["detail"]
    arm_events = client.get(
        f"/api/v1/admin/events?mission_id={mission['id']}",
        headers=admin_headers,
    )
    assert arm_events.status_code == 200
    arm_completed_event = next(
        event
        for event in arm_events.json()
        if event["event_id"] == arm_complete_payload["event_id"]
    )
    evidence = arm_completed_event["metadata"]
    assert evidence["health_snapshot_id"] == armed_heartbeat.json()["health"]["id"]
    assert _as_utc_datetime(evidence["health_received_at"]) == _as_utc_datetime(
        armed_heartbeat.json()["health"]["received_at"]
    )
    assert _as_utc_datetime(evidence["last_heartbeat_at"]) == _as_utc_datetime(
        armed_heartbeat.json()["health"]["last_heartbeat_at"]
    )
    assert evidence["source"] == "SITL"
    assert evidence["armed"] is True
    arm_complete_replay = client.post(
        f"/api/v1/gateway/commands/{arm_command['id']}/ack",
        headers=gateway_headers,
        json=arm_complete_payload,
    )
    assert arm_complete_replay.status_code == 200

    start_request = client.post(
        f"/api/v1/admin/missions/{mission['id']}/commands/START",
        headers={**admin_headers, "Idempotency-Key": "mission-start-flow-001"},
        json={"reason": "Início explícito no ensaio controlado"},
    )
    assert start_request.status_code == 202, start_request.text
    start_replay = client.post(
        f"/api/v1/admin/missions/{mission['id']}/commands/START",
        headers={**admin_headers, "Idempotency-Key": "mission-start-flow-001"},
        json={"reason": "Início explícito no ensaio controlado"},
    )
    assert start_replay.status_code == 202, start_replay.text
    assert start_replay.headers["Idempotency-Replayed"] == "true"
    pending_start = client.get(
        "/api/v1/gateway/commands/pending?gateway_id=gateway-sitl-1",
        headers=gateway_headers,
    )
    start_command = pending_start.json()[0]
    assert start_command["command"] == "START"
    start_ack = client.post(
        f"/api/v1/gateway/commands/{start_command['id']}/ack",
        headers=gateway_headers,
        json={
            "event_id": "start-command-ack-001",
            "gateway_id": "gateway-sitl-1",
            "status": "ACKNOWLEDGED",
        },
    )
    assert start_ack.status_code == 200, start_ack.text

    executing = client.post(
        f"/api/v1/gateway/missions/{mission['id']}/status",
        headers=gateway_headers,
        json={"event_id": "status-event-001", "status": "EXECUTING"},
    )
    assert executing.status_code == 200, executing.text
    start_complete = client.post(
        f"/api/v1/gateway/commands/{start_command['id']}/ack",
        headers=gateway_headers,
        json={
            "event_id": "start-command-complete-001",
            "gateway_id": "gateway-sitl-1",
            "status": "COMPLETED",
        },
    )
    assert start_complete.status_code == 200, start_complete.text

    pause_request = client.post(
        f"/api/v1/admin/missions/{mission['id']}/commands/PAUSE",
        headers={**admin_headers, "Idempotency-Key": "mission-pause-flow-001"},
        json={"reason": "Teste controlado de pausa"},
    )
    assert pause_request.status_code == 202, pause_request.text
    pending_pause = client.get(
        "/api/v1/gateway/commands/pending?gateway_id=gateway-sitl-1",
        headers=gateway_headers,
    )
    pause_command = pending_pause.json()[0]
    assert pause_command["command"] == "PAUSE"
    pause_ack = client.post(
        f"/api/v1/gateway/commands/{pause_command['id']}/ack",
        headers=gateway_headers,
        json={
            "event_id": "pause-command-ack-001",
            "gateway_id": "gateway-sitl-1",
            "status": "ACKNOWLEDGED",
        },
    )
    assert pause_ack.status_code == 200, pause_ack.text
    paused = client.post(
        f"/api/v1/gateway/missions/{mission['id']}/status",
        headers=gateway_headers,
        json={"event_id": "status-paused-001", "status": "PAUSED"},
    )
    assert paused.status_code == 200, paused.text
    pause_complete = client.post(
        f"/api/v1/gateway/commands/{pause_command['id']}/ack",
        headers=gateway_headers,
        json={
            "event_id": "pause-command-complete-001",
            "gateway_id": "gateway-sitl-1",
            "status": "COMPLETED",
        },
    )
    assert pause_complete.status_code == 200, pause_complete.text

    continue_request = client.post(
        f"/api/v1/admin/missions/{mission['id']}/commands/CONTINUE",
        headers={**admin_headers, "Idempotency-Key": "mission-continue-flow-001"},
        json={"reason": "Teste controlado de continuação"},
    )
    assert continue_request.status_code == 202, continue_request.text
    pending_continue = client.get(
        "/api/v1/gateway/commands/pending?gateway_id=gateway-sitl-1",
        headers=gateway_headers,
    )
    continue_command = pending_continue.json()[0]
    assert continue_command["command"] == "CONTINUE"
    continue_ack = client.post(
        f"/api/v1/gateway/commands/{continue_command['id']}/ack",
        headers=gateway_headers,
        json={
            "event_id": "continue-command-ack-001",
            "gateway_id": "gateway-sitl-1",
            "status": "ACKNOWLEDGED",
        },
    )
    assert continue_ack.status_code == 200, continue_ack.text
    resumed = client.post(
        f"/api/v1/gateway/missions/{mission['id']}/status",
        headers=gateway_headers,
        json={"event_id": "status-resumed-001", "status": "EXECUTING"},
    )
    assert resumed.status_code == 200, resumed.text
    continue_complete = client.post(
        f"/api/v1/gateway/commands/{continue_command['id']}/ack",
        headers=gateway_headers,
        json={
            "event_id": "continue-command-complete-001",
            "gateway_id": "gateway-sitl-1",
            "status": "COMPLETED",
        },
    )
    assert continue_complete.status_code == 200, continue_complete.text

    destination_reached = client.post(
        f"/api/v1/gateway/missions/{mission['id']}/status",
        headers=gateway_headers,
        json={"event_id": "status-destination-001", "status": "DESTINATION_REACHED"},
    )
    assert destination_reached.status_code == 200, destination_reached.text
    order_at_destination = client.get(
        f"/api/v1/orders/{mission['order_id']}", headers=customer_headers
    )
    assert order_at_destination.json()["status"] == "AT_DESTINATION"
    paused_at_destination = client.post(
        f"/api/v1/gateway/missions/{mission['id']}/status",
        headers=gateway_headers,
        json={"event_id": "status-paused-at-destination-001", "status": "PAUSED"},
    )
    assert paused_at_destination.status_code == 200, paused_at_destination.text
    order_while_paused = client.get(
        f"/api/v1/orders/{mission['order_id']}", headers=customer_headers
    )
    assert order_while_paused.json()["status"] == "AT_DESTINATION"
    resumed_at_destination = client.post(
        f"/api/v1/gateway/missions/{mission['id']}/status",
        headers=gateway_headers,
        json={"event_id": "status-resumed-at-destination-001", "status": "DESTINATION_REACHED"},
    )
    assert resumed_at_destination.status_code == 200, resumed_at_destination.text

    telemetry_payload = {
        "event_id": "telemetry-event-001",
        "vehicle_id": vehicle_id,
        "source": "SITL",
        # More precision than Numeric(10, 7) proves that an identical retry is
        # compared against the normalized persisted coordinates.
        "latitude": -23.11730004,
        "longitude": -46.55010004,
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
    incompatible_telemetry_replay = client.post(
        f"/api/v1/gateway/missions/{mission['id']}/telemetry",
        headers=gateway_headers,
        json={**telemetry_payload, "battery_percent": 79},
    )
    assert incompatible_telemetry_replay.status_code == 409
    assert incompatible_telemetry_replay.json()["code"] == "EVENT_ID_REUSED"
    mismatched_source = client.post(
        f"/api/v1/gateway/missions/{mission['id']}/telemetry",
        headers=gateway_headers,
        json={
            **telemetry_payload,
            "event_id": "telemetry-source-mismatch-001",
            "source": "HARDWARE_REAL",
        },
    )
    assert mismatched_source.status_code == 409
    assert mismatched_source.json()["code"] == "CONFLICT"

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
