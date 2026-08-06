import time
from collections import deque
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.exceptions import MissionUploadError, VehicleTimeoutError
from app.mavlink.pymavlink_gateway import PymavlinkVehicleGateway
from app.models import AuthorizedMission, MissionStatus, MissionWaypoint


class FakeMessage:
    def __init__(
        self,
        message_type: str,
        *,
        source_system: int = 1,
        source_component: int = 1,
        **fields: object,
    ) -> None:
        self._message_type = message_type
        self._source_system = source_system
        self._source_component = source_component
        self.target_system = 254
        self.mission_type = 0
        for name, value in fields.items():
            setattr(self, name, value)

    def get_type(self) -> str:
        return self._message_type

    def get_srcSystem(self) -> int:
        return self._source_system

    def get_srcComponent(self) -> int:
        return self._source_component


class MavRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def __getattr__(self, name: str):  # type: ignore[no-untyped-def]
        def record(*arguments: object) -> None:
            self.calls.append((name, arguments))

        return record


class FakeConnection:
    def __init__(self, messages: list[FakeMessage] | None = None) -> None:
        self.target_system = 1
        self.target_component = 1
        self.source_system = 254
        self.mav = MavRecorder()
        self.messages = deque(messages or [])

    def recv_match(self, **kwargs: object) -> FakeMessage | None:
        del kwargs
        return self.messages.popleft() if self.messages else None


def fake_mavutil() -> SimpleNamespace:
    constants = SimpleNamespace(
        MAV_MISSION_ACCEPTED=0,
        MAV_FRAME_GLOBAL=0,
        MAV_FRAME_GLOBAL_INT=5,
        MAV_FRAME_GLOBAL_RELATIVE_ALT=3,
        MAV_FRAME_GLOBAL_RELATIVE_ALT_INT=6,
        MAV_FRAME_GLOBAL_TERRAIN_ALT=10,
        MAV_FRAME_GLOBAL_TERRAIN_ALT_INT=11,
    )
    return SimpleNamespace(mavlink=constants, mode_string_v10=lambda message: "AUTO")


def mission_with_one_waypoint(*, label: str | None = None) -> AuthorizedMission:
    waypoint = MissionWaypoint(
        sequence=0,
        current=1,
        command=16,
        frame=3,
        latitude=-23.118,
        longitude=-46.551,
        altitude_m=10,
        label=label,
    )
    return AuthorizedMission(
        id=uuid4(),
        order_id=uuid4(),
        vehicle_id=uuid4(),
        status=MissionStatus.AUTHORIZED,
        origin_latitude=-23.1175,
        origin_longitude=-46.5502,
        destination_latitude=waypoint.latitude,
        destination_longitude=waypoint.longitude,
        takeoff_altitude_m=10,
        estimated_distance_m=100,
        mission_sha256="a" * 64,
        version=1,
        waypoints=[waypoint],
    )


def canonical_mission() -> AuthorizedMission:
    origin = (-23.1175, -46.5502)
    destination = (-23.118, -46.551)
    waypoints = [
        MissionWaypoint(
            sequence=0,
            current=1,
            command=16,
            latitude=origin[0],
            longitude=origin[1],
            altitude_m=0,
        ),
        MissionWaypoint(
            sequence=1,
            command=22,
            latitude=origin[0],
            longitude=origin[1],
            altitude_m=10,
        ),
        MissionWaypoint(
            sequence=2,
            command=16,
            latitude=destination[0],
            longitude=destination[1],
            altitude_m=10,
        ),
        MissionWaypoint(
            sequence=3,
            command=19,
            param1=5,
            latitude=destination[0],
            longitude=destination[1],
            altitude_m=10,
        ),
        MissionWaypoint(
            sequence=4,
            command=211,
            latitude=destination[0],
            longitude=destination[1],
            altitude_m=10,
        ),
        MissionWaypoint(
            sequence=5,
            command=16,
            latitude=origin[0],
            longitude=origin[1],
            altitude_m=10,
        ),
        MissionWaypoint(
            sequence=6,
            command=21,
            latitude=origin[0],
            longitude=origin[1],
            altitude_m=0,
        ),
    ]
    return AuthorizedMission(
        id=uuid4(),
        order_id=uuid4(),
        vehicle_id=uuid4(),
        status=MissionStatus.UPLOADING,
        origin_latitude=origin[0],
        origin_longitude=origin[1],
        destination_latitude=destination[0],
        destination_longitude=destination[1],
        takeoff_altitude_m=10,
        estimated_distance_m=100,
        mission_sha256="b" * 64,
        version=1,
        waypoints=waypoints,
    )


