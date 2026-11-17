import json
from uuid import UUID

import pytest
from sqlalchemy import select
from test_authorization_renewal import verified as shared_verified

from app.database.session import SessionLocal
from app.modules.missions.models import GatewayCommand, Mission
from app.modules.system_events.models import SystemEvent

verified = shared_verified


@pytest.fixture
def revision(client, gateway_headers, verified):
    path, gateway_path, _, health, original = verified
    for field in (
        "mission_upload_enabled",
        "flight_commands_enabled",
        "mission_start_enabled",
        "vehicle_arm_enabled",
    ):
        health[field] = False
    health["current_latitude"] = -23.11751
    health["current_longitude"] = -46.55021
    assert (
        client.post("/api/v1/gateway/heartbeat", headers=gateway_headers, json=health).status_code
        == 200
    )
    body = {
        "expected_version": original["mission"]["version"],
        "expected_sha256": original["mission"]["mission_sha256"],
        "origin_latitude": "-23.1175100",
        "origin_longitude": "-46.5502100",
        "reason": "Drone reposicionado pelo operador Luiz",
        "position_confirmed": True,
    }
    return path, gateway_path, body, health, original


def test_revision_archives_route_and_requires_new_review(
    client, admin_headers, gateway_headers, revision
):
    path, gateway_path, body, _, original = revision
    headers = {**admin_headers, "Idempotency-Key": "origin-revision-001"}
    result = client.post(path + "/revise-origin", headers=headers, json=body)
    assert result.status_code == 200, result.text
    revised = result.json()
    assert revised["version"] == 2
    assert revised["status"] == "GENERATED"
    assert revised["mission_sha256"] != body["expected_sha256"]
    assert revised["claimed_by_gateway"] is None
    assert revised["reviewed_at"] is None
    assert revised["exported_at"] is None
    assert revised["destination_latitude"] == original["mission"]["destination_latitude"]
    assert revised["destination_longitude"] == original["mission"]["destination_longitude"]
    for waypoint in revised["waypoints"]:
        if waypoint["sequence"] in (0, 1, 5, 6):
            assert float(waypoint["latitude"]) == float(body["origin_latitude"])
        else:
            assert waypoint == original["mission"]["waypoints"][waypoint["sequence"]]
    replay = client.post(path + "/revise-origin", headers=headers, json=body)
    assert replay.json() == revised
    assert replay.headers["Idempotency-Replayed"] == "true"
    assert (
        client.post(
            gateway_path + "/claim",
            headers=gateway_headers,
            json={"gateway_id": "gateway-sitl-1"},
        ).status_code
        == 409
    )
    with SessionLocal() as session:
        event = session.scalar(
            select(SystemEvent).where(SystemEvent.event_type == "MISSION_ORIGIN_REVISED")
        )
        assert event.event_metadata["previous_mission_file"] == original["mission_file"]
        archived = json.loads(event.event_metadata["previous_mission_json"])
        assert archived["version"] == 1
        assert archived["mission_sha256"] == body["expected_sha256"]
        assert archived["reviewed_at"]
        assert session.scalars(select(GatewayCommand)).all() == []
        assert len(session.scalars(select(Mission)).all()) == 1


@pytest.mark.parametrize(
    "fault",
    [
        "armed",
        "stale",
        "preflight",
        "gate",
        "missing_gate",
        "version",
        "hash",
        "unconfirmed",
        "destination",
        "latitude",
        "range",
        "pending",
        "start",
        "executing",
    ],
)
def test_revision_fails_closed(client, admin_headers, gateway_headers, revision, fault):
    from datetime import UTC, datetime, timedelta

    from app.core.enums import GatewayCommandType, MissionStatus
    from app.modules.approvals.models import FlightAuthorization
    from app.modules.vehicles.models import VehicleHealthSnapshot

    path, _, body, health, original = revision
    if fault in {"armed", "preflight", "gate", "missing_gate"}:
        key = {
            "armed": "armed",
            "preflight": "preflight_ok",
            "gate": "vehicle_arm_enabled",
            "missing_gate": "mission_upload_enabled",
        }[fault]
        health[key] = None if fault == "missing_gate" else fault != "preflight"
        client.post("/api/v1/gateway/heartbeat", headers=gateway_headers, json=health)
    elif fault in {"version", "hash", "unconfirmed", "destination", "latitude", "range"}:
        key, value = {
            "version": ("expected_version", 99),
            "hash": ("expected_sha256", "0" * 64),
            "unconfirmed": ("position_confirmed", False),
            "destination": ("destination_latitude", -23),
            "latitude": ("origin_latitude", 91),
            "range": ("origin_latitude", -22),
        }[fault]
        body[key] = value
    else:
        with SessionLocal() as session:
            mission = session.get(Mission, UUID(original["mission"]["id"]))
            if fault == "stale":
                for snapshot in session.scalars(select(VehicleHealthSnapshot)):
                    snapshot.received_at = datetime.now(UTC) - timedelta(minutes=2)
            elif fault == "executing":
                mission.status = MissionStatus.EXECUTING
            else:
                auth = session.get(FlightAuthorization, UUID(original["authorization_id"]))
                session.add(
                    GatewayCommand(
                        mission_id=mission.id,
                        requested_by_id=auth.administrator_id,
                        command=GatewayCommandType.START
                        if fault == "start"
                        else GatewayCommandType.ARM,
                    )
                )
            session.commit()
    result = client.post(
        path + "/revise-origin",
        json=body,
        headers={**admin_headers, "Idempotency-Key": "revision-invalid-001"},
    )
    assert result.status_code in (409, 422), result.text
    assert client.get(path, headers=admin_headers).json()["version"] == 1


