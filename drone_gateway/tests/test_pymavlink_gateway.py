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
