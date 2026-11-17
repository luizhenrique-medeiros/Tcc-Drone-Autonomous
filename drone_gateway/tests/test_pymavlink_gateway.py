import time
from collections import deque
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.config import MavlinkMode, Settings
from app.core.exceptions import (
    MissionUploadError,
    UnsafeOperationError,
    VehiclePortBusyError,
    VehiclePortNotFoundError,
    VehicleTimeoutError,
)
from app.mavlink.pymavlink_gateway import PymavlinkVehicleGateway
from app.models import AuthorizedMission, ConnectionState, MissionStatus, MissionWaypoint
from app.telemetry.normalizer import normalize_telemetry


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
        self.target_component = 190
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
        self.source_component = 190
        self.mav = MavRecorder()
        self.messages = deque(messages or [])
        self.closed = False

    def recv_match(self, **kwargs: object) -> FakeMessage | None:
        del kwargs
        return self.messages.popleft() if self.messages else None

    def close(self) -> None:
        self.closed = True


class AckAfterCommandConnection(FakeConnection):
    def recv_match(self, **kwargs: object) -> FakeMessage | None:
        if kwargs.get("blocking") is False:
            return None
        return super().recv_match(**kwargs)


class QueuedArmConnection(AckAfterCommandConnection):
    def __init__(self, backlog: list[FakeMessage], replies: list[FakeMessage]) -> None:
        super().__init__(replies)
        self.backlog = deque(backlog)

    def recv_match(self, **kwargs: object) -> FakeMessage | None:
        if kwargs.get("blocking") is False and self.backlog:
            return self.backlog.popleft()
        return super().recv_match(**kwargs)


def fake_mavutil() -> SimpleNamespace:
    constants = SimpleNamespace(
        MAV_MISSION_ACCEPTED=0,
        MAV_FRAME_GLOBAL=0,
        MAV_FRAME_GLOBAL_INT=5,
        MAV_FRAME_GLOBAL_RELATIVE_ALT=3,
        MAV_FRAME_GLOBAL_RELATIVE_ALT_INT=6,
        MAV_FRAME_GLOBAL_TERRAIN_ALT=10,
        MAV_FRAME_GLOBAL_TERRAIN_ALT_INT=11,
        MAV_AUTOPILOT_INVALID=8,
        MAV_AUTOPILOT_ARDUPILOTMEGA=3,
        MAV_MODE_FLAG_SAFETY_ARMED=128,
        MAV_TYPE_GCS=6,
        MAV_STATE_ACTIVE=4,
        MAV_CMD_SET_MESSAGE_INTERVAL=511,
        MAV_CMD_GET_HOME_POSITION=410,
        MAV_CMD_MISSION_START=300,
        MAV_CMD_DO_PAUSE_CONTINUE=193,
        MAV_CMD_NAV_RETURN_TO_LAUNCH=20,
        MAV_CMD_COMPONENT_ARM_DISARM=400,
        MAV_RESULT_ACCEPTED=0,
        MAV_RESULT_IN_PROGRESS=5,
        MAVLINK_MSG_ID_SYS_STATUS=1,
        MAVLINK_MSG_ID_BATTERY_STATUS=147,
        MAVLINK_MSG_ID_GPS_RAW_INT=24,
        MAVLINK_MSG_ID_GLOBAL_POSITION_INT=33,
        MAVLINK_MSG_ID_EKF_STATUS_REPORT=193,
        MAVLINK_MSG_ID_HOME_POSITION=242,
        MAVLINK_MSG_ID_MISSION_CURRENT=42,
    )
    return SimpleNamespace(
        mavlink=constants,
        mode_string_v10=lambda message: getattr(message, "mode_string", "AUTO"),
    )


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
            allow_mission_upload=True,
        )
    )
    connection = FakeConnection(messages)
    gateway._connection = connection
    gateway._mavutil = fake_mavutil()  # type: ignore[assignment]
    return gateway, connection


def configured_arm_gateway(
    messages: list[FakeMessage] | None = None,
    *,
    mode: str = "STABILIZE",
    preflight_ok: bool = True,
    timeout: float = 0.08,
    step_timeout: float = 0.02,
) -> tuple[PymavlinkVehicleGateway, AckAfterCommandConnection]:
    gateway = PymavlinkVehicleGateway(
        Settings(
            _env_file=None,
            allow_vehicle_arm=True,
            allow_flight_commands=True,
            allow_mission_start=True,
            mission_command_timeout_seconds=timeout,
            mission_protocol_step_timeout_seconds=step_timeout,
        )
    )
    connection = AckAfterCommandConnection(messages)
    gateway._connection = connection
    gateway._mavutil = fake_mavutil()  # type: ignore[assignment]
    gateway._last_heartbeat_monotonic = time.monotonic()
    gateway._mode = mode
    gateway._armed = False
    gateway._preflight_ok = preflight_ok
    gateway._last_message_monotonic["SYS_STATUS"] = time.monotonic()
    return gateway, connection


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "expected_endpoint"),
    [
        (MavlinkMode.DIRECT, "COM42"),
        (MavlinkMode.MISSION_PLANNER_FORWARD, "udpin:127.0.0.1:14551"),
    ],
)
async def test_unacknowledged_hardware_connect_is_receive_only_and_reports_topology(
    monkeypatch: pytest.MonkeyPatch,
    mode: MavlinkMode,
    expected_endpoint: str,
) -> None:
    settings = Settings(
        _env_file=None,
        mavlink_mode=mode,
        mavlink_connection="COM42",
        mavlink_forward_connection="udpin:127.0.0.1:14551",
        heartbeat_timeout_seconds=0.1,
    )
    gateway = PymavlinkVehicleGateway(settings)
    connection = FakeConnection(
        [
            FakeMessage(
                "HEARTBEAT",
                autopilot=3,
                base_mode=0,
            )
        ]
    )
    module = fake_mavutil()
    open_calls: list[tuple[str, dict[str, object]]] = []

    def open_connection(endpoint: str, **kwargs: object) -> FakeConnection:
        open_calls.append((endpoint, kwargs))
        return connection

    module.mavlink_connection = open_connection
    monkeypatch.setattr(gateway, "_load_mavutil", lambda: module)
    monkeypatch.setattr(gateway, "_validate_serial_port_exists", lambda: None)

    await gateway.connect()
    health = await gateway.read_health()

    assert open_calls[0][0] == expected_endpoint
    assert open_calls[0][1]["source_component"] == 190
    assert open_calls[0][1]["dialect"] == "ardupilotmega"
    assert connection.mav.calls == []
    assert health.connection_state is ConnectionState.CONNECTED
    assert health.connection_endpoint == expected_endpoint
    assert health.serial_port == "COM42"
    assert health.connection_baud == 57600
    assert health.connection_topology == mode.value
    assert not health.mission_upload_enabled
    assert not health.flight_commands_enabled
    assert not health.mission_start_enabled
    assert not health.vehicle_arm_enabled
    await gateway.close()
    assert connection.closed