def test_revision_customer_cannot_mutate(client, customer_headers, revision):
    path, _, body, _, _ = revision
    assert (
        client.post(
            path + "/revise-origin",
            json=body,
            headers={**customer_headers, "Idempotency-Key": "customer-revision-001"},
        ).status_code
        == 403
    )


def test_retirement_handshake_is_bound_idempotent_and_required(
    client, admin_headers, gateway_headers, revision, verified
):
    path, gateway_path, body, _, original = revision
    release_body = {"version": body["expected_version"], "mission_sha256": body["expected_sha256"]}
    release_path = gateway_path + "/release-retired-version"
    unchanged = client.post(release_path, headers=gateway_headers, json=release_body)
    assert unchanged.status_code == 200
    assert unchanged.json()["released"] is False
    assert (
        client.post(
            path + "/revise-origin",
            headers={**admin_headers, "Idempotency-Key": "revision-handshake-001"},
            json=body,
        ).status_code
        == 200
    )
    assert client.get(path + "/export", headers=admin_headers).status_code == 200
    assert client.post(path + "/mark-under-review", headers=admin_headers).status_code == 200
    assert client.post(path + "/mark-reviewed", headers=admin_headers, json={}).status_code == 200
    authorization = verified[2]
    blocked = client.post(path + "/authorize-flight", headers=admin_headers, json=authorization)
    assert blocked.status_code == 409
    assert "versão anterior" in blocked.json()["detail"]
    invalid = client.post(
        release_path, headers=gateway_headers, json={**release_body, "mission_sha256": "0" * 64}
    )
    assert invalid.status_code == 409
    for _ in range(2):
        released = client.post(release_path, headers=gateway_headers, json=release_body)
        assert released.status_code == 200, released.text
        assert released.json() == {
            **release_body,
            "mission_id": original["mission"]["id"],
            "released": True,
        }
    authorized = client.post(path + "/authorize-flight", headers=admin_headers, json=authorization)
    assert authorized.status_code == 200, authorized.text
    assert authorized.json()["authorization"]["mission_version"] == 2
    assert authorized.json()["authorization"]["id"] != original["authorization_id"]
    with SessionLocal() as session:
        releases = session.scalars(
            select(SystemEvent).where(SystemEvent.event_type == "MISSION_RETIRED_VERSION_RELEASED")
        ).all()
        assert len(releases) == 1


@pytest.mark.parametrize("fault", ["armed", "gate", "hash", "gateway"])
def test_retirement_rechecks_physical_state_and_binding(
    client, admin_headers, gateway_headers, revision, fault
):
    path, gateway_path, body, health, _ = revision
    assert (
        client.post(
            path + "/revise-origin",
            headers={**admin_headers, "Idempotency-Key": "revision-release-guards"},
            json=body,
        ).status_code
        == 200
    )
    release_body = {"version": 1, "mission_sha256": body["expected_sha256"]}
    if fault == "hash":
        release_body["mission_sha256"] = "0" * 64
    elif fault == "gateway":
        gateway_headers = {**gateway_headers, "X-Gateway-ID": "another-gateway"}
    else:
        health["armed" if fault == "armed" else "mission_upload_enabled"] = True
        client.post("/api/v1/gateway/heartbeat", headers=gateway_headers, json=health)
    released = client.post(
        gateway_path + "/release-retired-version", headers=gateway_headers, json=release_body
    )
    assert released.status_code == (401 if fault == "gateway" else 409), released.text