def set_fresh_position(
    gateway: PymavlinkVehicleGateway,
    latitude: float,
    longitude: float,
    *,
    armed: bool,
) -> datetime:
    sample_time = datetime.now(UTC)
    gateway._last_heartbeat_monotonic = time.monotonic()
    gateway._latitude = latitude
    gateway._longitude = longitude
    gateway._last_position_monotonic = time.monotonic()
    gateway._last_position_recorded_at = sample_time
    gateway._armed = armed
    return sample_time


def configured_gateway(
    messages: list[FakeMessage] | None = None,
) -> tuple[PymavlinkVehicleGateway, FakeConnection]:
    gateway = PymavlinkVehicleGateway(
        Settings(
            _env_file=None,
            mission_command_timeout_seconds=0.1,
            heartbeat_timeout_seconds=0.1,
            mission_protocol_retries=1,
        )
    )
    connection = FakeConnection(messages)
    gateway._connection = connection
    gateway._mavutil = fake_mavutil()  # type: ignore[assignment]
    return gateway, connection


def test_upload_rejects_early_ack_and_never_clears_existing_mission() -> None:
    gateway, connection = configured_gateway([FakeMessage("MISSION_ACK", type=0)])

    with pytest.raises(MissionUploadError, match="antes de todos"):
        gateway._upload_sync(mission_with_one_waypoint())

    call_names = [name for name, _arguments in connection.mav.calls]
    assert call_names == ["mission_count_send"]
    assert "mission_clear_all_send" not in call_names


def test_upload_filters_source_and_verifies_downloaded_content() -> None:
    mission = mission_with_one_waypoint()
    waypoint = mission.waypoints[0]
    messages = [
        FakeMessage("MISSION_ACK", source_system=99, type=0),
        FakeMessage("MISSION_REQUEST_INT", seq=0),
        FakeMessage("MISSION_ACK", type=0),
        FakeMessage("MISSION_COUNT", count=1),
        FakeMessage(
            "MISSION_ITEM_INT",
            seq=0,
            frame=6,
            command=waypoint.command,
            current=waypoint.current,
            autocontinue=waypoint.autocontinue,
            param1=waypoint.param1,
            param2=waypoint.param2,
            param3=waypoint.param3,
            param4=waypoint.param4,
            x=round(waypoint.latitude * 10_000_000),
            y=round(waypoint.longitude * 10_000_000),
            z=waypoint.altitude_m,
        ),
    ]
    gateway, connection = configured_gateway(messages)

    gateway._upload_sync(mission)
    gateway._verify_mission_sync(mission)

    call_names = [name for name, _arguments in connection.mav.calls]
    assert call_names == [
        "mission_count_send",
        "mission_item_int_send",
        "mission_request_list_send",
        "mission_request_int_send",
        "mission_ack_send",
    ]
    assert "mission_clear_all_send" not in call_names


@pytest.mark.asyncio
async def test_poll_rejects_stale_position_without_fabricating_timestamp() -> None:
    gateway, _connection = configured_gateway()
    old_sample = datetime.now(UTC) - timedelta(minutes=1)
    gateway._last_heartbeat_monotonic = time.monotonic()
    gateway._latitude = -23.118
    gateway._longitude = -46.551
    gateway._last_position_monotonic = time.monotonic() - 1
    gateway._last_position_recorded_at = old_sample

    with pytest.raises(VehicleTimeoutError, match="GLOBAL_POSITION_INT ficou vencido"):
        await gateway.poll_mission(mission_with_one_waypoint())

    assert gateway._last_position_recorded_at == old_sample