def test_serial_errors_keep_missing_and_busy_cases_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        mavlink_mode=MavlinkMode.DIRECT,
        mavlink_connection="COM42",
    )
    gateway = PymavlinkVehicleGateway(settings)
    monkeypatch.setattr("app.mavlink.pymavlink_gateway.list_serial_ports", lambda: [])

    with pytest.raises(VehiclePortNotFoundError, match="COM42"):
        gateway._validate_serial_port_exists()

    translated = gateway._translate_connection_error(PermissionError(13, "Access is denied"))
    assert isinstance(translated, VehiclePortBusyError)
    assert "ocupada ou com acesso negado" in str(translated)
    assert "mission_planner_forward" in str(translated)


@pytest.mark.asyncio
async def test_open_without_heartbeat_closes_resource_and_sets_error_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        mavlink_mode=MavlinkMode.DIRECT,
        mavlink_connection="COM42",
        heartbeat_timeout_seconds=0.01,
    )
    gateway = PymavlinkVehicleGateway(settings)
    connection = FakeConnection()
    module = fake_mavutil()
    module.mavlink_connection = lambda *args, **kwargs: connection
    monkeypatch.setattr(gateway, "_load_mavutil", lambda: module)
    monkeypatch.setattr(gateway, "_validate_serial_port_exists", lambda: None)

    with pytest.raises(VehicleTimeoutError, match="nenhum heartbeat ArduPilot"):
        await gateway.connect()

    assert connection.closed
    assert gateway._connection is None
    assert gateway.connection_state is ConnectionState.ERROR
    assert gateway.connection_error is not None
    health = await gateway.read_health()
    assert health.connected is False
    assert health.heartbeat is False
    assert health.connection_state is ConnectionState.ERROR
    assert health.connection_error == gateway.connection_error


def test_set_message_interval_waits_through_in_progress_ack() -> None:
    acknowledgements = [
        FakeMessage("COMMAND_ACK", source_system=99, command=511, result=0),
        FakeMessage("COMMAND_ACK", command=511, result=5),
        FakeMessage("COMMAND_ACK", command=511, result=0),
        *[FakeMessage("COMMAND_ACK", command=511, result=0) for _ in range(6)],
    ]
    gateway, connection = configured_gateway(acknowledgements)

    assert gateway._request_message_intervals()
    interval_calls = [call for call in connection.mav.calls if call[0] == "command_long_send"]
    assert len(interval_calls) == 7


def test_legacy_mission_request_is_answered_with_item_int() -> None:
    gateway, connection = configured_gateway(
        [
            FakeMessage("MISSION_REQUEST", seq=0),
            FakeMessage("MISSION_ACK", type=0),
        ]
    )

    gateway._upload_sync(mission_with_one_waypoint())

    call_names = [name for name, _arguments in connection.mav.calls]
    assert "mission_item_int_send" in call_names
    assert "mission_item_send" not in call_names


def test_upload_retries_each_protocol_step_before_timeout() -> None:
    gateway, connection = configured_gateway()

    with pytest.raises(VehicleTimeoutError, match="retries da etapa esgotados"):
        gateway._upload_sync(mission_with_one_waypoint())

    call_names = [name for name, _arguments in connection.mav.calls]
    assert call_names.count("mission_count_send") == 2


@pytest.mark.asyncio
async def test_upload_and_flight_commands_require_flags_and_live_heartbeat() -> None:
    mission = mission_with_one_waypoint()
    gateway = PymavlinkVehicleGateway(Settings(_env_file=None))
    gateway._connection = FakeConnection()
    gateway._mavutil = fake_mavutil()  # type: ignore[assignment]
    gateway._last_heartbeat_monotonic = time.monotonic()

    with pytest.raises(UnsafeOperationError, match="ALLOW_MISSION_UPLOAD"):
        await gateway.upload_mission(mission, "unused")
    with pytest.raises(UnsafeOperationError, match="ALLOW_FLIGHT_COMMANDS"):
        await gateway.request_rtl()
    with pytest.raises(UnsafeOperationError, match="ALLOW_FLIGHT_COMMANDS"):
        await gateway.pause_mission()
    with pytest.raises(UnsafeOperationError, match="ALLOW_FLIGHT_COMMANDS"):
        await gateway.continue_mission()
    with pytest.raises(UnsafeOperationError, match="ALLOW_FLIGHT_COMMANDS"):
        await gateway.start_mission(mission)

    stale_gateway = PymavlinkVehicleGateway(Settings(_env_file=None, allow_mission_upload=True))
    stale_gateway._connection = FakeConnection()
    stale_gateway._mavutil = fake_mavutil()  # type: ignore[assignment]
    with pytest.raises(VehicleTimeoutError, match="heartbeat"):
        await stale_gateway.upload_mission(mission, "unused")


@pytest.mark.asyncio
async def test_arm_sends_only_normal_command_and_requires_strict_ack_plus_new_heartbeat() -> None:
    gateway, connection = configured_arm_gateway(
        [
            FakeMessage("COMMAND_ACK", source_system=99, command=400, result=0),
            FakeMessage("COMMAND_ACK", command=400, result=0, target_system=99),
            FakeMessage("COMMAND_ACK", command=400, result=0, target_component=99),
            FakeMessage("COMMAND_ACK", command=400, result=0),
            FakeMessage("HEARTBEAT", base_mode=128),
        ]
    )

    result = await gateway.arm_vehicle()

    arm_calls = [
        arguments
        for name, arguments in connection.mav.calls
        if name == "command_long_send" and arguments[2] == 400
    ]
    assert len(arm_calls) == 1
    assert arm_calls[0][3] == 0
    assert arm_calls[0][4] == 1
    assert arm_calls[0][5:] == (0, 0, 0, 0, 0, 0)
    assert gateway._armed is True
    assert result.command_sent
    assert result.command_acknowledged
    assert result.armed_heartbeat_confirmed
    assert not result.external_state_reconciled


