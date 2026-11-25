import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.missions import flight_observations
from app.modules.vehicles import service as vehicle_service
from tests.test_full_flow import _create_submitted_order


@pytest.fixture
def replay(client, gateway_headers, admin_headers, monkeypatch):
    class ReplayClock(datetime):
        value = datetime.now(UTC)

        @classmethod
        def now(cls, tz=None):
            return cls.value.astimezone(tz)

    monkeypatch.setattr(flight_observations, "datetime", ReplayClock)
    monkeypatch.setattr(vehicle_service, "datetime", ReplayClock)

    class Replay:
        vehicle_id = None
        source = "HARDWARE_REAL"

        def heartbeat(
            self,
            *,
            armed=True,
            mode="MISSION",
            landed=2,
            seq=0,
            state=3,
            plan=4242,
            lat=-23.1175,
            lon=-46.5502,
            altitude=10.0,
            speed=2.0,
            seconds=2,
            connected=True,
        ):
            ReplayClock.value += timedelta(seconds=seconds)
            timestamp = ReplayClock.value.isoformat()
            response = client.post(
                "/api/v1/gateway/heartbeat",
                headers=gateway_headers,
                json={
                    "gateway_id": "gateway-sitl-1",
                    "vehicle_identifier": "replay-px4",
                    "autopilot_system": "PX4",
                    "source": self.source,
                    "connected": connected,
                    "heartbeat": connected,
                    "armed": armed if connected else None,
                    "mavlink_system_id": 1,
                    "mavlink_component_id": 1,
                    "flight_mode": mode,
                    "last_heartbeat_at": timestamp if connected else None,
                    "current_latitude": lat if connected else None,
                    "current_longitude": lon if connected else None,
                    "current_altitude_m": altitude,
                    "current_ground_speed_m_s": speed,
                    "gps_fix_type": 3,
                    "px4_flight": {
                        "landed_state": landed,
                        "sequence": seq,
                        "native_plan_id": plan,
                        "mission_total": 3 if seq is not None else None,
                        "mission_state": state,
                        "mission_at": timestamp if seq is not None else None,
                        "position_at": timestamp,
                    },
                },
            )
            response.raise_for_status()
            self.vehicle_id = response.json()["vehicle"]["id"]
            return self.read()

        def event(self, kind, metadata):
            response = client.post(
                f"/api/v1/gateway/vehicles/{self.vehicle_id}/observations",
                headers=gateway_headers,
                json=[
                    {
                        "event_id": str(uuid.uuid4()),
                        "event_type": kind,
                        "severity": "INFO",
                        "message": "Mensagem reproduzida",
                        "metadata": {
                            "source_occurred_at": ReplayClock.value.isoformat(),
                            **metadata,
                        },
                    }
                ],
            )
            assert response.status_code == 204, response.text

        def read(self, mission_path=None):
            path = mission_path or f"/api/v1/admin/vehicles/{self.vehicle_id}"
            response = client.get(f"{path}/observed-flight", headers=admin_headers)
            response.raise_for_status()
            return response.json()

        def offline_for(self, seconds):
            ReplayClock.value += timedelta(seconds=seconds)

    return Replay()


@pytest.fixture
def exported(client, customer_headers, admin_headers, valid_point_payload):
    order = _create_submitted_order(client, customer_headers, valid_point_payload)
    order_path = f"/api/v1/admin/orders/{order['id']}"
    client.post(f"{order_path}/approve", headers=admin_headers).raise_for_status()
    mission = client.post(f"{order_path}/prepare-mission", headers=admin_headers).json()
    path = f"/api/v1/admin/missions/{mission['id']}"
    revision = {
        "expected_version": mission["version"],
        "expected_sha256": mission["mission_sha256"],
    }
    exported = client.post(f"{path}/qgroundcontrol-plan", headers=admin_headers, json=revision)
    exported.raise_for_status()
    return order_path, path, revision, exported


def event_types(flight):
    return [event["event_type"] for event in flight["events"]]


def test_arm_on_ground_then_takeoff_manual_and_disarm(client, replay, admin_headers):
    ground = replay.heartbeat(landed=1, altitude=0.3, speed=0.1)
    assert ground["phase"] == "ARMED_ON_GROUND"
    assert ground["sequence"] is None and "FLIGHT_MISSION" not in event_types(ground)
    replay.heartbeat(landed=3, mode="TAKEOFF")
    manual = replay.heartbeat(mode="POSCTL")
    assert manual["phase"] == "MANUAL" and manual["link"] == "UNASSOCIATED"
    assert {"FLIGHT_ARMED", "FLIGHT_TAKING_OFF", "FLIGHT_AIRBORNE", "FLIGHT_MANUAL"} <= set(
        event_types(manual)
    )
    assert replay.heartbeat(landed=4, mode="LAND")["phase"] == "LANDING"
    assert replay.heartbeat(landed=1, mode="LAND")["phase"] == "LANDED"
    ended = replay.heartbeat(landed=1, armed=False, mode="MANUAL")
    assert ended["phase"] == "DISARMED" and ended["ended_at"]
    assert ended["normal_completion"] is False