@pytest.mark.asyncio
async def test_mission_progress_is_explicit_ordered_and_conservative() -> None:
    gateway, _connection = configured_gateway()
    mission = canonical_mission()
    gateway._ingest_message(FakeMessage("MISSION_CURRENT", seq=2, mission_state=3))
    gateway._ingest_message(FakeMessage("MISSION_ITEM_REACHED", seq=2))
    gateway._ingest_message(FakeMessage("STATUSTEXT", severity=4, text=b"GPS variance"))
    sample_time = set_fresh_position(
        gateway,
        mission.destination_latitude,
        mission.destination_longitude,
        armed=True,
    )

    destination_poll = await gateway.poll_mission(mission)

    assert destination_poll.suggested_status is MissionStatus.DESTINATION_REACHED
    assert {event.event_type for event in destination_poll.events} == {
        "MAVLINK_MISSION_CURRENT",
        "MAVLINK_MISSION_ITEM_REACHED",
        "MAVLINK_STATUSTEXT",
        "MAVLINK_DESTINATION_SEQUENCE_CONFIRMED",
    }
    assert destination_poll.telemetry.recorded_at == sample_time

    gateway._ingest_message(FakeMessage("MISSION_CURRENT", seq=5, mission_state=3))
    set_fresh_position(
        gateway,
        mission.destination_latitude,
        mission.destination_longitude,
        armed=True,
    )
    delivery_poll = await gateway.poll_mission(mission)
    assert delivery_poll.suggested_status is MissionStatus.DELIVERY_CONFIRMED
    mechanism_event = next(
        event
        for event in delivery_poll.events
        if event.event_type == "MAVLINK_DELIVERY_MECHANISM_SEQUENCE_CONFIRMED"
    )
    assert "não comprova fisicamente o pacote" in mechanism_event.message

    return_poll = await gateway.poll_mission(mission)
    assert return_poll.suggested_status is MissionStatus.RETURNING
    assert {event.event_type for event in return_poll.events} == {"MAVLINK_RETURN_SEQUENCE_STARTED"}

    gateway._ingest_message(FakeMessage("MISSION_ITEM_REACHED", seq=6))
    set_fresh_position(
        gateway,
        mission.origin_latitude,
        mission.origin_longitude,
        armed=True,
    )
    armed_poll = await gateway.poll_mission(mission)
    assert armed_poll.suggested_status is None

    set_fresh_position(
        gateway,
        mission.destination_latitude,
        mission.destination_longitude,
        armed=False,
    )
    far_poll = await gateway.poll_mission(mission)
    assert far_poll.suggested_status is None

    set_fresh_position(
        gateway,
        mission.origin_latitude,
        mission.origin_longitude,
        armed=False,
    )
    completed_poll = await gateway.poll_mission(mission)
    assert completed_poll.suggested_status is MissionStatus.COMPLETED
    assert {event.event_type for event in completed_poll.events} == {
        "MAVLINK_LANDING_COMPLETION_CONFIRMED"
    }


@pytest.mark.asyncio
async def test_progress_synchronization_resumes_after_process_restart() -> None:
    gateway, _connection = configured_gateway()
    mission = canonical_mission()
    await gateway.synchronize_progress(mission, MissionStatus.DESTINATION_REACHED)
    gateway._ingest_message(FakeMessage("MISSION_CURRENT", seq=5, mission_state=3))
    set_fresh_position(
        gateway,
        mission.destination_latitude,
        mission.destination_longitude,
        armed=True,
    )

    poll = await gateway.poll_mission(mission)

    assert poll.suggested_status is MissionStatus.DELIVERY_CONFIRMED
    assert any(
        event.event_type == "MAVLINK_DELIVERY_MECHANISM_SEQUENCE_CONFIRMED" for event in poll.events
    )