@pytest.mark.asyncio
async def test_arm_is_blocked_by_gate_mode_and_stale_or_failed_preflight() -> None:
    disabled = PymavlinkVehicleGateway(Settings(_env_file=None))
    with pytest.raises(UnsafeOperationError, match="ALLOW_VEHICLE_ARM"):
        await disabled.arm_vehicle()

    inconsistent, inconsistent_connection = configured_arm_gateway()
    inconsistent._settings = inconsistent._settings.model_copy(
        update={"allow_mission_start": False}
    )
    with pytest.raises(UnsafeOperationError, match="ALLOW_MISSION_START"):
        await inconsistent.arm_vehicle()
    assert not any(name == "command_long_send" for name, _ in inconsistent_connection.mav.calls)

    wrong_mode, wrong_mode_connection = configured_arm_gateway(mode="AUTO")
    with pytest.raises(UnsafeOperationError, match="STABILIZE"):
        await wrong_mode.arm_vehicle()
    assert not any(name == "command_long_send" for name, _ in wrong_mode_connection.mav.calls)

    failed_preflight, _ = configured_arm_gateway(preflight_ok=False)
    with pytest.raises(UnsafeOperationError, match="preflight aprovado"):
        await failed_preflight.arm_vehicle()

    stale_preflight, _ = configured_arm_gateway()
    stale_preflight._last_message_monotonic["SYS_STATUS"] = (
        time.monotonic() - stale_preflight._settings.mavlink_telemetry_stale_seconds - 0.1
    )
    with pytest.raises(UnsafeOperationError, match="SYS_STATUS fresco"):
        await stale_preflight.arm_vehicle()


@pytest.mark.asyncio
async def test_arm_accepted_ack_without_new_armed_heartbeat_is_not_success() -> None:
    gateway, _connection = configured_arm_gateway(
        [FakeMessage("COMMAND_ACK", command=400, result=0)],
        timeout=0.03,
        step_timeout=0.01,
    )

    with pytest.raises(VehicleTimeoutError, match="heartbeat novo"):
        await gateway.arm_vehicle()


@pytest.mark.asyncio
async def test_arm_new_armed_then_disarmed_heartbeat_without_ack_is_never_resent() -> None:
    gateway, connection = configured_arm_gateway(
        [
            FakeMessage("HEARTBEAT", base_mode=128, mode_string="STABILIZE"),
            FakeMessage("HEARTBEAT", base_mode=0, mode_string="STABILIZE"),
        ],
        timeout=0.06,
        step_timeout=0.02,
    )

    with pytest.raises(VehicleTimeoutError, match="resultado é incerto"):
        await gateway.arm_vehicle()

    arm_calls = [
        arguments
        for name, arguments in connection.mav.calls
        if name == "command_long_send" and arguments[2] == 400
    ]
    assert len(arm_calls) == 1
    assert gateway._armed is False


@pytest.mark.asyncio
async def test_arm_preparation_race_reports_external_state_without_sending_command() -> None:
    gateway, _ = configured_arm_gateway()
    connection = FakeConnection([FakeMessage("HEARTBEAT", base_mode=128, mode_string="STABILIZE")])
    gateway._connection = connection

    result = await gateway.arm_vehicle()

    assert not any(name == "command_long_send" for name, _ in connection.mav.calls)
    assert not result.command_sent
    assert not result.command_acknowledged
    assert result.armed_heartbeat_confirmed
    assert result.external_state_reconciled


@pytest.mark.asyncio
async def test_arm_drains_preexisting_ack_before_starting_transaction() -> None:
    gateway, _ = configured_arm_gateway(timeout=0.04, step_timeout=0.01)
    connection = FakeConnection([FakeMessage("COMMAND_ACK", command=400, result=0)])
    gateway._connection = connection

    with pytest.raises(VehicleTimeoutError, match="COMMAND_ACK"):
        await gateway.arm_vehicle()

    arm_calls = [
        arguments
        for name, arguments in connection.mav.calls
        if name == "command_long_send" and arguments[2] == 400
    ]
    assert [arguments[3] for arguments in arm_calls] == [0, 1, 2]


@pytest.mark.asyncio
async def test_arm_terminal_rejection_is_not_retried() -> None:
    gateway, connection = configured_arm_gateway(
        [FakeMessage("COMMAND_ACK", command=400, result=4)]
    )

    with pytest.raises(UnsafeOperationError, match="rejeitado"):
        await gateway.arm_vehicle()

    arm_calls = [
        arguments
        for name, arguments in connection.mav.calls
        if name == "command_long_send" and arguments[2] == 400
    ]
    assert len(arm_calls) == 1