def test_position_estimate_requires_sustained_rise_motion_and_ground_baseline(replay):
    assert replay.heartbeat(armed=False, landed=None, seq=None, altitude=0, speed=0) is None
    armed = replay.heartbeat(landed=None, altitude=0.4, speed=3, mode="POSCTL")
    assert armed["phase"] == "ARMED"
    assert replay.heartbeat(landed=None, altitude=3.5, speed=1.6, mode="POSCTL")["phase"] == "ARMED"
    flight = replay.heartbeat(landed=None, altitude=3.8, speed=1.8, mode="POSCTL")
    assert flight["phase"] == "MANUAL" and flight["estimated"]
    no_landing = replay.heartbeat(landed=None, armed=False)
    assert no_landing["phase"] == "DISARMED" and no_landing["ended_at"] is None
    assert "FLIGHT_LANDED" not in event_types(no_landing)


@pytest.mark.parametrize("early", [False, True])
def test_verified_plan_execution_and_return_without_completing_order(
    client, replay, exported, admin_headers, early
):
    order, path, revision, exported_plan = exported
    replay.heartbeat(armed=False, landed=1, altitude=0)
    review = client.post(
        f"{path}/qgroundcontrol-review",
        headers=admin_headers,
        json={**revision, "plan": exported_plan.text, "confirmed": True},
    )
    review.raise_for_status()
    replay.event(
        "PX4_PHYSICAL_PLAN_READBACK",
        {
            "native_plan_id": 4242,
            "system_id": 1,
            "component_id": 1,
            "item_count": 3,
            "plan_sha256": review.json()["plan_sha256"],
        },
    )
    assert replay.heartbeat(landed=1)["mission_id"] is None
    assert replay.read(path) is None
    executing = replay.heartbeat()
    assert executing["link"] == "VERIFIED" and executing["phase"] == "MISSION"
    assert (
        executing["sequence"],
        executing["destination_sequence"],
        executing["return_sequence"],
    ) == (0, 1, 2)
    if not early:
        assert replay.heartbeat(seq=1)["sequence"] == 1
        reached = {"sequence": 1, "system_id": 1, "component_id": 1, "native_plan_id": 4242}
        replay.event("MAVLINK_MISSION_ITEM_REACHED", reached)
        replay.event("MAVLINK_MISSION_ITEM_REACHED", reached)
        reached_flight = replay.read(path)
        assert reached_flight["destination"] == "CONFIRMED"
        assert reached_flight["reached_sequences"] == [1]
        assert event_types(reached_flight).count("FLIGHT_ITEM_REACHED") == 1
    returning = replay.heartbeat(mode="RTL" if early else "MISSION", seq=0 if early else 2)
    assert returning["phase"] == "RETURNING" and returning["early_return"] is early
    assert returning["normal_completion"] is False
    assert replay.heartbeat(mode="RTL", landed=4, state=3 if early else 5)["phase"] == "LANDING"
    replay.heartbeat(mode="LAND", landed=1, state=3 if early else 5)
    ended = replay.heartbeat(armed=False, mode="MANUAL", landed=1, state=3 if early else 5)
    assert ended["ended_at"] and ended["normal_completion"] is (not early)
    assert client.get(order, headers=admin_headers).json()["status"] == "MISSION_READY"


@pytest.mark.parametrize("source", ["HARDWARE_REAL", "SITL"])
def test_manual_association_reconnection_pause_and_divergence(
    client, replay, exported, admin_headers, customer_headers, source
):
    replay.source = source
    order, path, revision, _ = exported
    replay.heartbeat(armed=False, landed=1, altitude=0)
    body = {**revision, "vehicle_id": replay.vehicle_id}
    endpoint = f"{path}/observed-flight"
    assert client.post(endpoint, headers=customer_headers, json=body).status_code == 403
    associated = client.post(endpoint, headers=admin_headers, json=body).json()
    assert associated["link"] == "OPERATOR" and associated["associated_by"]
    assert associated["source"] == source
    assert associated["vehicle_name"]
    assert associated["phase"] == "WAITING"
    assert client.post(endpoint, headers=admin_headers, json=body).status_code == 200
    assert event_types(replay.read(path)).count("FLIGHT_ASSOCIATED") == 1
    assert replay.heartbeat(landed=1)["phase"] == "ARMED_ON_GROUND"
    active = replay.heartbeat(seq=1)
    assert active["phase"] == "MISSION" and active["destination_sequence"] is None
    assert active["sequence"] == 1 and active["distance_m"] > 0
    assert replay.heartbeat(seq=1, state=4, mode="LOITER")["phase"] == "PAUSED"
    replay.heartbeat(seq=1)
    replay.heartbeat(seq=1, lat=-23.117, lon=-46.55)
    estimated = replay.heartbeat(seq=1, lat=-23.117, lon=-46.55)
    assert estimated["destination"] == "ESTIMATED"
    replay.offline_for(20)
    lost = replay.read(path)
    assert lost["phase"] == "MISSION" and lost["stale"] is True and lost["ended_at"] is None
    replay.heartbeat(connected=False)
    restored = replay.heartbeat(seq=1)
    assert restored["phase"] == "MISSION" and restored["stale"] is False
    assert event_types(restored).count("FLIGHT_LINK_RESTORED") == 1
    assert event_types(restored).count("FLIGHT_TAKING_OFF") == 0
    assert len(restored["track"]) == 2
    divergent = replay.heartbeat(seq=1, plan=4243)
    assert divergent["link"] == "DIVERGENT"
    assert divergent["sequence"] is None and divergent["reached_sequences"] == []
    assert client.get(order, headers=admin_headers).json()["status"] == "MISSION_READY"
