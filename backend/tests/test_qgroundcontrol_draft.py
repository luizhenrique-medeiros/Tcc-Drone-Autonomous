import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.enums import GatewayCommandStatus, GatewayCommandType, MissionStatus
from app.database.session import SessionLocal
from app.main import app
from app.modules.approvals.models import FlightAuthorization
from app.modules.missions.models import GatewayCommand, Mission
from app.modules.missions.qgroundcontrol_plan import (
    PlanPosition,
    build_reviewed_candidate,
    create_draft_plan,
    validate_reviewed_plan,
)
from app.modules.system_events.models import SystemEvent
from tests.test_full_flow import _create_submitted_order


def test_operational_export_and_delivery_confirmation(
    client: TestClient,
    customer_headers: dict[str, str],
    admin_headers: dict[str, str],
    gateway_headers: dict[str, str],
    valid_point_payload: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings().model_copy(update={"app_env": "development"})
    monkeypatch.setitem(app.dependency_overrides, get_settings, lambda: settings)
    order = _create_submitted_order(client, customer_headers, valid_point_payload)
    order_path = f"/api/v1/admin/orders/{order['id']}"
    assert client.post(f"{order_path}/approve", headers=admin_headers).status_code == 200
    mission = client.post(f"{order_path}/prepare-mission", headers=admin_headers).json()
    mission_path = f"/api/v1/admin/missions/{mission['id']}"
    assert mission["status"] == "GENERATED"
    assert mission["qgroundcontrol_plan_exported_at"] is None

    revision = {
        "expected_version": mission["version"],
        "expected_sha256": mission["mission_sha256"],
    }
    download = client.post(
        f"{mission_path}/qgroundcontrol-plan", headers=admin_headers, json=revision
    )
    assert download.status_code == 200, download.text
    plan = download.json()["mission"]
    assert f"pedido-{order['id']}-v{mission['version']}-" in download.headers["content-disposition"]
    assert download.headers["x-plan-sha256"] == hashlib.sha256(download.content).hexdigest()
    assert plan["plannedHomePosition"] == [
        float(mission["origin_latitude"]),
        float(mission["origin_longitude"]),
        None,
    ]
    assert [item["command"] for item in plan["items"]] == [22, 16, 20]
    assert [item["frame"] for item in plan["items"]] == [3, 3, 2]
    assert plan["items"][1]["params"][0] == 5
    assert plan["items"][1]["params"][4:] == [
        float(mission["destination_latitude"]),
        float(mission["destination_longitude"]),
        float(mission["takeoff_altitude_m"]),
    ]
    detail = client.get(mission_path, headers=admin_headers).json()
    assert detail["qgroundcontrol_plan_exported_at"]
    assert detail["status"] == "GENERATED"
    assert client.get(order_path, headers=admin_headers).json()["status"] == "MISSION_READY"
    stale_version = {**revision, "expected_version": mission["version"] + 1}
    assert (
        client.post(
            f"{mission_path}/qgroundcontrol-plan", headers=admin_headers, json=stale_version
        ).status_code
        == 409
    )

    with SessionLocal() as db:
        export_event = db.scalar(
            select(SystemEvent).where(
                SystemEvent.order_id == UUID(order["id"]),
                SystemEvent.event_type == "QGROUNDCONTROL_PLAN_EXPORTED",
            )
        )
        assert export_event is not None and export_event.actor_user_id is not None
        previous_command = GatewayCommand(
            mission_id=UUID(mission["id"]),
            requested_by_id=export_event.actor_user_id,
            command=GatewayCommandType.ARM,
            gateway_id="gateway-sitl-1",
        )
        db.add(previous_command)
        db.flush()
        previous_command_id = previous_command.id
        db.commit()
    assert client.get("/api/v1/gateway/missions/authorized", headers=gateway_headers).json() == []
    assert (
        client.get(
            "/api/v1/gateway/commands/pending?gateway_id=gateway-sitl-1", headers=gateway_headers
        ).json()
        == []
    )
    assert (
        client.post(
            f"/api/v1/gateway/missions/{mission['id']}/claim",
            headers=gateway_headers,
            json={"gateway_id": "gateway-sitl-1"},
        ).status_code
        == 404
    )
    assert client.post(f"{mission_path}/arm", headers=admin_headers).status_code == 404
    assert client.get("/api/v1/admin/bench-arm", headers=admin_headers).status_code == 404
    evidence = {"evidence": "Recebimento confirmado pelo destinatário."}
    assert (
        client.post(
            f"{order_path}/confirm-delivery", headers=customer_headers, json=evidence
        ).status_code
        == 403
    )
    for _ in range(2):
        delivered = client.post(
            f"{order_path}/confirm-delivery", headers=admin_headers, json=evidence
        )
        assert delivered.status_code == 200, delivered.text
        assert delivered.json()["status"] == "COMPLETED"
    assert client.get(mission_path, headers=admin_headers).json()["status"] == "GENERATED"
    with SessionLocal() as db:
        previous_command_after = db.get(GatewayCommand, previous_command_id)
        assert previous_command_after is not None
        assert previous_command_after.status is GatewayCommandStatus.PENDING
        (confirmation,) = db.scalars(
            select(SystemEvent).where(
                SystemEvent.order_id == UUID(order["id"]),
                SystemEvent.event_type == "ORDER_DELIVERY_CONFIRMED",
            )
        ).all()
        assert confirmation.actor_user_id is not None
        assert confirmation.event_metadata == evidence


def test_draft_uses_current_position_and_never_changes_mission_state(
    client: TestClient,
    customer_headers: dict[str, str],
    admin_headers: dict[str, str],
    gateway_headers: dict[str, str],
    valid_point_payload: dict[str, object],
) -> None:
    order = _create_submitted_order(client, customer_headers, valid_point_payload)
    assert (
        client.post(
            f"/api/v1/admin/orders/{order['id']}/approve", headers=admin_headers, json={}
        ).status_code
        == 200
    )
    mission = client.post(
        f"/api/v1/admin/orders/{order['id']}/prepare-mission", headers=admin_headers
    ).json()
    assert mission["qgroundcontrol_review_status"] is None
    heartbeat = client.post(
        "/api/v1/gateway/heartbeat",
        headers=gateway_headers,
        json={
            "gateway_id": "gateway-sitl-1",
            "vehicle_identifier": "qgc-draft",
            "source": "SITL",
            "connected": True,
            "heartbeat": True,
            "armed": False,
            "gps_fix_type": 3,
            "current_latitude": -23.1,
            "current_longitude": -46.5,
        },
    )
    assert heartbeat.status_code == 200, heartbeat.text
    vehicle_id = heartbeat.json()["vehicle"]["id"]
    path = f"/api/v1/admin/missions/{mission['id']}/qgroundcontrol-draft"
    response = client.post(
        path, headers=admin_headers, json={"vehicle_id": vehicle_id, "home_amsl_m": 750}
    )
    assert response.status_code == 200, response.text
    result = response.json()
    items = result["mission"]["items"]
    assert [item["command"] for item in items] == [22, 16, 20]
    assert items[0]["params"][4:6] == [-23.1, -46.5]
    assert items[1]["params"][0] == 5
    assert items[1]["params"][4:6] == [
        float(mission["destination_latitude"]),
        float(mission["destination_longitude"]),
    ]
    assert result["mission"]["plannedHomePosition"] == [-23.1, -46.5, 750]
    assert items[0]["AltitudeMode"] == items[1]["AltitudeMode"] == 1
    assert items[-1] == {
        "type": "SimpleItem",
        "command": 20,
        "frame": 2,
        "autoContinue": True,
        "doJumpId": 3,
        "params": [0] * 7,
    }
    assert response.headers["x-draft-sha256"] == hashlib.sha256(response.content).hexdigest()
    offline = client.post(path, headers=admin_headers, json={})
    assert offline.status_code == 200, offline.text
    assert offline.json()["mission"]["plannedHomePosition"] == [
        float(mission["origin_latitude"]),
        float(mission["origin_longitude"]),
        None,
    ]
    missing_altitude = client.post(path, headers=admin_headers, json={"vehicle_id": vehicle_id})
    assert missing_altitude.status_code == 200
    assert missing_altitude.json()["mission"]["plannedHomePosition"] == [-23.1, -46.5, None]
    health = client.post(
        "/api/v1/gateway/heartbeat",
        headers=gateway_headers,
        json={
            "gateway_id": "gateway-sitl-1",
            "vehicle_identifier": "qgc-draft",
            "source": "HARDWARE_REAL",
            "connected": True,
            "heartbeat": True,
            "armed": True,
            "gps_fix_type": 1,
            "preflight_ok": False,
            "rtl_configured": False,
            "current_latitude": -23.1,
            "current_longitude": -46.5,
            "current_altitude_m": 0.25,
            "current_amsl_m": 755.2,
        },
    )
    assert health.status_code == 200, health.text
    automatic = client.post(path, headers=admin_headers, json={"vehicle_id": vehicle_id})
    assert automatic.status_code == 200, automatic.text
    assert automatic.json()["mission"]["plannedHomePosition"] == [-23.1, -46.5, 755.2]
    review_path = f"/api/v1/admin/missions/{mission['id']}/qgroundcontrol-review"
    assert client.get(review_path, headers=admin_headers).status_code == 404
    review_payload = {
        "expected_version": mission["version"],
        "expected_sha256": mission["mission_sha256"],
        "plan": response.text,
        "confirmed": True,
    }
    rejected = client.post(review_path, headers=customer_headers, json=review_payload)
    assert rejected.status_code == 403
    not_confirmed = client.post(
        review_path, headers=admin_headers, json={**review_payload, "confirmed": False}
    )
    assert not_confirmed.status_code == 409
    stale = client.post(
        review_path, headers=admin_headers, json={**review_payload, "expected_version": 999}
    )
    assert stale.status_code == 409
    mismatched_home = response.json()
    mismatched_home["mission"]["plannedHomePosition"][0] += 0.001
    invalid_return = client.post(
        review_path,
        headers=admin_headers,
        json={**review_payload, "plan": json.dumps(mismatched_home)},
    )
    assert invalid_return.status_code == 409
    assert "Home planejado" in invalid_return.json()["detail"]
    modified = response.json()
    modified["mission"]["items"][1]["params"][4] += 0.1
    wrong_destination = client.post(
        review_path, headers=admin_headers, json={**review_payload, "plan": json.dumps(modified)}
    )
    assert wrong_destination.status_code == 409
    modified = response.json()
    added_point = dict(modified["mission"]["items"][1])
    added_point["params"] = list(added_point["params"])
    added_point["params"][4] -= 0.0001
    modified["mission"]["items"].insert(1, added_point)
    # Continue accepting earlier .plan files that used null for reserved RTL values.
    modified["mission"]["items"][-1]["params"] = [0, 0, 0, None, None, None, None]
    modified["mission"]["items"].insert(
        0,
        {
            "type": "SimpleItem",
            "command": 530,
            "frame": 2,
            "autoContinue": True,
            "params": [0, 2, None, None, None, None, None],
        },
    )
    edited_content = json.dumps(modified, indent=2) + "\r\n"
    reviewed = client.post(
        review_path, headers=admin_headers, json={**review_payload, "plan": edited_content}
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["plan_sha256"] == hashlib.sha256(edited_content.encode()).hexdigest()
    assert client.get(review_path, headers=customer_headers).status_code == 403
    downloaded = client.get(review_path, headers=admin_headers)
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content == edited_content.encode("utf-8")
    assert downloaded.headers["x-plan-sha256"] == reviewed.json()["plan_sha256"]
    assert downloaded.headers["content-disposition"].endswith('.plan"')
    assert downloaded.headers["cache-control"] == "no-store"
    reviewed_items = reviewed.json()["reviewed_items"]
    assert [item["command"] for item in reviewed_items] == [530, 22, 16, 16, 20]
    assert reviewed_items[1]["params"][3] is None
    assert reviewed_items[-1]["params"][3:] == [None, None, None, None]
    assert reviewed.json()["candidate_sha256"] is not None
    assert reviewed.json()["ignored_camera_item"] is True
    with SessionLocal() as session:
        event = session.scalar(
            select(SystemEvent).where(
                SystemEvent.event_type == "QGROUNDCONTROL_PLAN_REVIEW_RECORDED"
            )
        )
        assert event is not None
        assert event.event_metadata["plan"] == edited_content
        assert event.event_metadata["mission_version"] == mission["version"]
        assert event.event_metadata["mission_sha256"] == mission["mission_sha256"]
        assert event.event_metadata["reviewed_items"] == reviewed_items
        assert event.event_metadata["ignored_camera_item"] is True
        candidate = event.event_metadata["candidate"]
        assert isinstance(candidate, str)
        assert hashlib.sha256(candidate.encode()).hexdigest() == reviewed.json()["candidate_sha256"]
        parsed_candidate = json.loads(candidate)
        assert parsed_candidate["plan_sha256"] == reviewed.json()["plan_sha256"]
        assert parsed_candidate["mission_sha256"] == mission["mission_sha256"]
        assert parsed_candidate["mission_version"] == mission["version"]
        assert [item["command"] for item in parsed_candidate["items"]] == [22, 16, 16, 20]
        assert [item["sequence"] for item in parsed_candidate["items"]] == [0, 1, 2, 3]
        assert parsed_candidate["items"][0]["params"][3] is None
        assert parsed_candidate["items"][-1]["params"] == [0] * 7
    audit = client.get(f"/api/v1/admin/events?mission_id={mission['id']}", headers=admin_headers)
    assert audit.status_code == 200, audit.text
    recorded = next(item for item in audit.json() if item["id"] == reviewed.json()["event_id"])
    assert recorded["metadata"]["reviewed_items"] == reviewed_items
    assert recorded["metadata"]["plan_sha256"] == reviewed.json()["plan_sha256"]
    current = client.get(f"/api/v1/admin/missions/{mission['id']}", headers=admin_headers).json()
    assert current["status"] == "GENERATED"
    assert current["mission_sha256"] == mission["mission_sha256"]
    assert current["qgroundcontrol_review_status"] == "CURRENT"
    started = client.post(
        f"/api/v1/admin/missions/{mission['id']}/mark-under-review", headers=admin_headers
    )
    assert started.status_code == 200
    legacy_review = client.post(
        f"/api/v1/admin/missions/{mission['id']}/mark-reviewed", headers=admin_headers, json={}
    )
    assert legacy_review.status_code == 409
    assert "não está vinculado" in legacy_review.json()["detail"]
    # Even an older READY_FOR_AUTHORIZATION row cannot bypass the independent guard.
    with SessionLocal() as session:
        stored = session.get(Mission, UUID(mission["id"]))
        assert stored is not None
        stored.status = MissionStatus.READY_FOR_AUTHORIZATION
        stored.version += 1
        session.commit()
    changed = client.get(f"/api/v1/admin/missions/{mission['id']}", headers=admin_headers).json()
    assert changed["qgroundcontrol_review_status"] == "OUTDATED"
    assert client.get(review_path, headers=admin_headers).status_code == 409
    authorization = client.post(
        f"/api/v1/admin/missions/{mission['id']}/authorize-flight",
        headers=admin_headers,
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
    assert authorization.status_code == 409
    assert "exclusiva do QGroundControl" in authorization.json()["detail"]
    after_review = client.post(path, headers=admin_headers, json={"vehicle_id": vehicle_id})
    assert after_review.status_code == 200, after_review.text
    with SessionLocal() as session:
        assert session.scalar(select(FlightAuthorization.id)) is None
        stored = session.get(Mission, UUID(mission["id"]))
        assert stored is not None
        stored.status = MissionStatus.UNDER_REVIEW
        session.commit()
    armed_heartbeat = client.post(
        "/api/v1/gateway/heartbeat",
        headers=gateway_headers,
        json={
            "gateway_id": "gateway-sitl-1",
            "vehicle_identifier": "qgc-draft",
            "source": "SITL",
            "connected": True,
            "heartbeat": True,
            "armed": True,
            "gps_fix_type": 3,
            "current_latitude": -23.1,
            "current_longitude": -46.5,
        },
    )
    assert armed_heartbeat.status_code == 200
    armed_draft = client.post(
        path, headers=admin_headers, json={"vehicle_id": vehicle_id, "home_amsl_m": 750}
    )
    assert armed_draft.status_code == 200, armed_draft.text
    assert armed_draft.json()["mission"]["plannedHomePosition"] == [-23.1, -46.5, 750]
    assert (
        client.post(
            path, headers=customer_headers, json={"vehicle_id": vehicle_id, "home_amsl_m": 750}
        ).status_code
        == 403
    )
    assert (
        client.post(
            path, headers=admin_headers, json={"vehicle_id": str(uuid4()), "home_amsl_m": 750}
        ).status_code
        == 404
    )


@pytest.mark.parametrize("altitude", [0, -1, float("nan"), float("inf")])
def test_invalid_relative_altitude_is_rejected(altitude: float) -> None:
    with pytest.raises(ValueError):
        create_draft_plan(
            PlanPosition(1, 2), PlanPosition(3, 4), home_amsl_m=10, altitude_m=altitude
        )


def test_physical_progress_requires_a_readback_of_the_current_review(
    client: TestClient,
    customer_headers: dict[str, str],
    admin_headers: dict[str, str],
    gateway_headers: dict[str, str],
    valid_point_payload: dict[str, object],
) -> None:
    order = _create_submitted_order(client, customer_headers, valid_point_payload)
    order_path = f"/api/v1/admin/orders/{order['id']}"
    assert client.post(f"{order_path}/approve", headers=admin_headers, json={}).status_code == 200
    mission = client.post(f"{order_path}/prepare-mission", headers=admin_headers).json()
    mission_path = f"/api/v1/admin/missions/{mission['id']}"
    draft = client.post(f"{mission_path}/qgroundcontrol-draft", headers=admin_headers, json={})
    assert draft.status_code == 200, draft.text
    review_payload = {
        "expected_version": mission["version"],
        "expected_sha256": mission["mission_sha256"],
        "plan": draft.text,
        "confirmed": True,
    }
    review = client.post(
        f"{mission_path}/qgroundcontrol-review", headers=admin_headers, json=review_payload
    )
    assert review.status_code == 200, review.text
    heartbeat = client.post(
        "/api/v1/gateway/heartbeat",
        headers=gateway_headers,
        json={
            "gateway_id": gateway_headers["X-Gateway-ID"],
            "vehicle_identifier": "physical-observation",
            "autopilot_system": "PX4",
            "source": "HARDWARE_REAL",
            "connected": True,
            "heartbeat": True,
        },
    )
    assert heartbeat.status_code == 200, heartbeat.text
    vehicle = heartbeat.json()["vehicle"]
    path = f"/api/v1/gateway/vehicles/{vehicle['id']}/observations"
    now = datetime.now(UTC)
    identity = {"native_plan_id": 444, "system_id": 1, "component_id": 1}

    def send(event_type: str, metadata: dict) -> dict:
        event = {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "message": "Observação de teste do PX4.",
            "metadata": metadata,
        }
        response = client.post(path, headers=gateway_headers, json=[event])
        assert response.status_code == 204, response.text
        return event

    def linked_events() -> list[dict]:
        response = client.get(
            "/api/v1/admin/events", params={"order_id": order["id"]}, headers=admin_headers
        )
        assert response.status_code == 200, response.text
        return [
            event
            for event in response.json()
            if event["event_type"] == "PX4_PHYSICAL_MISSION_PROGRESS_OBSERVED"
        ]

    progress = {
        **identity,
        "sequence": 1,
        "mission_state": 3,
        "source_occurred_at": (now + timedelta(seconds=1)).isoformat(),
    }
    send("MAVLINK_MISSION_CURRENT", progress)
    assert linked_events() == []
    send(
        "PX4_PHYSICAL_PLAN_READBACK",
        {
            **identity,
            "plan_sha256": review.json()["plan_sha256"],
            "item_count": 3,
            "source_occurred_at": now.isoformat(),
        },
    )
    send("MAVLINK_MISSION_CURRENT", {**progress, "native_plan_id": 555})
    send("MAVLINK_MISSION_CURRENT", {**progress, "source_occurred_at": now.isoformat()})
    assert linked_events() == []
    observed = send("MAVLINK_MISSION_CURRENT", progress)
    replay = client.post(path, headers=gateway_headers, json=[observed])
    assert replay.status_code == 204, replay.text
    linked = linked_events()
    assert len(linked) == 1
    assert linked[0]["mission_id"] == mission["id"]
    assert linked[0]["vehicle_id"] == vehicle["id"]
    assert linked[0]["metadata"]["sequence"] == 1

    newer = client.post(
        f"{mission_path}/qgroundcontrol-review",
        headers=admin_headers,
        json={**review_payload, "plan": draft.text + "\n"},
    )
    assert newer.status_code == 200, newer.text
    send("MAVLINK_MISSION_CURRENT", progress)
    assert len(linked_events()) == 1
    assert client.get(mission_path, headers=admin_headers).json()["status"] == mission["status"]


def test_draft_is_valid_json_without_nonstandard_nan() -> None:
    content = create_draft_plan(
        PlanPosition(1, 2), PlanPosition(3, 4), home_amsl_m=10, altitude_m=5
    )
    assert json.loads(content)["geoFence"]["polygons"] == []


def test_review_identifies_land_instead_of_rtl() -> None:
    origin, destination = PlanPosition(1, 2), PlanPosition(3, 4)
    plan = json.loads(create_draft_plan(origin, destination, home_amsl_m=10, altitude_m=5))
    plan["mission"]["items"][-1]["command"] = 21
    with pytest.raises(ValueError, match=r"termina com Land \(Pousar\).*Return to Launch"):
        validate_reviewed_plan(json.dumps(plan), destination)


def test_qgroundcontrol_camera_and_unknown_home_altitude_do_not_hide_missing_rtl() -> None:
    origin, destination = PlanPosition(-23.1, -46.5), PlanPosition(-23.2, -46.6)
    plan = json.loads(create_draft_plan(origin, destination, home_amsl_m=10, altitude_m=5))
    plan["mission"]["plannedHomePosition"][2] = None
    plan["mission"]["items"].insert(
        0,
        {
            "type": "SimpleItem",
            "command": 530,
            "frame": 2,
            "autoContinue": True,
            "doJumpId": 1,
            "params": [0, 2, None, None, None, None, None],
        },
    )
    items = validate_reviewed_plan(json.dumps(plan), destination)
    assert [item["command"] for item in items] == [530, 22, 16, 20]
    assert items[0]["params"] == [0, 2, None, None, None, None, None]
    assert items[1]["params"][3] is None
    candidate = build_reviewed_candidate(
        items, plan_digest="a" * 64, mission_version=1, mission_digest="b" * 64
    )
    assert candidate.ignored_camera_item is True
    route = json.loads(candidate.content)
    assert [(item["sequence"], item["command"]) for item in route["items"]] == [
        (0, 22),
        (1, 16),
        (2, 20),
    ]
    assert route["items"][0]["params"][3] is None
    assert route["items"][-1]["params"] == [0] * 7
    plan["mission"]["items"].pop()
    with pytest.raises(ValueError, match="não contém Return To Launch"):
        validate_reviewed_plan(json.dumps(plan), destination)


def test_candidate_binds_exact_file_and_mission_version() -> None:
    origin, destination = PlanPosition(1, 2), PlanPosition(3, 4)
    content = create_draft_plan(origin, destination, home_amsl_m=10, altitude_m=5)
    items = validate_reviewed_plan(content, destination)
    arguments = {
        "plan_digest": hashlib.sha256(content.encode()).hexdigest(),
        "mission_version": 1,
        "mission_digest": "b" * 64,
    }
    original = build_reviewed_candidate(items, **arguments)
    assert original.sha256 == build_reviewed_candidate(items, **arguments).sha256
    assert (
        original.sha256
        != build_reviewed_candidate(items, **{**arguments, "mission_version": 2}).sha256
    )
    assert (
        original.sha256
        != build_reviewed_candidate(items, **{**arguments, "plan_digest": "c" * 64}).sha256
    )
    assert (
        original.sha256
        != build_reviewed_candidate(items, **{**arguments, "mission_digest": "d" * 64}).sha256
    )


@pytest.mark.parametrize("explicit_upload", [False, True])
def test_sitl_authorization_and_claim_bind_the_selected_review(
    client: TestClient,
    customer_headers: dict[str, str],
    admin_headers: dict[str, str],
    gateway_headers: dict[str, str],
    valid_point_payload: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    explicit_upload: bool,
) -> None:
    order = _create_submitted_order(client, customer_headers, valid_point_payload)
    client.post(f"/api/v1/admin/orders/{order['id']}/approve", headers=admin_headers, json={})
    mission = client.post(
        f"/api/v1/admin/orders/{order['id']}/prepare-mission", headers=admin_headers
    ).json()
    path = f"/api/v1/admin/missions/{mission['id']}"
    plan = create_draft_plan(
        PlanPosition(-23.1175, -46.5502),
        PlanPosition(
            float(mission["destination_latitude"]), float(mission["destination_longitude"])
        ),
        home_amsl_m=750,
        altitude_m=10,
    )
    review_payload = {
        "expected_version": mission["version"],
        "expected_sha256": mission["mission_sha256"],
        "plan": plan,
        "confirmed": True,
    }
    first = client.post(f"{path}/qgroundcontrol-review", headers=admin_headers, json=review_payload)
    assert first.status_code == 200, first.text
    latest = client.post(
        f"{path}/qgroundcontrol-review",
        headers=admin_headers,
        json={**review_payload, "plan": plan + "\n"},
    )
    assert latest.status_code == 200, latest.text
    review = latest.json()
    heartbeat = {
        "gateway_id": "gateway-sitl-1",
        "vehicle_identifier": "px4-binding-test",
        "autopilot_system": "PX4",
        "source": "SITL",
        "connection_mode": "sitl",
        "connected": True,
        "heartbeat": True,
        "armed": False,
        "gps_fix_type": 3,
        "satellites": 14,
        "flight_mode": "POSCTL",
        "preflight_ok": True,
        "rtl_configured": True,
        "mission_upload_enabled": True,
        "origin_latitude": -23.1175,
        "origin_longitude": -46.5502,
    }
    response = client.post("/api/v1/gateway/heartbeat", headers=gateway_headers, json=heartbeat)
    assert response.status_code == 200, response.text
    authorization_input = {
        "vehicle_id": response.json()["vehicle"]["id"],
        "operator_name": "Operador de teste",
        "controlled_area_confirmed": True,
        "checklist": {
            "area_and_conditions_clear": True,
            "aircraft_and_payload_inspected": True,
            "operator_ready": True,
        },
        "qgroundcontrol_review_event_id": review["event_id"],
    }
    denied = client.post(
        f"{path}/authorize-flight", headers=admin_headers, json=authorization_input
    )
    assert denied.status_code == 409
    if explicit_upload:
        response = client.post(
            f"{path}/px4-sitl/upload",
            headers={**admin_headers, "Idempotency-Key": str(uuid4())},
            json={
                "vehicle_id": authorization_input["vehicle_id"],
                "qgroundcontrol_review_event_id": review["event_id"],
                "confirmed": True,
            },
        )
        assert response.status_code == 404
    monkeypatch.setattr(get_settings(), "px4_sitl_plan_validation", True)
    outdated = client.post(
        f"{path}/authorize-flight",
        headers=admin_headers,
        json={**authorization_input, "qgroundcontrol_review_event_id": first.json()["event_id"]},
    )
    assert outdated.status_code == 409
    assert "mais recente" in outdated.json()["detail"]
    if explicit_upload:
        upload_path = f"{path}/px4-sitl/upload"
        operator = {**admin_headers, "Idempotency-Key": str(uuid4())}
        request = {
            "vehicle_id": authorization_input["vehicle_id"],
            "qgroundcontrol_review_event_id": review["event_id"],
            "confirmed": True,
        }
        assert (
            client.post(upload_path, headers=operator, json={**request, "force": True}).status_code
            == 422
        )
        authorized = client.post(upload_path, headers=operator, json=request)
        assert authorized.status_code == 202, authorized.text
        assert client.post(upload_path, headers=operator, json=request).json() == authorized.json()
        with SessionLocal() as session:
            persisted = session.scalar(select(FlightAuthorization))
            assert persisted.qgroundcontrol_review_event_id == UUID(review["event_id"])
            assert persisted.qgroundcontrol_candidate_sha256 == review["candidate_sha256"]
            assert persisted.checklist == {}
    else:
        authorized = client.post(
            f"{path}/authorize-flight", headers=admin_headers, json=authorization_input
        )
        assert authorized.status_code == 200, authorized.text
        authorization = authorized.json()["authorization"]
        assert authorization["qgroundcontrol_review_event_id"] == review["event_id"]
        assert authorization["qgroundcontrol_candidate_sha256"] == review["candidate_sha256"]
    gateway_url = "/api/v1/gateway/missions"
    with SessionLocal() as session:
        stored_review = session.get(SystemEvent, UUID(review["event_id"]))
        assert stored_review is not None
        verified_metadata = stored_review.event_metadata
        stored_review.event_metadata = {**verified_metadata, "candidate_sha256": "0" * 64}
        session.commit()
    rejected_claim = client.post(
        f"{gateway_url}/{mission['id']}/claim",
        headers=gateway_headers,
        json={"gateway_id": heartbeat["gateway_id"]},
    )
    assert rejected_claim.status_code == 409
    assert client.get(path, headers=admin_headers).json()["status"] == "AUTHORIZED"
    with SessionLocal() as session:
        stored_review = session.get(SystemEvent, UUID(review["event_id"]))
        assert stored_review is not None
        stored_review.event_metadata = verified_metadata
        session.commit()
    offered = client.get(f"{gateway_url}/authorized", headers=gateway_headers).json()
    assert offered[0]["mission_sha256"] == review["candidate_sha256"]
    claimed = client.post(
        f"{gateway_url}/{mission['id']}/claim",
        headers=gateway_headers,
        json={"gateway_id": heartbeat["gateway_id"]},
    )
    assert claimed.status_code == 200, claimed.text
    body = claimed.json()
    assert hashlib.sha256(body["mission_file"].encode()).hexdigest() == review["candidate_sha256"]
    assert json.loads(body["mission_file"])["plan_sha256"] == review["plan_sha256"]
    assert [item["command"] for item in body["mission"]["waypoints"]] == [22, 16, 20]


@pytest.mark.parametrize(
    ("index", "field", "value"),
    [
        (-1, "frame", 3),
        (-1, "autoContinue", False),
        (-1, "params", [0, 0, 0, 0, 1, 0, 0]),
        (-1, "params", []),
        (0, "params", ["invalid", 0, 0, None, 1, 2, 5]),
        (1, "Altitude", 100),
    ],
)
def test_review_rejects_invalid_or_inconsistent_plan_fields(
    index: int, field: str, value: object
) -> None:
    origin, destination = PlanPosition(1, 2), PlanPosition(3, 4)
    plan = json.loads(create_draft_plan(origin, destination, home_amsl_m=10, altitude_m=5))
    plan["mission"]["items"][index][field] = value
    with pytest.raises(ValueError):
        validate_reviewed_plan(json.dumps(plan), destination)


def test_review_requires_waypoint_even_when_initial_camera_item_present() -> None:
    origin, destination = PlanPosition(1, 2), PlanPosition(3, 4)
    plan = json.loads(create_draft_plan(origin, destination, home_amsl_m=10, altitude_m=5))
    plan["mission"]["items"].pop(1)
    plan["mission"]["items"].insert(
        0,
        {
            "type": "SimpleItem",
            "command": 530,
            "frame": 2,
            "autoContinue": True,
            "params": [0, 2, None, None, None, None, None],
        },
    )
    with pytest.raises(ValueError, match="sequência"):
        validate_reviewed_plan(json.dumps(plan), destination)