@pytest.mark.asyncio
async def test_health_consumes_burst_instead_of_publishing_old_head_of_queue() -> None:
    gateway, connection = configured_gateway(
        [FakeMessage("HEARTBEAT", base_mode=0, mode_string="STABILIZE")]
        + [FakeMessage("ATTITUDE") for _ in range(1_200)]
        + [
            FakeMessage("GPS_RAW_INT", fix_type=3, satellites_visible=24),
            FakeMessage("HEARTBEAT", base_mode=128, mode_string="AUTO"),
        ]
    )

    health = await gateway.read_health()

    assert not connection.messages
    assert health.connected
    assert health.satellites == 24
    assert health.armed is True
    assert health.flight_mode == "AUTO"
    assert not any(name == "command_long_send" for name, _ in connection.mav.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("burst_size", [500, 501, 2_500])
async def test_arm_consumes_finite_burst_and_requires_post_send_ack(burst_size: int) -> None:
    gateway, _ = configured_arm_gateway(timeout=1, step_timeout=0.05)
    connection = QueuedArmConnection(
        [FakeMessage("ATTITUDE") for _ in range(burst_size)]
        + [FakeMessage("COMMAND_ACK", command=400, result=0)],
        [
            FakeMessage("COMMAND_ACK", command=400, result=0),
            FakeMessage("HEARTBEAT", base_mode=128, mode_string="STABILIZE"),
        ],
    )
    gateway._connection = connection

    result = await gateway.arm_vehicle()

    assert not connection.backlog
    assert result.command_sent and result.command_acknowledged
    assert result.armed_heartbeat_confirmed
    arm_calls = [args for name, args in connection.mav.calls if name == "command_long_send"]
    assert len(arm_calls) == 1
    assert arm_calls[0][2:] == (400, 0, 1, 0, 0, 0, 0, 0, 0)


@pytest.mark.asyncio
async def test_arm_large_burst_old_ack_is_not_confirmation_or_reason_to_resend() -> None:
    gateway, _ = configured_arm_gateway(timeout=0.08, step_timeout=0.02)
    connection = QueuedArmConnection(
        [FakeMessage("ATTITUDE") for _ in range(700)]
        + [FakeMessage("COMMAND_ACK", command=400, result=0)],
        [FakeMessage("HEARTBEAT", base_mode=128, mode_string="STABILIZE")],
    )
    gateway._connection = connection

    with pytest.raises(VehicleTimeoutError, match="resultado é incerto"):
        await gateway.arm_vehicle()

    assert not connection.backlog
    assert len([name for name, _ in connection.mav.calls if name == "command_long_send"]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("tail_state", ["preflight_failed", "wrong_mode", "already_armed"])
async def test_arm_checks_latest_state_after_large_burst(tail_state: str) -> None:
    gateway, _ = configured_arm_gateway(timeout=1)
    tail = {
        "preflight_failed": FakeMessage(
            "SYS_STATUS",
            battery_remaining=80,
            voltage_battery=15000,
            onboard_control_sensors_health=0,
        ),
        "wrong_mode": FakeMessage("HEARTBEAT", base_mode=0, mode_string="AUTO"),
        "already_armed": FakeMessage("HEARTBEAT", base_mode=128, mode_string="STABILIZE"),
    }[tail_state]
    connection = FakeConnection([FakeMessage("ATTITUDE") for _ in range(700)] + [tail])
    gateway._connection = connection

    if tail_state == "already_armed":
        result = await gateway.arm_vehicle()
        assert result.external_state_reconciled and not result.command_sent
    else:
        with pytest.raises(UnsafeOperationError, match=r"preflight|STABILIZE"):
            await gateway.arm_vehicle()
    assert not any(name == "command_long_send" for name, _ in connection.mav.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["health", "arm"])
async def test_receive_drain_deadline_blocks_continuous_stream_without_commands(
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    clock = [1_000.0]

    class ContinuousConnection(FakeConnection):
        read_count = 0

        def recv_match(self, **kwargs: object) -> FakeMessage:
            assert kwargs.get("blocking") is False
            self.read_count += 1
            clock[0] += 0.02
            return FakeMessage("HEARTBEAT", base_mode=0, mode_string="STABILIZE")

    gateway, _ = configured_arm_gateway(timeout=0.08)
    connection = ContinuousConnection()
    gateway._connection = connection
    monkeypatch.setattr(
        "app.mavlink.pymavlink_gateway.time",
        SimpleNamespace(monotonic=lambda: clock[0]),
    )

    if operation == "arm":
        with pytest.raises(UnsafeOperationError, match="fila MAVLink"):
            await gateway.arm_vehicle()
    else:
        health = await gateway.read_health()
        assert not health.connected and not health.heartbeat
        assert health.connection_state is ConnectionState.STALE
        assert "fila MAVLink" in (health.connection_error or "")
    assert connection.read_count <= 6
    assert not any(name == "command_long_send" for name, _ in connection.mav.calls)


@pytest.mark.asyncio
async def test_receive_drain_packet_cap_fails_closed_then_recovers_when_queue_empties(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.mavlink.pymavlink_gateway.time",
        SimpleNamespace(monotonic=lambda: 1_000.0),
    )
    gateway, connection = configured_gateway(
        [FakeMessage("HEARTBEAT", base_mode=0, mode_string="STABILIZE")]
        + [FakeMessage("ATTITUDE") for _ in range(10_100)]
    )

    health = await gateway.read_health()
    assert not health.connected and not health.heartbeat
    assert health.armed is None
    assert health.connection_state is ConnectionState.STALE
    assert len(connection.messages) == 101
    with pytest.raises(VehicleTimeoutError, match="heartbeat"):
        await gateway.upload_mission(mission_with_one_waypoint(), "unused")

    connection.messages.append(FakeMessage("HEARTBEAT", base_mode=0, mode_string="STABILIZE"))
    health = await gateway.read_health()
    assert health.connected and health.armed is False
    assert health.connection_error is None
    assert not connection.messages
    assert not any(name == "command_long_send" for name, _ in connection.mav.calls)


@pytest.mark.asyncio
async def test_arm_packet_cap_blocks_unending_fast_stream_without_sending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ContinuousConnection(FakeConnection):
        read_count = 0

        def recv_match(self, **kwargs: object) -> FakeMessage:
            assert kwargs.get("blocking") is False
            self.read_count += 1
            return FakeMessage("ATTITUDE")

    gateway, _ = configured_arm_gateway()
    connection = ContinuousConnection()
    gateway._connection = connection
    monkeypatch.setattr(
        "app.mavlink.pymavlink_gateway.time",
        SimpleNamespace(monotonic=lambda: 1_000.0),
    )
    with pytest.raises(UnsafeOperationError, match="nenhum ARM foi enviado"):
        await gateway.arm_vehicle()
    assert connection.read_count == 10_000
    assert not any(name == "command_long_send" for name, _ in connection.mav.calls)


@pytest.mark.asyncio
async def test_arm_missing_ack_has_bounded_same_transaction_retries() -> None:
    gateway, connection = configured_arm_gateway(
        timeout=0.06,
        step_timeout=0.01,
    )

    with pytest.raises(VehicleTimeoutError, match="COMMAND_ACK"):
        await gateway.arm_vehicle()

    arm_calls = [
        arguments
        for name, arguments in connection.mav.calls
        if name == "command_long_send" and arguments[2] == 400
    ]
    assert [arguments[3] for arguments in arm_calls] == [0, 1, 2]


@pytest.mark.asyncio
async def test_pause_and_continue_use_command_long_and_require_ack() -> None:
    settings = Settings(_env_file=None, allow_flight_commands=True)
    gateway = PymavlinkVehicleGateway(settings)
    connection = AckAfterCommandConnection(
        [
            FakeMessage("COMMAND_ACK", command=193, result=0),
            FakeMessage("COMMAND_ACK", command=193, result=0),
        ]
    )
    gateway._connection = connection
    gateway._mavutil = fake_mavutil()  # type: ignore[assignment]
    gateway._last_heartbeat_monotonic = time.monotonic()

    await gateway.pause_mission()
    await gateway.continue_mission()

    command_calls = [
        arguments
        for name, arguments in connection.mav.calls
        if name == "command_long_send" and arguments[2] == 193
    ]
    assert [arguments[4] for arguments in command_calls] == [0, 1]


def test_upload_rejects_early_ack_and_never_clears_existing_mission() -> None:
    gateway, connection = configured_gateway([FakeMessage("MISSION_ACK", type=0)])

    with pytest.raises(MissionUploadError, match="antes de todos"):
        gateway._upload_sync(mission_with_one_waypoint())

    call_names = [name for name, _arguments in connection.mav.calls]
    assert call_names == ["mission_count_send", "heartbeat_send"]
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
        "heartbeat_send",
        "mission_item_int_send",
        "mission_request_list_send",
        "mission_request_int_send",
        "mission_ack_send",
    ]
    assert "mission_clear_all_send" not in call_names


def downloaded_waypoint(
    waypoint: MissionWaypoint,
    *,
    message_type: str = "MISSION_ITEM_INT",
    **changes: object,
) -> FakeMessage:
    scale = 10_000_000 if message_type == "MISSION_ITEM_INT" else 1
    fields: dict[str, object] = {
        "seq": waypoint.sequence,
        "frame": waypoint.frame,
        "command": waypoint.command,
        "current": 0,
        "autocontinue": waypoint.autocontinue,
        "param1": waypoint.param1,
        "param2": waypoint.param2,
        "param3": waypoint.param3,
        "param4": waypoint.param4,
        "x": round(waypoint.latitude * scale) if scale != 1 else waypoint.latitude,
        "y": round(waypoint.longitude * scale) if scale != 1 else waypoint.longitude,
        "z": waypoint.altitude_m,
    }
    fields.update(changes)
    return FakeMessage(message_type, **fields)


@pytest.mark.parametrize("message_type", ["MISSION_ITEM_INT", "MISSION_ITEM"])
@pytest.mark.parametrize("frames", [(0, 5), (3, 6), (10, 11)])
@pytest.mark.parametrize("reverse", [False, True])
def test_readback_accepts_only_equivalent_global_frames(
    message_type: str, frames: tuple[int, int], reverse: bool
) -> None:
    expected_frame, actual_frame = frames[::-1] if reverse else frames
    waypoint = canonical_mission().waypoints[2].model_copy(update={"frame": expected_frame})
    gateway, _connection = configured_gateway()

    gateway._verify_downloaded_waypoint(
        downloaded_waypoint(waypoint, message_type=message_type, frame=actual_frame), waypoint
    )


@pytest.mark.parametrize("current", [0, 1])
def test_readback_current_is_runtime_state(current: int) -> None:
    waypoint = canonical_mission().waypoints[2].model_copy(update={"current": 1 - current})
    gateway, _connection = configured_gateway()

    gateway._verify_downloaded_waypoint(downloaded_waypoint(waypoint, current=current), waypoint)


@pytest.mark.parametrize("frame", [0, 2, 3, 6])
def test_readback_gripper_accepts_nonpositional_frame_without_ignoring_parameters(
    frame: int,
) -> None:
    waypoint = canonical_mission().waypoints[4]
    gateway, _connection = configured_gateway()
    actual = downloaded_waypoint(waypoint, frame=frame, x=0, y=0, z=0)

    gateway._verify_downloaded_waypoint(actual, waypoint)
    actual.param2 = 1
    with pytest.raises(MissionUploadError, match="param2"):
        gateway._verify_downloaded_waypoint(actual, waypoint)


@pytest.mark.parametrize("message_type", ["MISSION_ITEM_INT", "MISSION_ITEM"])
@pytest.mark.parametrize(("sequence", "field"), [(3, "param3"), (6, "param4")])
def test_readback_accepts_arducopter_default_direction_encoding(
    sequence: int, field: str, message_type: str
) -> None:
    waypoint = canonical_mission().waypoints[sequence]
    assert getattr(waypoint, field) == 0
    gateway, _connection = configured_gateway()

    gateway._verify_downloaded_waypoint(
        downloaded_waypoint(waypoint, message_type=message_type, **{field: 1.0}), waypoint
    )


@pytest.mark.parametrize(("sequence", "field"), [(3, "param3"), (6, "param4")])
@pytest.mark.parametrize("value", [-1.0, 2.0, float("nan"), float("inf")])
def test_readback_rejects_other_default_direction_changes(
    sequence: int, field: str, value: float
) -> None:
    waypoint = canonical_mission().waypoints[sequence]
    gateway, _connection = configured_gateway()

    with pytest.raises(MissionUploadError, match=field):
        gateway._verify_downloaded_waypoint(
            downloaded_waypoint(waypoint, **{field: value}), waypoint
        )


@pytest.mark.parametrize(("sequence", "field"), [(3, "param3"), (6, "param4")])
@pytest.mark.parametrize("planned", [-1.0, 2.0])
def test_readback_does_not_normalize_nondefault_planned_parameters(
    sequence: int, field: str, planned: float
) -> None:
    waypoint = canonical_mission().waypoints[sequence].model_copy(update={field: planned})
    gateway, _connection = configured_gateway()

    with pytest.raises(MissionUploadError, match=field):
        gateway._verify_downloaded_waypoint(downloaded_waypoint(waypoint, **{field: 1.0}), waypoint)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("seq", 3),
        ("frame", 0),
        ("frame", 5),
        ("frame", 10),
        ("frame", 11),
        ("frame", 2),
        ("command", 21),
        ("current", 2),
        ("autocontinue", 0),
        ("param1", 1.0),
        ("param2", 1.0),
        ("param3", 1.0),
        ("param4", 1.0),
        ("param4", float("nan")),
        ("x", -231190000),
        ("y", -465520000),
        ("z", 10.1),
        ("z", float("nan")),
    ],
)
def test_readback_still_rejects_changed_mission_content(field: str, value: object) -> None:
    waypoint = canonical_mission().waypoints[2]
    gateway, _connection = configured_gateway()
    changes = {"frame": 6, field: value}

    with pytest.raises(MissionUploadError):
        gateway._verify_downloaded_waypoint(downloaded_waypoint(waypoint, **changes), waypoint)


def ingest_test_home(gateway: PymavlinkVehicleGateway, waypoint: MissionWaypoint) -> None:
    gateway._ingest_message(
        FakeMessage(
            "HOME_POSITION",
            latitude=round(waypoint.latitude * 10_000_000),
            longitude=round(waypoint.longitude * 10_000_000),
            altitude=742_320,
        )
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("explicit_passive", [False, True])
async def test_opt_in_queries_do_not_unlock_passive_diagnostics_or_actuation(
    monkeypatch: pytest.MonkeyPatch, explicit_passive: bool
) -> None:
    gateway = PymavlinkVehicleGateway(
        Settings(
            _env_file=None,
            mavlink_mode=MavlinkMode.MISSION_PLANNER_FORWARD,
            mavlink_connection="COM42",
            allow_telemetry_requests=True,
        )
    )
    connection = FakeConnection([FakeMessage("HEARTBEAT", autopilot=3, base_mode=0)])
    module = fake_mavutil()
    module.mavlink_connection = lambda *args, **kwargs: connection
    monkeypatch.setattr(gateway, "_load_mavutil", lambda: module)
    await gateway.connect(passive=explicit_passive)
    health = await gateway.read_health()
    expected_calls = (
        []
        if explicit_passive
        else [
            ("command_long_send", (1, 1, 410, 0, 0, 0, 0, 0, 0, 0, 0)),
            ("param_request_read_send", (1, 1, b"FENCE_ENABLE", -1)),
            ("param_request_read_send", (1, 1, b"RTL_ALT", -1)),
        ]
    )
    assert connection.mav.calls == expected_calls
    assert gateway._passive_connection
    assert health.armed is False
    assert not any(
        (
            health.mission_upload_enabled,
            health.flight_commands_enabled,
            health.mission_start_enabled,
            health.vehicle_arm_enabled,
        )
    )
    with pytest.raises(UnsafeOperationError):
        await gateway.arm_vehicle()
    with pytest.raises(UnsafeOperationError):
        await gateway.upload_mission(canonical_mission(), "")
    with pytest.raises(UnsafeOperationError):
        await gateway.start_mission(canonical_mission())
    assert connection.mav.calls == expected_calls
    # Reconnection must query again, even if the previous batch was recent.
    connection.messages.append(FakeMessage("HEARTBEAT", autopilot=3, base_mode=0))
    await gateway.connect(passive=explicit_passive)
    assert connection.mav.calls == expected_calls * 2
    await gateway.close()


def test_safety_queries_are_rate_limited_retry_and_require_live_drained_link() -> None:
    gateway, connection = configured_gateway()
    gateway._telemetry_requests_enabled = True
    gateway._passive_connection = True
    gateway._request_safety_state_if_due()
    assert connection.mav.calls == []  # no heartbeat
    gateway._last_heartbeat_monotonic = time.monotonic()
    gateway._request_safety_state_if_due()
    assert len(connection.mav.calls) == 3
    gateway._request_safety_state_if_due()
    assert len(connection.mav.calls) == 3
    gateway._last_safety_request_monotonic = time.monotonic() - 10
    gateway._receive_backlog = True
    gateway._request_safety_state_if_due()
    assert len(connection.mav.calls) == 3
    gateway._receive_backlog = False
    gateway._request_safety_state_if_due()
    assert len(connection.mav.calls) == 6  # retry even when replies are lost
    gateway._last_safety_request_monotonic = time.monotonic() - 10
    gateway._last_heartbeat_monotonic = time.monotonic() - 10
    gateway._request_safety_state_if_due()
    assert len(connection.mav.calls) == 6


@pytest.mark.asyncio
async def test_home_and_each_parameter_expire_independently_and_reset() -> None:
    gateway, connection = configured_gateway()
    gateway._passive_connection = True
    gateway._last_heartbeat_monotonic = time.monotonic()
    ingest_test_home(gateway, canonical_mission().waypoints[0])
    for parameter, value in ((b"FENCE_ENABLE\x00", 1), ("RTL_ALT", 1500)):
        gateway._ingest_message(FakeMessage("PARAM_VALUE", param_id=parameter, param_value=value))
    fresh = await gateway.read_health()
    assert fresh.origin_latitude == canonical_mission().origin_latitude
    assert fresh.rtl_configured is True
    assert fresh.geofence_enabled is True
    for key in ("HOME_POSITION", "PARAM:FENCE_ENABLE", "PARAM:RTL_ALT"):
        gateway._last_message_monotonic[key] = time.monotonic() - 3600
    gateway._ingest_message(FakeMessage("PARAM_VALUE", param_id="OTHER", param_value=1))
    gateway._ingest_message(
        FakeMessage("PARAM_VALUE", source_system=99, param_id="RTL_ALT", param_value=1500)
    )
    gateway._ingest_message(
        FakeMessage("HOME_POSITION", source_component=2, latitude=0, longitude=0, altitude=0)
    )
    stale = await gateway.read_health()
    assert stale.origin_latitude is None and stale.origin_longitude is None
    assert stale.rtl_configured is None and stale.geofence_enabled is None
    gateway._ingest_message(FakeMessage("PARAM_VALUE", param_id="RTL_ALT", param_value=1500))
    renewed = await gateway.read_health()
    assert renewed.rtl_configured is True and renewed.geofence_enabled is None
    gateway._reset_live_state()
    reset = await gateway.read_health()
    assert reset.origin_latitude is None and reset.rtl_configured is None
    assert connection.mav.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
async def test_nonfinite_safety_parameters_do_not_claim_readiness(value: float) -> None:
    gateway, _connection = configured_gateway()
    for parameter in ("RTL_ALT", "FENCE_ENABLE"):
        gateway._ingest_message(FakeMessage("PARAM_VALUE", param_id=parameter, param_value=value))
    health = await gateway.read_health()
    assert health.rtl_configured is None and health.geofence_enabled is None


@pytest.mark.parametrize("message_type", ["MISSION_ITEM_INT", "MISSION_ITEM"])
def test_item_zero_uses_live_home_within_existing_origin_guard(message_type: str) -> None:
    expected = canonical_mission().waypoints[0]
    live_home = expected.model_copy(update={"latitude": expected.latitude + 0.000016})
    gateway, _connection = configured_gateway()
    ingest_test_home(gateway, live_home)
    actual = downloaded_waypoint(live_home, frame=0, z=742.32, message_type=message_type)
    gateway._verify_downloaded_waypoint(actual, expected)
    # The old planned origin cannot masquerade as the fresh, shifted Home.
    with pytest.raises(MissionUploadError, match="Coordenadas"):
        gateway._verify_downloaded_waypoint(
            downloaded_waypoint(expected, frame=0, z=742.32, message_type=message_type), expected
        )
    # The same displacement is still invalid for every real route item.
    for waypoint in canonical_mission().waypoints[1:]:
        if waypoint.command == 211:
            continue
        displaced = waypoint.model_copy(update={"latitude": waypoint.latitude + 0.000016})
        with pytest.raises(MissionUploadError, match="Coordenadas"):
            gateway._verify_downloaded_waypoint(downloaded_waypoint(displaced), waypoint)


@pytest.mark.parametrize("offset", [0.00028, float("nan"), float("inf")])
def test_item_zero_rejects_home_outside_origin_guard_even_if_readback_matches(
    offset: float,
) -> None:
    expected = canonical_mission().waypoints[0]
    gateway, _connection = configured_gateway()
    ingest_test_home(gateway, expected)
    gateway._origin_latitude = expected.latitude + offset
    actual = downloaded_waypoint(expected, message_type="MISSION_ITEM", frame=0, z=742.32)
    actual.x = gateway._origin_latitude
    with pytest.raises(MissionUploadError, match="HOME_POSITION"):
        gateway._verify_downloaded_waypoint(actual, expected)


def test_mission_receive_preserves_interleaved_telemetry_and_filters_message_type() -> None:
    waypoint = canonical_mission().waypoints[0]
    gateway, connection = configured_gateway(
        [
            FakeMessage(
                "HOME_POSITION",
                latitude=round(waypoint.latitude * 1e7),
                longitude=round(waypoint.longitude * 1e7),
                altitude=742320,
            ),
            FakeMessage("PARAM_VALUE", param_id="RTL_ALT", param_value=1500),
            FakeMessage("MISSION_ITEM_INT", seq=0),
            FakeMessage("MISSION_COUNT", count=7),
        ]
    )
    message = gateway._recv_mission_message("MISSION_COUNT")
    assert message.get_type() == "MISSION_COUNT"
    assert gateway._message_is_fresh("HOME_POSITION")
    assert gateway._message_is_fresh("PARAM:RTL_ALT")
    assert not connection.messages


def test_readback_verifies_full_arducopter_mission_and_live_home() -> None:
    mission = canonical_mission()
    messages = [FakeMessage("MISSION_COUNT", count=len(mission.waypoints))]
    for waypoint in mission.waypoints:
        changes: dict[str, object] = {}
        if waypoint.sequence == 0:
            changes = {"frame": 0, "z": 742.32}
        elif waypoint.command == 211:
            changes = {"frame": 0, "x": 0, "y": 0, "z": 0}
        elif waypoint.command == 19:
            changes = {"param3": 1.0}
        elif waypoint.command == 21:
            changes = {"param4": 1.0}
        messages.append(downloaded_waypoint(waypoint, **changes))
    gateway, connection = configured_gateway(messages)
    ingest_test_home(gateway, mission.waypoints[0])

    gateway._verify_mission_sync(mission)

    requests = [
        args[2] for name, args in connection.mav.calls if name == "mission_request_int_send"
    ]
    assert requests == list(range(7))
    assert connection.mav.calls[-1] == ("mission_ack_send", (1, 1, 0))
    assert not any(
        name in {"command_long_send", "mission_count_send"} for name, _ in connection.mav.calls
    )


@pytest.mark.parametrize("reply", [False, True])
def test_readback_requests_missing_home_before_starting_download(reply: bool) -> None:
    mission = canonical_mission()
    home = mission.waypoints[0].model_copy(update={"latitude": mission.origin_latitude + 0.000016})
    messages = []
    if reply:
        messages = [
            FakeMessage(
                "HOME_POSITION",
                latitude=round(home.latitude * 1e7),
                longitude=round(home.longitude * 1e7),
                altitude=742320,
            ),
            FakeMessage("MISSION_COUNT", count=7),
            downloaded_waypoint(home, frame=0, z=742.32),
            *(downloaded_waypoint(waypoint) for waypoint in mission.waypoints[1:]),
        ]
    gateway, connection = configured_gateway(messages)
    gateway._last_heartbeat_monotonic = time.monotonic()
    gateway._telemetry_requests_enabled = True
    gateway._passive_connection = True
    if reply:
        gateway._verify_mission_sync(mission)
        assert connection.mav.calls[-1][0] == "mission_ack_send"
    else:
        with pytest.raises(VehicleTimeoutError, match="HOME_POSITION"):
            gateway._verify_mission_sync(mission)
        assert len(connection.mav.calls) == 3  # whitelist only; download never started
    assert connection.mav.calls[0][0] == "command_long_send"
    assert connection.mav.calls[0][1][2] == 410


@pytest.mark.parametrize("mismatch", ["count", "altitude"])
def test_readback_never_acknowledges_a_mismatched_mission(mismatch: str) -> None:
    mission = mission_with_one_waypoint()
    messages = [
        FakeMessage("MISSION_COUNT", count=2 if mismatch == "count" else 1),
        downloaded_waypoint(mission.waypoints[0], z=30),
    ]
    gateway, connection = configured_gateway(messages)

    with pytest.raises(MissionUploadError):
        gateway._verify_mission_sync(mission)

    assert not any(name == "mission_ack_send" for name, _ in connection.mav.calls)
    assert gateway._verified == {}


@pytest.mark.parametrize("frame", [0, 5])
@pytest.mark.parametrize("message_type", ["MISSION_ITEM_INT", "MISSION_ITEM"])
def test_readback_home_absolute_altitude_requires_fresh_matching_home(
    frame: int, message_type: str
) -> None:
    waypoint = canonical_mission().waypoints[0]
    gateway, _connection = configured_gateway()
    actual = downloaded_waypoint(waypoint, message_type=message_type, frame=frame, z=742.32)

    with pytest.raises(MissionUploadError):
        gateway._verify_downloaded_waypoint(actual, waypoint)
    ingest_test_home(gateway, waypoint)
    gateway._verify_downloaded_waypoint(actual, waypoint)
    gateway._last_message_monotonic["HOME_POSITION"] = time.monotonic() - 3600
    with pytest.raises(MissionUploadError):
        gateway._verify_downloaded_waypoint(actual, waypoint)


@pytest.mark.parametrize(
    "invalid_home", ["altitude", "latitude", "longitude", "missing", "nan", "reset"]
)
def test_readback_rejects_inconsistent_or_missing_home(invalid_home: str) -> None:
    waypoint = canonical_mission().waypoints[0]
    gateway, _connection = configured_gateway()
    ingest_test_home(gateway, waypoint)
    actual = downloaded_waypoint(waypoint, frame=0, z=742.32)
    if invalid_home == "altitude":
        actual.z = 743.0
    elif invalid_home == "latitude":
        gateway._origin_latitude = waypoint.latitude + 0.001
    elif invalid_home == "longitude":
        gateway._origin_longitude = waypoint.longitude + 0.001
    elif invalid_home == "missing":
        gateway._home_altitude_m = None
    elif invalid_home == "nan":
        gateway._home_altitude_m = float("nan")
    else:
        gateway._reset_live_state()

    with pytest.raises(MissionUploadError):
        gateway._verify_downloaded_waypoint(actual, waypoint)


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
async def test_passive_telemetry_preserves_timestamp_and_does_not_evaluate_progress() -> None:
    gateway, connection = configured_gateway()
    sample_time = set_fresh_position(gateway, -23.118, -46.551, armed=False)
    gateway._settings = gateway._settings.model_copy(update={"allow_mission_upload": False})

    def unexpected_progress(_mission: AuthorizedMission) -> None:
        pytest.fail("A leitura passiva não pode avançar a missão.")

    gateway._next_progress_status = unexpected_progress  # type: ignore[method-assign]
    telemetry = await gateway.read_telemetry()
    assert telemetry.recorded_at == sample_time
    assert telemetry.armed is False
    assert telemetry.latitude == -23.118
    assert not any(name == "command_long_send" for name, _args in connection.mav.calls)


@pytest.mark.asyncio
async def test_health_keeps_unreceived_mavlink_values_null_and_filters_other_vehicle() -> None:
    gateway, _connection = configured_gateway()
    gateway._ingest_message(
        FakeMessage("GPS_RAW_INT", source_system=99, fix_type=3, satellites_visible=14)
    )
    gateway._last_heartbeat_monotonic = time.monotonic()

    health = await gateway.read_health()

    assert health.gps_fix_type is None
    assert health.satellites is None
    assert health.battery_percent is None
    assert health.flight_mode is None
    assert health.armed is None


@pytest.mark.asyncio
async def test_health_and_telemetry_accept_all_standard_mavlink_gps_fix_types() -> None:
    gateway, _connection = configured_gateway()
    gateway._last_heartbeat_monotonic = time.monotonic()
    gateway._ingest_message(FakeMessage("GPS_RAW_INT", fix_type=8, satellites_visible=14))

    health = await gateway.read_health()
    telemetry = normalize_telemetry(
        latitude_e7=-231175000,
        longitude_e7=-465502000,
        relative_altitude_mm=0,
        velocity_x_cm_s=0,
        velocity_y_cm_s=0,
        battery_percent=80,
        gps_fix_type=8,
        satellites=14,
        flight_mode="STANDBY",
        armed=False,
    )

    assert health.gps_fix_type == 8
    assert telemetry.gps_fix_type == 8


@pytest.mark.asyncio
async def test_battery_status_is_normalized_then_becomes_stale() -> None:
    gateway, _connection = configured_gateway()
    gateway._last_heartbeat_monotonic = time.monotonic()
    gateway._ingest_message(
        FakeMessage(
            "BATTERY_STATUS",
            battery_remaining=73,
            voltages=[4100, 4090, 0xFFFF],
        )
    )

    fresh = await gateway.read_health()
    assert fresh.battery_percent == 73
    assert fresh.battery_voltage == pytest.approx(8.19)

    gateway._last_message_monotonic["BATTERY"] = (
        time.monotonic() - gateway._settings.mavlink_telemetry_stale_seconds - 0.1
    )
    stale = await gateway.read_health()
    assert stale.battery_percent is None
    assert stale.battery_voltage is None


@pytest.mark.asyncio
@pytest.mark.parametrize("message_type", ["SYS_STATUS", "BATTERY_STATUS"])
@pytest.mark.parametrize("remaining", [-1, 101])
async def test_unknown_battery_clears_previous_reading(message_type: str, remaining: int) -> None:
    gateway, connection = configured_gateway()
    gateway._last_heartbeat_monotonic = time.monotonic()
    gateway._ingest_message(FakeMessage("BATTERY_STATUS", battery_remaining=80, voltages=[15000]))
    assert (await gateway.read_health()).battery_percent == 80

    gateway._ingest_message(
        FakeMessage(
            message_type,
            battery_remaining=remaining,
            voltage_battery=0xFFFF,
            voltages=[0xFFFF] * 10,
            onboard_control_sensors_health=1 << 28,
        )
    )

    health = await gateway.read_health()
    assert health.battery_percent is None
    assert health.battery_voltage is None
    assert all(name == "heartbeat_send" for name, _ in connection.mav.calls)


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
