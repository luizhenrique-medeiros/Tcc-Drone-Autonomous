import asyncio
import logging
import math
import os
import struct
import time
from collections import deque
from datetime import UTC, datetime
from types import ModuleType
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError
from serial import SerialException

from app.core.config import MavlinkMode, Settings
from app.core.exceptions import (
    GatewayError,
    MissionUploadError,
    UnsafeOperationError,
    VehicleConnectionError,
    VehiclePortAccessError,
    VehiclePortBusyError,
    VehiclePortNotFoundError,
    VehicleTimeoutError,
)
from app.core.geo import distance_m
from app.mavlink.ports import list_serial_ports
from app.models import (
    AuthorizedMission,
    BenchArmClaim,
    BenchArmEvidence,
    ConnectionState,
    MissionStatus,
    MissionVerificationResult,
    MissionWaypoint,
    OperationalSource,
    Px4FlightObservation,
    Px4HealthDiagnostics,
    TelemetrySnapshot,
    UploadResult,
    VehicleArmResult,
    VehicleEvent,
    VehicleHealth,
    VehiclePoll,
)

logger = logging.getLogger(__name__)


def _mission_plan_id(message: Any, field: str, extension_offset: int) -> int | None:
    """Read a MAVLink 2 plan ID even with an older generated pymavlink dialect."""
    value = getattr(message, field, None)
    if value is None:
        get_frame = getattr(message, "get_msgbuf", None)
        frame = get_frame() if callable(get_frame) else None
        if not frame or len(frame) < 12 or frame[0] != 0xFD or len(frame) < 12 + frame[1]:
            return None
        payload = frame[10 : 10 + frame[1]]
        field_bytes = payload[extension_offset : extension_offset + 4]
        value = int.from_bytes(field_bytes, "little")
    return value if type(value) is int and 0 < value <= 0xFFFFFFFF else None


PX4_RTL_PARAM_FIELDS = {
    "RTL_TYPE": "rtl_type",
    "RTL_RETURN_ALT": "rtl_return_alt_m",
    "RTL_DESCEND_ALT": "rtl_descend_alt_m",
    "RTL_LAND_DELAY": "rtl_land_delay_s",
    "RTL_CONE_ANG": "rtl_cone_angle_deg",
    "RTL_MIN_DIST": "rtl_min_distance_m",
}
# Parameters received during a QGroundControl refresh are evidence for a limited time.
PX4_RTL_PARAM_MAX_AGE_SECONDS = 60

MISSION_PROGRESS_STATUSES = (
    MissionStatus.DESTINATION_REACHED,
    MissionStatus.DELIVERY_CONFIRMED,
    MissionStatus.RETURNING,
    MissionStatus.COMPLETED,
)


class PymavlinkVehicleGateway:
    """Thin pymavlink adapter with explicit, gated commands and no parameter writes."""

    _ARM_MAX_SEND_ATTEMPTS = 3
    _RECEIVE_MAX_DRAIN_MESSAGES = 10_000
    _RECEIVE_DRAIN_TIMEOUT_SECONDS = 0.1
    _ARM_DRAIN_TIMEOUT_SECONDS = 1.0

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._mavutil: ModuleType | None = None
        # pymavlink builds dynamic dialect classes, so a static type is not available here.
        self._connection: Any | None = None
        self._connection_lock = asyncio.Lock()
        self._arm_command_lock = asyncio.Lock()
        self._connection_state = ConnectionState.DISCONNECTED
        self._connection_error: str | None = None
        self._passive_connection = False
        self._bench_arm_session_id: UUID | None = None
        self._telemetry_requests_enabled = False
        self._last_safety_request_monotonic: float | None = None
        self._receive_backlog = False
        self._last_heartbeat_monotonic: float | None = None
        self._last_heartbeat_recorded_at: datetime | None = None
        self._last_gcs_heartbeat_monotonic: float | None = None
        self._last_message_monotonic: dict[str, float] = {}
        self._mode: str | None = None
        self._armed: bool | None = None
        self._gps_fix: int | None = None
        self._satellites: int | None = None
        self._ekf_ok: bool | None = None
        self._battery_percent: float | None = None
        self._battery_voltage: float | None = None
        self._preflight_ok: bool | None = None
        self._px4_current_mode_prearm_ok: bool | None = None
        self._px4_rtl_parameters: dict[str, int | float] = {}
        self._rtl_configured: bool | None = None
        self._geofence_enabled: bool | None = None
        self._autopilot_version: str | None = None
        self._origin_latitude: float | None = None
        self._origin_longitude: float | None = None
        self._home_altitude_m: float | None = None
        self._latitude: float | None = None
        self._longitude: float | None = None
        self._current_amsl_m: float | None = None
        self._last_position_monotonic: float | None = None
        self._last_position_recorded_at: datetime | None = None
        self._relative_altitude_m = 0.0
        self._ground_speed_m_s = 0.0
        self._uploaded: dict[str, str] = {}
        self._last_current_sequence: int | None = None
        self._last_mission_observation: tuple[int, int | None, int | None] | None = None
        self._px4_mission_current = Px4FlightObservation()
        self._reached_sequences: set[int] = set()
        self._landed_state: int | None = None
        self._saw_sitl_airborne = False
        self._saw_sitl_destination = False
        self._events: deque[VehicleEvent] = deque(maxlen=200)
        self._reported_progress: dict[str, set[MissionStatus]] = {}
        self._verified: dict[str, str] = {}

    @property
    def connection_state(self) -> ConnectionState:
        self._refresh_connection_state()
        return self._connection_state

    @property
    def connection_error(self) -> str | None:
        return self._connection_error

    def mark_reconnecting(self) -> None:
        self._connection_state = ConnectionState.RECONNECTING

    def _load_mavutil(self) -> ModuleType:
        if self._settings.mavlink2_enabled:
            os.environ["MAVLINK20"] = "1"
        try:
            from pymavlink import mavutil
        except ImportError as exc:
            raise VehicleConnectionError(
                "pymavlink não está instalado; execute o bootstrap do gateway."
            ) from exc
        return mavutil

    async def connect(self, *, passive: bool = False) -> None:
        async with self._connection_lock:
            await self._close_unlocked()
            self._connection_state = ConnectionState.CONNECTING
            self._connection_error = None
            # A hardware endpoint without the explicit acknowledgement is strictly
            # receive-only by default. A separate opt-in only permits the fixed
            # safety-state query whitelist, never GCS heartbeats or stream control.
            self._passive_connection = (
                passive
                or (
                    self._settings.is_hardware_mode
                    and not self._settings.real_hardware_acknowledged
                )
                or (
                    self._settings.autopilot_system.strip().upper() == "PX4"
                    and not self._settings.px4_sitl_plan_validation
                )
                or self._settings.mavlink_mode is MavlinkMode.QGROUNDCONTROL_FORWARD
                or self._settings.mavlink_mode is MavlinkMode.MAVLINK_ROUTER
            )
            self._reset_live_state()
            self._telemetry_requests_enabled = (
                not passive
                and not self._settings.px4_sitl_plan_validation
                and (not self._passive_connection or self._settings.allow_telemetry_requests)
            )
            self._mavutil = self._load_mavutil()
            try:
                self._validate_serial_port_exists()
                self._connection = self._mavutil.mavlink_connection(
                    self._settings.effective_mavlink_connection,
                    baud=self._settings.mavlink_baud_rate,
                    autoreconnect=not self._settings.is_px4_bench_arm,
                    source_system=self._settings.mavlink_source_system_id,
                    source_component=self._settings.mavlink_source_component_id,
                    dialect=self._settings.mavlink_dialect,
                )
                self._connection_state = ConnectionState.WAITING_HEARTBEAT
                heartbeat = await asyncio.to_thread(self._wait_for_target_heartbeat)
                if heartbeat is None:
                    raise VehicleTimeoutError(
                        "Conexão aberta, mas nenhum heartbeat "
                        f"{self._settings.autopilot_system} válido chegou no timeout."
                    )
                self._ingest_message(heartbeat)
                self._connection_state = ConnectionState.CONNECTED
                if (
                    self._settings.is_px4_bench_arm
                    and self._settings.allow_vehicle_arm
                    and not passive
                ):
                    self._bench_arm_session_id = uuid4()
                if not self._passive_connection and not self._settings.px4_sitl_plan_validation:
                    await asyncio.to_thread(self._request_initial_state)
                    await asyncio.to_thread(self._drain_messages)
                elif self._telemetry_requests_enabled:
                    await asyncio.to_thread(self._drain_messages)
                    await asyncio.to_thread(self._request_safety_state_if_due)
                logger.info(
                    "MAVLink connected",
                    extra={
                        "connection_state": self._connection_state.value,
                        "connection_mode": self._settings.connection_topology,
                    },
                )
            except (PermissionError, SerialException, OSError) as exc:
                translated = self._translate_connection_error(exc)
                self._connection_error = str(translated)
                self._connection_state = ConnectionState.ERROR
                await self._close_connection_resource()
                raise translated from exc
            except (VehicleConnectionError, VehicleTimeoutError) as exc:
                self._connection_error = str(exc)
                self._connection_state = ConnectionState.ERROR
                await self._close_connection_resource()
                raise

    async def _close_connection_resource(self) -> None:
        self._bench_arm_session_id = None
        connection = self._connection
        self._connection = None
        if connection is None:
            return
        close = getattr(connection, "close", None)
        if callable(close):
            try:
                await asyncio.to_thread(close)
            except (OSError, SerialException):
                logger.warning("MAVLink resource close failed", exc_info=True)

    async def _close_unlocked(self) -> None:
        await self._close_connection_resource()
        self._connection_state = ConnectionState.DISCONNECTED
        self._connection_error = None

    def _reset_live_state(self) -> None:
        self._last_safety_request_monotonic = None
        self._receive_backlog = False
        self._last_heartbeat_monotonic = None
        self._last_heartbeat_recorded_at = None
        self._last_gcs_heartbeat_monotonic = None
        self._last_message_monotonic.clear()
        self._mode = None
        self._armed = None
        self._gps_fix = None
        self._satellites = None
        self._ekf_ok = None
        self._battery_percent = None
        self._battery_voltage = None
        self._preflight_ok = None
        self._px4_current_mode_prearm_ok = None
        self._px4_rtl_parameters.clear()
        self._rtl_configured = None
        self._geofence_enabled = None
        self._autopilot_version = None
        self._origin_latitude = None
        self._origin_longitude = None
        self._home_altitude_m = None
        self._latitude = None
        self._longitude = None
        self._current_amsl_m = None
        self._last_position_monotonic = None
        self._last_position_recorded_at = None
        self._relative_altitude_m = 0.0
        self._ground_speed_m_s = 0.0
        self._last_current_sequence = None
        self._last_mission_observation = None
        self._px4_mission_current = Px4FlightObservation()
        self._reached_sequences.clear()
        self._landed_state = None
        self._saw_sitl_airborne = False
        self._saw_sitl_destination = False

    def _is_serial_connection(self) -> bool:
        return not self._settings.effective_mavlink_connection.lower().startswith(
            ("udp:", "udpin:", "udpout:", "tcp:", "tcpin:", "mcast:")
        )

    def _upstream_serial_port(self) -> str | None:
        if self._settings.mavlink_mode is MavlinkMode.MISSION_PLANNER_FORWARD:
            configured = self._settings.mavlink_connection.strip()
        elif self._is_serial_connection():
            configured = self._settings.effective_mavlink_connection.strip()
        else:
            return None
        return configured or None

    def _validate_serial_port_exists(self) -> None:
        if not self._is_serial_connection():
            return
        configured = self._settings.effective_mavlink_connection.casefold()
        available = {port.device.casefold() for port in list_serial_ports()}
        if configured not in available:
            raise VehiclePortNotFoundError(
                f"Porta {self._settings.sanitized_connection} não foi encontrada."
            )

    def _translate_connection_error(self, exc: BaseException) -> VehicleConnectionError:
        endpoint = self._settings.sanitized_connection
        message = str(exc).casefold()
        if isinstance(exc, PermissionError) and self._is_serial_connection():
            return VehiclePortBusyError(
                f"Porta {endpoint} ocupada ou com acesso negado. Não abra a mesma porta "
                "em dois processos; use encaminhamento UDP para observação passiva."
            )
        if isinstance(exc, PermissionError):
            return VehiclePortAccessError(f"Acesso negado ao abrir {endpoint}.")
        if self._is_serial_connection() and any(
            marker in message for marker in ("access is denied", "permission", "acesso negado")
        ):
            return VehiclePortBusyError(
                f"{endpoint} existe, mas está ocupada ou sem permissão; feche o concorrente "
                "ou configure encaminhamento UDP para observação passiva."
            )
        return VehicleConnectionError(f"Falha ao abrir {endpoint}: {exc}")

    def _wait_for_target_heartbeat(self) -> Any | None:
        connection = self._required_connection()
        mavutil = self._required_mavutil()
        deadline = time.monotonic() + self._settings.heartbeat_timeout_seconds
        invalid_autopilot = getattr(mavutil.mavlink, "MAV_AUTOPILOT_INVALID", 8)
        expected_autopilot = (
            getattr(mavutil.mavlink, "MAV_AUTOPILOT_PX4", 12)
            if self._settings.autopilot_system.strip().upper() == "PX4"
            else getattr(mavutil.mavlink, "MAV_AUTOPILOT_ARDUPILOTMEGA", 3)
        )
        while time.monotonic() < deadline:
            heartbeat = connection.recv_match(
                type="HEARTBEAT",
                blocking=True,
                timeout=max(0.1, deadline - time.monotonic()),
            )
            if heartbeat is None:
                continue
            source_system = int(heartbeat.get_srcSystem())
            source_component = int(heartbeat.get_srcComponent())
            if (
                self._settings.mavlink_target_system_id is not None
                and source_system != self._settings.mavlink_target_system_id
            ):
                continue
            if (
                self._settings.mavlink_target_component_id is not None
                and source_component != self._settings.mavlink_target_component_id
            ):
                continue
            autopilot = int(getattr(heartbeat, "autopilot", invalid_autopilot))
            if autopilot == invalid_autopilot or autopilot != expected_autopilot:
                continue
            connection.target_system = source_system
            connection.target_component = source_component
            return heartbeat
        return None

    def _request_initial_state(self) -> None:
        if self._passive_connection:
            return
        self._request_safety_state_if_due()
        self._request_autopilot_version()
        if not self._request_message_intervals():
            self._request_data_stream_fallback()

    def _request_safety_state_if_due(self) -> None:
        """Only read Home and two parameters, with a bounded rate and a live target."""
        if not self._telemetry_requests_enabled or self._connection is None:
            return
        self._refresh_connection_state()
        if self._connection_state is not ConnectionState.CONNECTED:
            return
        now = time.monotonic()
        # Default: one three-message batch per 2 seconds. A short freshness
        # configuration never increases this above two batches per second.
        interval = max(0.5, min(2.0, self._settings.mavlink_telemetry_stale_seconds / 2))
        if (
            self._last_safety_request_monotonic is not None
            and now - self._last_safety_request_monotonic < interval
        ):
            return
        self._last_safety_request_monotonic = now
        connection = self._required_connection()
        mavutil = self._required_mavutil()
        target_system = connection.target_system
        target_component = connection.target_component
        connection.mav.command_long_send(
            target_system,
            target_component,
            mavutil.mavlink.MAV_CMD_GET_HOME_POSITION,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        )
        for parameter in (b"FENCE_ENABLE", b"RTL_ALT"):
            connection.mav.param_request_read_send(target_system, target_component, parameter, -1)
        logger.debug("Home, FENCE_ENABLE and RTL_ALT requested (read-only)")

    def _request_autopilot_version(self) -> None:
        if self._passive_connection or not self._telemetry_requests_enabled:
            return
        connection = self._required_connection()
        mavlink = self._required_mavutil().mavlink
        request_message = getattr(mavlink, "MAV_CMD_REQUEST_MESSAGE", None)
        message_id = getattr(mavlink, "MAVLINK_MSG_ID_AUTOPILOT_VERSION", None)
        if request_message is not None and message_id is not None:
            connection.mav.command_long_send(
                connection.target_system,
                connection.target_component,
                request_message,
                0,
                message_id,
                0,
                0,
                0,
                0,
                0,
                0,
            )
            return
        legacy_command = getattr(mavlink, "MAV_CMD_REQUEST_AUTOPILOT_CAPABILITIES", None)
        if legacy_command is not None:
            connection.mav.command_long_send(
                connection.target_system,
                connection.target_component,
                legacy_command,
                0,
                1,
                0,
                0,
                0,
                0,
                0,
                0,
            )

    def _request_message_intervals(self) -> bool:
        if self._passive_connection:
            return False
        connection = self._required_connection()
        mavlink = self._required_mavutil().mavlink
        command = getattr(mavlink, "MAV_CMD_SET_MESSAGE_INTERVAL", None)
        if command is None:
            return False
        requested = (
            ("MAVLINK_MSG_ID_SYS_STATUS", 1_000_000),
            ("MAVLINK_MSG_ID_BATTERY_STATUS", 1_000_000),
            ("MAVLINK_MSG_ID_GPS_RAW_INT", 1_000_000),
            ("MAVLINK_MSG_ID_GLOBAL_POSITION_INT", 500_000),
            ("MAVLINK_MSG_ID_EKF_STATUS_REPORT", 1_000_000),
            ("MAVLINK_MSG_ID_HOME_POSITION", 5_000_000),
            ("MAVLINK_MSG_ID_MISSION_CURRENT", 1_000_000),
        )
        sent_any = False
        all_acknowledged = True
        for constant_name, interval_us in requested:
            message_id = getattr(mavlink, constant_name, None)
            if message_id is None:
                continue
            try:
                connection.mav.command_long_send(
                    connection.target_system,
                    connection.target_component,
                    command,
                    0,
                    message_id,
                    interval_us,
                    0,
                    0,
                    0,
                    0,
                    0,
                )
            except (AttributeError, OSError, TypeError, ValueError):
                return False
            sent_any = True
            if not self._wait_command_ack(
                command,
                timeout=self._settings.mavlink_message_interval_timeout_seconds,
            ):
                all_acknowledged = False
        return sent_any and all_acknowledged

    def _wait_command_ack(self, command: int, *, timeout: float) -> bool:
        result = self._receive_command_ack_result(command, timeout=timeout)
        accepted = getattr(self._required_mavutil().mavlink, "MAV_RESULT_ACCEPTED", 0)
        return result == accepted

    def _receive_command_ack_result(self, command: int, *, timeout: float) -> int | None:
        connection = self._required_connection()
        mavlink = self._required_mavutil().mavlink
        in_progress = getattr(mavlink, "MAV_RESULT_IN_PROGRESS", 5)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            message = connection.recv_match(
                type="COMMAND_ACK",
                condition=f"COMMAND_ACK.command=={command}",
                blocking=True,
                timeout=max(0.05, deadline - time.monotonic()),
            )
            if message is None or not self._message_matches_target(message):
                continue
            target_system = getattr(
                message, "target_system", self._settings.mavlink_source_system_id
            )
            if int(target_system) not in {0, self._settings.mavlink_source_system_id}:
                continue
            target_component = getattr(
                message,
                "target_component",
                self._settings.mavlink_source_component_id,
            )
            if int(target_component) not in {0, self._settings.mavlink_source_component_id}:
                continue
            result = int(message.result)
            if result == in_progress:
                continue
            return result
        return None

    def _request_data_stream_fallback(self) -> None:
        connection = self._required_connection()
        mavlink = self._required_mavutil().mavlink
        stream = getattr(mavlink, "MAV_DATA_STREAM_ALL", 0)
        try:
            connection.mav.request_data_stream_send(
                connection.target_system,
                connection.target_component,
                stream,
                2,
                1,
            )
        except (AttributeError, OSError, TypeError, ValueError):
            # Failure is non-fatal: consume whatever stream the autopilot exposes.
            return

    def _required_connection(self) -> Any:
        if self._connection is None:
            raise VehicleConnectionError("Conexão MAVLink ainda não foi aberta.")
        return self._connection

    def _required_mavutil(self) -> ModuleType:
        if self._mavutil is None:
            raise VehicleConnectionError("pymavlink ainda não foi carregado.")
        return self._mavutil

    def _drain_messages(self, *, timeout: float = _RECEIVE_DRAIN_TIMEOUT_SECONDS) -> bool:
        """Consume a burst without starving the loop or treating buffered state as live."""
        connection = self._required_connection()
        self._send_gcs_heartbeat_if_due()
        deadline = time.monotonic() + timeout
        for _ in range(self._RECEIVE_MAX_DRAIN_MESSAGES):
            if time.monotonic() >= deadline:
                break
            message = connection.recv_match(blocking=False)
            if message is None:
                self._receive_backlog = False
                return True
            self._ingest_message(message)
        # A recent local receive timestamp cannot prove freshness while older
        # packets may still be queued. Never flush/discard them to enable ARM.
        self._receive_backlog = True
        return False

    def _ingest_message(self, message: Any) -> None:
        mavutil = self._required_mavutil()
        message_type = message.get_type()
        if message_type == "BAD_DATA":
            return
        if not self._message_matches_target(message):
            return
        if (
            message_type == "HEARTBEAT"
            and self._settings.autopilot_system.strip().upper() == "PX4"
            and int(getattr(message, "autopilot", -1))
            != getattr(mavutil.mavlink, "MAV_AUTOPILOT_PX4", 12)
        ):
            return
        received_monotonic = time.monotonic()
        self._last_message_monotonic[message_type] = received_monotonic
        is_px4 = self._settings.autopilot_system.strip().upper() == "PX4"
        if message_type == "HEARTBEAT":
            self._last_heartbeat_monotonic = received_monotonic
            self._last_heartbeat_recorded_at = datetime.now(UTC)
            self._connection_state = ConnectionState.CONNECTED
            self._connection_error = None
            mode = mavutil.mode_string_v10(message)
            if is_px4 and mode != self._mode:
                self._preflight_ok = None
                self._px4_current_mode_prearm_ok = None
            self._mode = mode
            armed_flag = mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
            self._armed = bool(message.base_mode & armed_flag)
        elif message_type == "GPS_RAW_INT":
            self._gps_fix = int(message.fix_type)
            satellites = int(message.satellites_visible)
            self._satellites = satellites if 0 <= satellites <= 100 else None
        elif message_type == "SYS_STATUS":
            battery_remaining = int(message.battery_remaining)
            self._battery_percent = (
                float(battery_remaining) if 0 <= battery_remaining <= 100 else None
            )
            voltage = int(message.voltage_battery)
            self._battery_voltage = voltage / 1000 if 0 < voltage < 0xFFFF else None
            prearm_bit = getattr(mavutil.mavlink, "MAV_SYS_STATUS_PREARM_CHECK", 1 << 28)
            if is_px4:
                present = int(getattr(message, "onboard_control_sensors_present", 0))
                enabled = int(getattr(message, "onboard_control_sensors_enabled", 0))
                self._preflight_ok = (
                    bool(int(message.onboard_control_sensors_health) & prearm_bit)
                    if present & prearm_bit and enabled & prearm_bit
                    else None
                )
                # PX4 1.17 sets this health bit from can_arm_mode_flags for nav_state.
                # Expose it for the observed mode without substituting the flight gate.
                health_bit = bool(int(message.onboard_control_sensors_health) & prearm_bit)
                self._px4_current_mode_prearm_ok = (
                    (True if health_bit else self._preflight_ok) if self._mode is not None else None
                )
            else:
                self._preflight_ok = bool(int(message.onboard_control_sensors_health) & prearm_bit)
            self._last_message_monotonic["BATTERY"] = received_monotonic
        elif message_type == "BATTERY_STATUS":
            battery_remaining = int(getattr(message, "battery_remaining", -1))
            self._battery_percent = (
                float(battery_remaining) if 0 <= battery_remaining <= 100 else None
            )
            voltages = getattr(message, "voltages", ())
            valid_voltages = [int(value) for value in voltages if 0 < int(value) < 0xFFFF]
            self._battery_voltage = sum(valid_voltages) / 1000 if valid_voltages else None
            self._last_message_monotonic["BATTERY"] = received_monotonic
        elif message_type == "EKF_STATUS_REPORT":
            attitude = getattr(mavutil.mavlink, "EKF_ATTITUDE", 1)
            velocity = getattr(mavutil.mavlink, "EKF_VELOCITY_HORIZ", 2)
            position = getattr(mavutil.mavlink, "EKF_POS_HORIZ_REL", 8)
            required = attitude | velocity | position
            self._ekf_ok = int(message.flags) & required == required
            self._last_message_monotonic["ESTIMATOR"] = received_monotonic
        elif message_type == "ESTIMATOR_STATUS":
            flags = int(message.flags)
            required = (
                getattr(mavutil.mavlink, "ESTIMATOR_ATTITUDE", 1)
                | getattr(mavutil.mavlink, "ESTIMATOR_VELOCITY_HORIZ", 2)
                | getattr(mavutil.mavlink, "ESTIMATOR_POS_HORIZ_ABS", 16)
            )
            invalid = (
                getattr(mavutil.mavlink, "ESTIMATOR_CONST_POS_MODE", 128)
                | getattr(mavutil.mavlink, "ESTIMATOR_GPS_GLITCH", 1024)
                | getattr(mavutil.mavlink, "ESTIMATOR_ACCEL_ERROR", 2048)
            )
            self._ekf_ok = flags & required == required and not flags & invalid
            self._last_message_monotonic["ESTIMATOR"] = received_monotonic
        elif message_type == "HOME_POSITION":
            self._origin_latitude = float(message.latitude) / 10_000_000
            self._origin_longitude = float(message.longitude) / 10_000_000
            altitude = getattr(message, "altitude", None)
            self._home_altitude_m = float(altitude) / 1000 if altitude is not None else None
        elif message_type == "GLOBAL_POSITION_INT":
            self._latitude = float(message.lat) / 10_000_000
            self._longitude = float(message.lon) / 10_000_000
            absolute_altitude = getattr(message, "alt", None)
            self._current_amsl_m = (
                absolute_altitude / 1000
                if isinstance(absolute_altitude, int)
                and -1000 <= absolute_altitude / 1000 <= 100_000
                else None
            )
            self._relative_altitude_m = float(message.relative_alt) / 1000
            self._ground_speed_m_s = math.hypot(float(message.vx), float(message.vy)) / 100
            self._last_position_monotonic = received_monotonic
            self._last_position_recorded_at = datetime.now(UTC)
        elif message_type == "PARAM_VALUE":
            raw_parameter_id = message.param_id
            parameter_id = (
                raw_parameter_id.decode(errors="replace")
                if isinstance(raw_parameter_id, bytes)
                else str(raw_parameter_id)
            ).rstrip("\x00")
            value = float(message.param_value)
            if is_px4:
                self._ingest_px4_rtl_param(parameter_id, value, message, received_monotonic)
            elif parameter_id == "FENCE_ENABLE":
                self._geofence_enabled = value >= 1 if math.isfinite(value) else None
                self._last_message_monotonic["PARAM:FENCE_ENABLE"] = received_monotonic
            elif parameter_id == "RTL_ALT":
                self._rtl_configured = value > 0 if math.isfinite(value) else None
                self._last_message_monotonic["PARAM:RTL_ALT"] = received_monotonic
        elif message_type == "AUTOPILOT_VERSION":
            software = int(getattr(message, "flight_sw_version", 0))
            major = (software >> 24) & 0xFF
            minor = (software >> 16) & 0xFF
            patch = (software >> 8) & 0xFF
            release_type = software & 0xFF
            vendor = int(getattr(message, "vendor_id", 0))
            product = int(getattr(message, "product_id", 0))
            self._autopilot_version = (
                f"{major}.{minor}.{patch} (tipo {release_type}; vendor {vendor}; produto {product})"
            )
        elif is_px4 and message_type == "EXTENDED_SYS_STATE":
            self._landed_state = int(message.landed_state)
            if self._settings.px4_sitl_plan_validation and self._landed_state == 2:
                self._saw_sitl_airborne = True
        elif is_px4 and self._passive_connection and message_type == "COMMAND_ACK":
            command = int(message.command)
            result = int(message.result)
            self._queue_event(
                event_type="MAVLINK_COMMAND_ACK",
                severity="INFO",
                message=f"PX4 respondeu ao comando {command} com resultado MAVLink {result}.",
                metadata={"command": command, "result": result},
            )
        elif is_px4 and self._passive_connection and message_type == "MISSION_ACK":
            result = int(message.type)
            self._queue_event(
                event_type="MAVLINK_MISSION_ACK",
                severity="INFO",
                message=f"PX4 informou resultado MAVLink {result} para a operação de missão.",
                metadata={
                    "result": result,
                    "mission_type": int(getattr(message, "mission_type", 0)),
                },
            )
        elif message_type == "MISSION_CURRENT":
            sequence = int(message.seq)
            sequence_changed = sequence != self._last_current_sequence
            self._last_current_sequence = sequence
            observing_px4 = is_px4 and self._passive_connection
            plan_id = _mission_plan_id(message, "mission_id", 6) if observing_px4 else None
            mission_state = getattr(message, "mission_state", None)
            if observing_px4:
                total = getattr(message, "total", 0)
                mission_mode = getattr(message, "mission_mode", None)
                self._px4_mission_current = Px4FlightObservation(
                    sequence=sequence if 0 <= sequence < 65535 and mission_state != 1 else None,
                    mission_total=total if 0 < total < 65535 else None,
                    mission_state=mission_state if mission_state in {1, 2, 3, 4, 5} else None,
                    mission_mode=mission_mode if mission_mode in {1, 2} else None,
                    native_plan_id=plan_id,
                    mission_at=datetime.now(UTC),
                )
            observation = (sequence, plan_id, mission_state)
            changed_observation = observing_px4 and observation != self._last_mission_observation
            self._last_mission_observation = observation
            if sequence_changed or changed_observation:
                metadata: dict[str, str | int | float | bool | None] = {"sequence": sequence}
                for field in ("mission_state", "mission_mode"):
                    value = getattr(message, field, None)
                    if value is not None:
                        metadata[field] = int(value)
                if plan_id is not None:
                    metadata.update(
                        native_plan_id=plan_id,
                        system_id=int(message.get_srcSystem()),
                        component_id=int(message.get_srcComponent()),
                    )
                self._queue_event(
                    event_type="MAVLINK_MISSION_CURRENT",
                    severity="INFO",
                    message=f"Autopiloto informou waypoint atual {sequence}.",
                    metadata=metadata,
                )
        elif message_type == "MISSION_ITEM_REACHED":
            sequence = int(message.seq)
            self._reached_sequences.add(sequence)
            current = self._px4_mission_current
            current_fresh = self._message_is_fresh("MISSION_CURRENT")
            self._queue_event(
                event_type="MAVLINK_MISSION_ITEM_REACHED",
                severity="INFO",
                message=f"Autopiloto informou waypoint alcançado {sequence}.",
                metadata={
                    "sequence": sequence,
                    **(
                        {
                            "native_plan_id": current.native_plan_id if current_fresh else None,
                            "system_id": int(message.get_srcSystem()),
                            "component_id": int(message.get_srcComponent()),
                        }
                        if is_px4 and self._passive_connection
                        else {}
                    ),
                },
            )
        elif message_type == "STATUSTEXT":
            raw_text = message.text
            text = (
                raw_text.decode(errors="replace") if isinstance(raw_text, bytes) else str(raw_text)
            )
            severity_number = int(getattr(message, "severity", 6))
            severity = (
                "ERROR"
                if severity_number <= 2
                else "ERROR"
                if severity_number == 3
                else "WARNING"
                if severity_number == 4
                else "INFO"
            )
            self._queue_event(
                event_type="MAVLINK_STATUSTEXT",
                severity=severity,
                message=text.rstrip("\x00")[:2000] or "STATUSTEXT sem conteúdo.",
                metadata={"mav_severity": severity_number},
            )

    def _ingest_px4_rtl_param(
        self, name: str, value: float, message: Any, received_monotonic: float
    ) -> None:
        if name not in PX4_RTL_PARAM_FIELDS:
            return
        self._px4_rtl_parameters.pop(name, None)
        parameter_type = getattr(message, "param_type", None)
        if not math.isfinite(value):
            return
        if name in {"RTL_TYPE", "RTL_CONE_ANG"}:
            if parameter_type != 6:  # MAV_PARAM_TYPE_INT32, PX4 byte-wise encoding
                return
            try:
                value = struct.unpack("<i", struct.pack("<f", value))[0]
            except OverflowError:
                return
        elif parameter_type != 9:  # MAV_PARAM_TYPE_REAL32
            return
        if value < (-1 if name == "RTL_LAND_DELAY" else 0):
            return
        if name == "RTL_CONE_ANG" and value > 90:
            return
        self._px4_rtl_parameters[name] = value
        self._last_message_monotonic[f"PARAM:{name}"] = received_monotonic

    def _px4_diagnostics(self) -> Px4HealthDiagnostics | None:
        if self._connection_state is not ConnectionState.CONNECTED:
            return None
        fields = {
            PX4_RTL_PARAM_FIELDS[name]: value
            for name, value in self._px4_rtl_parameters.items()
            if self._message_is_fresh(f"PARAM:{name}", timeout=PX4_RTL_PARAM_MAX_AGE_SECONDS)
        }
        if self._px4_current_mode_prearm_ok is not None and self._message_is_fresh("SYS_STATUS"):
            fields["current_mode_prearm_ok"] = self._px4_current_mode_prearm_ok
        return Px4HealthDiagnostics.model_validate(fields) if fields else None

    def _message_matches_target(self, message: Any) -> bool:
        connection = self._required_connection()
        source_system_getter = getattr(message, "get_srcSystem", None)
        source_component_getter = getattr(message, "get_srcComponent", None)
        if not callable(source_system_getter) or not callable(source_component_getter):
            return False
        try:
            source_system = int(source_system_getter())
            source_component = int(source_component_getter())
        except (TypeError, ValueError):
            return False
        if source_system != int(connection.target_system):
            return False
        return int(connection.target_component) <= 0 or source_component == int(
            connection.target_component
        )

    def _operational_source(self) -> OperationalSource:
        if self._settings.mavlink_mode in {
            MavlinkMode.QGROUNDCONTROL_FORWARD,
            MavlinkMode.MAVLINK_ROUTER,
        }:
            # Operator declaration, not automatic detection by forwarding.
            return OperationalSource(self._settings.mavlink_forward_source.value)
        if self._settings.mavlink_mode is MavlinkMode.SITL:
            return OperationalSource.SITL
        if self._settings.is_hardware_mode:
            return OperationalSource.HARDWARE_REAL
        return OperationalSource.SIMULATION

    def _heartbeat_age_seconds(self) -> float | None:
        if self._last_heartbeat_monotonic is None:
            return None
        return max(0.0, time.monotonic() - self._last_heartbeat_monotonic)

    def _refresh_connection_state(self) -> None:
        if self._connection is None:
            if self._connection_state not in {ConnectionState.ERROR, ConnectionState.RECONNECTING}:
                self._connection_state = ConnectionState.DISCONNECTED
            return
        heartbeat_age = self._heartbeat_age_seconds()
        if self._receive_backlog:
            self._connection_state = ConnectionState.STALE
            self._connection_error = (
                "A fila MAVLink não foi drenada no limite de tempo/mensagens; "
                "o estado recebido ainda não pode ser considerado atual."
            )
        elif heartbeat_age is None:
            self._connection_state = ConnectionState.WAITING_HEARTBEAT
        elif heartbeat_age <= self._settings.heartbeat_timeout_seconds:
            self._connection_state = ConnectionState.CONNECTED
            self._connection_error = None
        else:
            self._connection_state = ConnectionState.STALE
            self._connection_error = (
                f"Nenhum heartbeat válido nos últimos {heartbeat_age:.1f} segundos."
            )

    def _require_live_heartbeat(self, operation: str) -> None:
        self._refresh_connection_state()
        if self._connection_state is not ConnectionState.CONNECTED:
            raise VehicleTimeoutError(
                f"{operation} bloqueado: heartbeat válido não está disponível."
            )

    def _message_is_fresh(self, *message_types: str, timeout: float | None = None) -> bool:
        if self._receive_backlog:
            return False
        latest = max(
            (
                self._last_message_monotonic[item]
                for item in message_types
                if item in self._last_message_monotonic
            ),
            default=None,
        )
        if latest is None:
            return False
        limit = timeout or self._settings.mavlink_telemetry_stale_seconds
        return time.monotonic() - latest <= limit

    def _send_gcs_heartbeat_if_due(self) -> None:
        if (
            self._passive_connection
            or self._connection is None
            or (self._settings.is_hardware_mode and not self._settings.real_hardware_acknowledged)
        ):
            return
        now = time.monotonic()
        if (
            self._last_gcs_heartbeat_monotonic is not None
            and now - self._last_gcs_heartbeat_monotonic
            < self._settings.gcs_heartbeat_interval_seconds
        ):
            return
        mavlink = self._required_mavutil().mavlink
        self._connection.mav.heartbeat_send(
            getattr(mavlink, "MAV_TYPE_GCS", 6),
            getattr(mavlink, "MAV_AUTOPILOT_INVALID", 8),
            0,
            0,
            getattr(mavlink, "MAV_STATE_ACTIVE", 4),
        )
        self._last_gcs_heartbeat_monotonic = now
        logger.debug("GCS heartbeat sent")

    def _queue_event(
        self,
        *,
        event_type: str,
        severity: str,
        message: str,
        metadata: dict[str, str | int | float | bool | None],
    ) -> None:
        self._events.append(
            VehicleEvent(
                event_type=event_type,
                severity=severity,
                message=message,
                metadata=metadata,
                occurred_at=datetime.now(UTC),
            )
        )

    async def drain_events(self) -> list[VehicleEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    def _flight_observation(self, position_fresh: bool) -> Px4FlightObservation | None:
        if self._settings.autopilot_system.strip().upper() != "PX4" or not self._passive_connection:
            return None
        current = (
            self._px4_mission_current
            if self._message_is_fresh("MISSION_CURRENT")
            else Px4FlightObservation()
        )
        return current.model_copy(
            update={
                "landed_state": (
                    self._landed_state
                    if self._message_is_fresh("EXTENDED_SYS_STATE")
                    and self._landed_state in {1, 2, 3, 4}
                    else None
                ),
                "position_at": self._last_position_recorded_at if position_fresh else None,
            }
        )

    async def read_health(self) -> VehicleHealth:
        if self._connection is not None:
            await asyncio.to_thread(self._drain_messages)
            await asyncio.to_thread(self._request_safety_state_if_due)
        self._refresh_connection_state()
        heartbeat_age = self._heartbeat_age_seconds()
        heartbeat = self._connection_state is ConnectionState.CONNECTED
        connected = self._connection is not None and heartbeat
        gps_fresh = self._message_is_fresh("GPS_RAW_INT")
        battery_fresh = self._message_is_fresh("BATTERY")
        ekf_fresh = self._message_is_fresh("ESTIMATOR")
        status_fresh = self._message_is_fresh("SYS_STATUS")
        position_fresh = self._message_is_fresh("GLOBAL_POSITION_INT")
        home_fresh = self._message_is_fresh("HOME_POSITION")
        heartbeat_fields_fresh = heartbeat
        connection = self._connection
        target_system = int(connection.target_system) if connection is not None else None
        target_component = int(connection.target_component) if connection is not None else None
        try:
            return VehicleHealth(
                source=self._operational_source(),
                autopilot_version=self._autopilot_version,
                connected=connected,
                heartbeat=heartbeat,
                gps_fix_type=self._gps_fix if gps_fresh else None,
                satellites=self._satellites if gps_fresh else None,
                ekf_ok=self._ekf_ok if ekf_fresh else None,
                battery_percent=self._battery_percent if battery_fresh else None,
                battery_voltage=self._battery_voltage if battery_fresh else None,
                flight_mode=self._mode if heartbeat_fields_fresh else None,
                armed=self._armed if heartbeat_fields_fresh else None,
                preflight_ok=self._preflight_ok if status_fresh else None,
                rtl_configured=(
                    self._rtl_configured if self._message_is_fresh("PARAM:RTL_ALT") else None
                ),
                px4_diagnostics=self._px4_diagnostics(),
                geofence_enabled=(
                    self._geofence_enabled if self._message_is_fresh("PARAM:FENCE_ENABLE") else None
                ),
                origin_latitude=self._origin_latitude if home_fresh else None,
                origin_longitude=self._origin_longitude if home_fresh else None,
                connection_state=self._connection_state,
                connection_mode=self._settings.mavlink_mode.value,
                connection_topology=self._settings.connection_topology,
                connection_endpoint=self._settings.sanitized_connection,
                serial_port=self._upstream_serial_port(),
                connection_baud=(
                    self._settings.mavlink_baud_rate
                    if self._upstream_serial_port() is not None
                    else None
                ),
                mavlink_system_id=target_system if target_system and target_system > 0 else None,
                mavlink_component_id=(
                    target_component
                    if target_component is not None and target_component >= 0
                    else None
                ),
                heartbeat_age_seconds=heartbeat_age,
                last_heartbeat_at=self._last_heartbeat_recorded_at,
                current_latitude=self._latitude if position_fresh else None,
                current_longitude=self._longitude if position_fresh else None,
                current_altitude_m=self._relative_altitude_m if position_fresh else None,
                current_amsl_m=self._current_amsl_m if position_fresh else None,
                current_ground_speed_m_s=self._ground_speed_m_s if position_fresh else None,
                px4_flight=self._flight_observation(position_fresh),
                mission_upload_enabled=self._settings.allow_mission_upload,
                flight_commands_enabled=self._settings.allow_flight_commands,
                mission_start_enabled=self._settings.allow_mission_start,
                vehicle_arm_enabled=self._settings.allow_vehicle_arm,
                bench_arm_session_id=self._bench_arm_session_id if connected else None,
                connection_error=self._connection_error,
            )
        except ValidationError as exc:
            raise VehicleConnectionError(
                "Estado MAVLink contém valores fora do contrato do backend."
            ) from exc

    async def upload_mission(self, mission: AuthorizedMission, mission_file: str) -> UploadResult:
        del mission_file
        self._require_live_heartbeat("upload")
        if not self._settings.allow_mission_upload:
            raise UnsafeOperationError("ALLOW_MISSION_UPLOAD não foi habilitado.")
        key = str(mission.id)
        previous_hash = self._uploaded.get(key)
        if previous_hash == mission.mission_sha256:
            return UploadResult(
                item_count=len(mission.waypoints),
                acknowledged=True,
                detail="MISSION_ACK do mesmo mission_id/hash já foi registrado nesta sessão.",
            )
        if previous_hash is not None:
            raise MissionUploadError("Missão já enviada com outro hash.")
        await asyncio.to_thread(self._upload_sync, mission)
        self._uploaded[key] = mission.mission_sha256
        self._verified.pop(key, None)
        self._last_current_sequence = None
        self._reached_sequences.clear()
        self._reported_progress.pop(key, None)
        return UploadResult(
            item_count=len(mission.waypoints),
            acknowledged=True,
            detail="MISSION_ACK aceito; a releitura ainda precisa ser verificada.",
        )

    async def verify_mission(self, mission: AuthorizedMission) -> MissionVerificationResult:
        self._require_live_heartbeat("verificação da missão")
        if not self._settings.allow_mission_upload:
            raise UnsafeOperationError("ALLOW_MISSION_UPLOAD não foi habilitado.")
        key = str(mission.id)
        if self._verified.get(key) == mission.mission_sha256:
            return MissionVerificationResult(
                item_count=len(mission.waypoints),
                verified=True,
                detail="A mesma versão/hash já foi verificada nesta sessão.",
            )
        await asyncio.to_thread(self._verify_mission_sync, mission)
        self._uploaded[key] = mission.mission_sha256
        self._verified[key] = mission.mission_sha256
        return MissionVerificationResult(
            item_count=len(mission.waypoints),
            verified=True,
            detail="Contagem e conteúdo foram relidos e comparados com a missão autorizada.",
        )

    async def arm_vehicle(self) -> VehicleArmResult:
        if not self._settings.allow_vehicle_arm:
            raise UnsafeOperationError("ALLOW_VEHICLE_ARM não foi habilitado.")
        if not self._settings.allow_flight_commands:
            raise UnsafeOperationError("Armamento exige ALLOW_FLIGHT_COMMANDS habilitado.")
        if self._passive_connection:
            raise UnsafeOperationError("Conexão receive-only não pode armar o veículo.")
        async with self._arm_command_lock:
            await asyncio.to_thread(self._prepare_arm_transaction)
            self._require_live_heartbeat("armamento")
            if not self._settings.px4_sitl_plan_validation:
                if not self._message_is_fresh("SYS_STATUS") or self._preflight_ok is not True:
                    raise UnsafeOperationError(
                        "Armamento exige SYS_STATUS fresco com preflight aprovado."
                    )
                if (self._mode or "").strip().upper() != "STABILIZE":
                    raise UnsafeOperationError("Armamento exige modo STABILIZE.")
            if self._armed is True:
                return VehicleArmResult(
                    command_sent=False,
                    command_acknowledged=False,
                    armed_heartbeat_confirmed=True,
                    external_state_reconciled=True,
                )
            await asyncio.to_thread(self._arm_vehicle_sync)
            return VehicleArmResult(
                command_sent=True,
                command_acknowledged=True,
                armed_heartbeat_confirmed=True,
                external_state_reconciled=False,
            )

    def _prepare_arm_transaction(self) -> None:
        timeout = min(
            self._ARM_DRAIN_TIMEOUT_SECONDS, self._settings.mission_command_timeout_seconds
        )
        if self._drain_messages(timeout=timeout):
            return
        raise UnsafeOperationError(
            "Armamento bloqueado: a fila MAVLink não estabilizou antes da transação "
            f"(limite {timeout:g}s/{self._RECEIVE_MAX_DRAIN_MESSAGES} mensagens); "
            "nenhum ARM foi enviado."
        )

    async def arm_bench(self, request: BenchArmClaim) -> BenchArmEvidence:
        evidence = BenchArmEvidence()
        async with self._arm_command_lock:
            async with self._connection_lock:
                try:
                    if (
                        not self._settings.is_px4_bench_arm
                        or not self._settings.allow_vehicle_arm
                        or request.session_id != self._bench_arm_session_id
                    ):
                        raise UnsafeOperationError(
                            "Sessão física de ARM indisponível ou substituída."
                        )
                    await asyncio.to_thread(self._prepare_arm_transaction)
                    self._require_live_heartbeat("ARM de bancada")
                    connection = self._required_connection()
                    if (connection.target_system, connection.target_component) != (
                        request.target_system,
                        request.target_component,
                    ):
                        raise UnsafeOperationError("Alvo MAVLink diferente da solicitação.")
                    if self._armed is not False:
                        raise UnsafeOperationError("O último heartbeat não confirma desarmamento.")
                    await asyncio.to_thread(self._arm_vehicle_sync, evidence, request.expires_at)
                    evidence.detail = "PX4 aceitou ARM e um novo heartbeat confirmou armamento."
                except (GatewayError, OSError) as exc:
                    evidence.detail = str(exc)
        return evidence

    def _arm_vehicle_sync(
        self,
        evidence: BenchArmEvidence | None = None,
        expires_at: datetime | None = None,
    ) -> None:
        connection = self._required_connection()
        mavlink = self._required_mavutil().mavlink
        command = mavlink.MAV_CMD_COMPONENT_ARM_DISARM
        accepted = mavlink.MAV_RESULT_ACCEPTED
        first_heartbeat = self._last_heartbeat_monotonic
        transaction_deadline = time.monotonic() + self._settings.mission_command_timeout_seconds

        attempts = (
            1
            if evidence is not None or self._settings.px4_sitl_plan_validation
            else self._ARM_MAX_SEND_ATTEMPTS
        )
        for attempt in range(attempts):
            remaining = transaction_deadline - time.monotonic()
            if remaining <= 0:
                break
            if expires_at is not None and datetime.now(UTC) >= expires_at:
                raise UnsafeOperationError("Prazo de transmissão da solicitação expirou.")
            if evidence is not None:
                evidence.transmitted = None  # A falha de escrita pode ser parcial.
            try:
                connection.mav.command_long_send(
                    connection.target_system,
                    connection.target_component,
                    command,
                    attempt,
                    1,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                )
                if evidence is not None:
                    evidence.transmitted = True
            except (AttributeError, OSError, TypeError, ValueError) as exc:
                raise VehicleConnectionError(
                    "Falha ao enviar o comando MAVLink normal de armamento."
                ) from exc

            ack_deadline = (
                transaction_deadline
                if attempts == 1
                else min(
                    transaction_deadline,
                    time.monotonic() + self._settings.mission_protocol_step_timeout_seconds,
                )
            )
            result, armed_heartbeat_seen = self._receive_strict_arm_ack(
                command,
                first_heartbeat=first_heartbeat,
                deadline=ack_deadline,
            )
            if evidence is not None:
                evidence.ack_result = result
            if result is None:
                if armed_heartbeat_seen:
                    raise VehicleTimeoutError(
                        "Heartbeat novo mostrou armed=true sem COMMAND_ACK correlacionado; "
                        "o resultado é incerto e o comando não será reenviado."
                    )
                continue
            if result != accepted:
                if armed_heartbeat_seen:
                    raise VehicleTimeoutError(
                        "Heartbeat novo mostrou armed=true, mas o COMMAND_ACK rejeitou ARM; "
                        "o estado é inconsistente, incerto e não será reenviado."
                    )
                raise UnsafeOperationError(f"Armamento rejeitado pelo veículo: {result}")
            if self._wait_for_new_armed_heartbeat(
                first_heartbeat,
                deadline=transaction_deadline,
            ):
                if evidence is not None:
                    evidence.armed_confirmed = True
                return
            if armed_heartbeat_seen:
                raise VehicleTimeoutError(
                    "COMMAND_ACK aceitou ARM, mas o heartbeat armado foi seguido por "
                    "armed=false; o resultado final é incerto."
                )
            raise VehicleTimeoutError(
                "ACK de armamento aceito, mas nenhum heartbeat novo confirmou armed=true."
            )

        raise VehicleTimeoutError(
            "Timeout aguardando COMMAND_ACK estritamente correlacionado do armamento."
        )

    def _receive_strict_arm_ack(
        self,
        command: int,
        *,
        first_heartbeat: float | None,
        deadline: float,
    ) -> tuple[int | None, bool]:
        connection = self._required_connection()
        in_progress = self._required_mavutil().mavlink.MAV_RESULT_IN_PROGRESS
        armed_heartbeat_seen = False
        while time.monotonic() < deadline:
            self._send_gcs_heartbeat_if_due()
            message = connection.recv_match(
                blocking=True,
                timeout=max(0.01, deadline - time.monotonic()),
            )
            if message is None:
                continue
            if message.get_type() != "COMMAND_ACK":
                self._ingest_message(message)
                if (
                    message.get_type() == "HEARTBEAT"
                    and self._last_heartbeat_monotonic is not None
                    and (
                        first_heartbeat is None or self._last_heartbeat_monotonic > first_heartbeat
                    )
                    and self._armed is True
                ):
                    armed_heartbeat_seen = True
                continue
            if int(getattr(message, "command", -1)) != command:
                continue
            if not self._arm_ack_matches_transaction(message):
                continue
            result = int(message.result)
            if result == in_progress:
                continue
            return result, armed_heartbeat_seen
        return None, armed_heartbeat_seen

    def _arm_ack_matches_transaction(self, message: Any) -> bool:
        if not self._message_matches_target(message):
            return False
        connection = self._required_connection()
        try:
            return int(message.target_system) == int(connection.source_system) and int(
                message.target_component
            ) == int(connection.source_component)
        except (AttributeError, TypeError, ValueError):
            return False

    def _wait_for_new_armed_heartbeat(
        self,
        first_heartbeat: float | None,
        *,
        deadline: float,
    ) -> bool:
        connection = self._required_connection()
        while time.monotonic() < deadline:
            if (
                self._last_heartbeat_monotonic is not None
                and (first_heartbeat is None or self._last_heartbeat_monotonic > first_heartbeat)
                and self._armed is True
            ):
                return True
            self._send_gcs_heartbeat_if_due()
            message = connection.recv_match(
                blocking=True,
                timeout=max(0.01, deadline - time.monotonic()),
            )
            if message is not None:
                self._ingest_message(message)
        return False

    def _upload_sync(self, mission: AuthorizedMission) -> None:
        connection = self._required_connection()
        mavutil = self._required_mavutil()
        ordered = sorted(mission.waypoints, key=lambda item: item.sequence)
        if [item.sequence for item in ordered] != list(range(len(ordered))):
            raise MissionUploadError("Waypoints não possuem sequência contígua.")
        if self._settings.autopilot_system.strip().upper() == "PX4":
            # This narrow allowlist is not a substitute for validating the
            # installed PX4 version or the route before enabling upload.
            if not ordered or any(item.command not in {16, 19, 20, 21, 22} for item in ordered):
                raise MissionUploadError("Missão PX4 contém comando não validado ou está vazia.")
            if any(
                (item.command == 20 and item.frame != 2) or (item.command != 20 and item.frame != 3)
                for item in ordered
            ):
                raise MissionUploadError(
                    "Missão PX4 exige frame 2 para RTL e frame 3 para itens posicionais."
                )
            if any(item.param4 is None and item.command not in {16, 22} for item in ordered):
                raise MissionUploadError("Orientação nula não é suportada neste comando PX4.")
            if any(
                item.command == 20
                and any(
                    value != 0
                    for value in (
                        item.param1,
                        item.param2,
                        item.param3,
                        item.param4,
                        item.latitude,
                        item.longitude,
                        item.altitude_m,
                    )
                )
                for item in ordered
            ):
                raise MissionUploadError("RTL PX4 exige parâmetros reservados zerados.")
        self._send_mission_count(len(ordered))
        sent_sequences: set[int] = set()
        last_sequence: int | None = None
        retries = 0
        overall_deadline = time.monotonic() + self._settings.mission_command_timeout_seconds
        while time.monotonic() < overall_deadline:
            self._send_gcs_heartbeat_if_due()
            message = connection.recv_match(
                type=["MISSION_REQUEST", "MISSION_REQUEST_INT", "MISSION_ACK"],
                blocking=True,
                timeout=min(
                    self._settings.mission_protocol_step_timeout_seconds,
                    max(0.05, overall_deadline - time.monotonic()),
                ),
            )
            if message is None:
                retries += 1
                if retries > self._settings.mission_protocol_retries:
                    expected = "MISSION_REQUEST_INT" if last_sequence is None else "MISSION_ACK"
                    raise VehicleTimeoutError(
                        f"Timeout aguardando {expected}; retries da etapa esgotados."
                    )
                if last_sequence is None:
                    self._send_mission_count(len(ordered))
                else:
                    self._send_mission_item_int(ordered[last_sequence])
                continue
            if not self._message_matches_mission_operation(message):
                continue
            retries = 0
            message_type = message.get_type()
            if message_type == "MISSION_ACK":
                if int(message.type) != mavutil.mavlink.MAV_MISSION_ACCEPTED:
                    raise MissionUploadError(f"MISSION_ACK rejeitou upload: {message.type}")
                if sent_sequences != set(range(len(ordered))):
                    raise MissionUploadError(
                        "MISSION_ACK chegou antes de todos os waypoints serem solicitados."
                    )
                return
            sequence = int(message.seq)
            if sequence < 0 or sequence >= len(ordered):
                raise MissionUploadError(f"Veículo solicitou waypoint inexistente: {sequence}")
            waypoint = ordered[sequence]
            sent_sequences.add(sequence)
            last_sequence = sequence
            # MAVLink Mission Protocol requires ITEM_INT even for a legacy REQUEST.
            self._send_mission_item_int(waypoint)
        raise VehicleTimeoutError("Timeout aguardando requests/ACK do upload MAVLink.")

    def _send_mission_count(self, item_count: int) -> None:
        connection = self._required_connection()
        connection.mav.mission_count_send(
            connection.target_system,
            connection.target_component,
            item_count,
        )

    def _send_mission_item_int(self, waypoint: Any) -> None:
        connection = self._required_connection()
        if waypoint.param4 is None and (
            self._settings.autopilot_system.strip().upper() != "PX4"
            or waypoint.command not in {16, 22}
        ):
            raise MissionUploadError("Orientação nula não é suportada neste comando.")
        connection.mav.mission_item_int_send(
            connection.target_system,
            connection.target_component,
            waypoint.sequence,
            self._int_frame(waypoint.frame),
            waypoint.command,
            waypoint.current,
            waypoint.autocontinue,
            waypoint.param1,
            waypoint.param2,
            waypoint.param3,
            math.nan if waypoint.param4 is None else waypoint.param4,
            round(waypoint.latitude * 10_000_000),
            round(waypoint.longitude * 10_000_000),
            waypoint.altitude_m,
        )

    def _message_matches_mission_operation(self, message: Any) -> bool:
        connection = self._required_connection()
        source_system = getattr(message, "get_srcSystem", None)
        if not callable(source_system) or int(source_system()) != int(connection.target_system):
            return False
        source_component = getattr(message, "get_srcComponent", None)
        if not callable(source_component) or (
            int(connection.target_component) > 0
            and int(source_component()) != int(connection.target_component)
        ):
            return False
        target_system = getattr(message, "target_system", connection.source_system)
        if int(target_system) not in {0, int(connection.source_system)}:
            return False
        own_component = int(
            getattr(
                connection,
                "source_component",
                self._settings.mavlink_source_component_id,
            )
        )
        target_component = getattr(message, "target_component", own_component)
        if int(target_component) not in {0, own_component}:
            return False
        mission_type = getattr(message, "mission_type", 0)
        return int(mission_type) == 0

    def _int_frame(self, frame: int) -> int:
        mavutil = self._required_mavutil()
        mappings = {
            getattr(mavutil.mavlink, "MAV_FRAME_GLOBAL", 0): getattr(
                mavutil.mavlink, "MAV_FRAME_GLOBAL_INT", 5
            ),
            getattr(mavutil.mavlink, "MAV_FRAME_GLOBAL_RELATIVE_ALT", 3): getattr(
                mavutil.mavlink, "MAV_FRAME_GLOBAL_RELATIVE_ALT_INT", 6
            ),
            getattr(mavutil.mavlink, "MAV_FRAME_GLOBAL_TERRAIN_ALT", 10): getattr(
                mavutil.mavlink, "MAV_FRAME_GLOBAL_TERRAIN_ALT_INT", 11
            ),
        }
        return mappings.get(frame, frame)

    def _recv_mission_message(
        self,
        message_types: str | list[str],
        *,
        sequence: int | None = None,
        timeout: float | None = None,
    ) -> Any:
        connection = self._required_connection()
        accepted_types = {message_types} if isinstance(message_types, str) else set(message_types)
        deadline = time.monotonic() + (
            timeout or self._settings.mission_protocol_step_timeout_seconds
        )
        while time.monotonic() < deadline:
            self._send_gcs_heartbeat_if_due()
            self._request_safety_state_if_due()
            # Filtering in pymavlink would consume HOME/PARAM/HEARTBEAT without
            # updating our freshness cache. Ingest first, then match the transaction.
            message = connection.recv_match(
                blocking=True,
                timeout=min(0.5, max(0.01, deadline - time.monotonic())),
            )
            if message is None:
                continue
            self._ingest_message(message)
            if (
                message.get_type() not in accepted_types
                or not self._message_matches_mission_operation(message)
            ):
                continue
            if sequence is not None and int(getattr(message, "seq", -1)) != sequence:
                continue
            return message
        expected = ", ".join(message_types) if isinstance(message_types, list) else message_types
        raise VehicleTimeoutError(f"Timeout aguardando {expected} na verificação da missão.")

    def _verify_mission_sync(self, mission: AuthorizedMission) -> None:
        ordered = sorted(mission.waypoints, key=lambda item: item.sequence)
        if (
            self._settings.autopilot_system.strip().upper() != "PX4"
            and self._telemetry_requests_enabled
            and ordered
            and ordered[0].sequence == 0
            and ordered[0].command == 16
            and self._int_frame(ordered[0].frame) == self._int_frame(3)
            and ordered[0].altitude_m == 0
            and not self._message_is_fresh("HOME_POSITION")
        ):
            self._recv_mission_message(
                "HOME_POSITION", timeout=self._settings.mission_command_timeout_seconds
            )
        self._verify_stored_waypoints(ordered)

    async def verify_bench_readback(
        self, waypoints: list[MissionWaypoint], system_id: int, component_id: int
    ) -> int | None:
        if (
            self._settings.px4_bench_readback_dir is None
            or not self._passive_connection
            or self._telemetry_requests_enabled
        ):
            raise UnsafeOperationError("Releitura de bancada está indisponível neste enlace.")
        connection = self._required_connection()
        if (connection.target_system, connection.target_component) != (system_id, component_id):
            raise UnsafeOperationError(
                "A identidade PX4 do enlace diverge da identidade informada."
            )
        if (
            not waypoints
            or len(waypoints) > 20
            or [point.sequence for point in waypoints] != list(range(len(waypoints)))
        ):
            raise MissionUploadError("A releitura exige uma sequência de 1 a 20 itens.")
        plan_id = await asyncio.to_thread(
            self._verify_stored_waypoints, waypoints, bench_readback=True
        )
        # The next observation must come from a message received after readback.
        self._last_mission_observation = None
        return plan_id

    def _verify_stored_waypoints(
        self, ordered: list[MissionWaypoint], *, bench_readback: bool = False
    ) -> int | None:
        connection = self._required_connection()
        mavutil = self._required_mavutil()
        target_system = connection.target_system
        target_component = connection.target_component
        retries = 0 if bench_readback else self._settings.mission_protocol_retries
        if bench_readback:
            self._check_bench_readback_state()
        count_message = None
        for attempt in range(retries + 1):
            connection.mav.mission_request_list_send(target_system, target_component)
            try:
                count_message = self._recv_mission_message("MISSION_COUNT")
                break
            except VehicleTimeoutError:
                if attempt >= retries:
                    raise
        if count_message is None:  # pragma: no cover - guarded by the retry loop
            raise VehicleTimeoutError("MISSION_COUNT não chegou durante a verificação.")
        if int(count_message.count) != len(ordered):
            raise MissionUploadError(
                f"Veículo armazenou {count_message.count} waypoints; esperado {len(ordered)}."
            )
        for sequence, expected in enumerate(ordered):
            if bench_readback:
                self._check_bench_readback_state()
            actual = None
            for attempt in range(retries + 1):
                connection.mav.mission_request_int_send(target_system, target_component, sequence)
                try:
                    actual = self._recv_mission_message(
                        ["MISSION_ITEM_INT", "MISSION_ITEM"], sequence=sequence
                    )
                    break
                except VehicleTimeoutError:
                    if attempt >= retries:
                        raise
            if actual is None:  # pragma: no cover - guarded by the retry loop
                raise VehicleTimeoutError(f"Waypoint {sequence} não chegou durante a verificação.")
            self._verify_downloaded_waypoint(actual, expected)
        connection.mav.mission_ack_send(
            target_system,
            target_component,
            mavutil.mavlink.MAV_MISSION_ACCEPTED,
        )
        return _mission_plan_id(count_message, "opaque_id", 5) if bench_readback else None

    def _check_bench_readback_state(self) -> None:
        self._drain_messages()
        self._require_live_heartbeat("releitura de bancada")
        if self._armed is not False:
            raise UnsafeOperationError("A releitura de bancada exige PX4 desarmado.")

    def _verify_downloaded_waypoint(self, actual: Any, expected: MissionWaypoint) -> None:
        # The received message is a dynamic pymavlink dialect class.
        message_type = actual.get_type()
        is_px4 = self._settings.autopilot_system.strip().upper() == "PX4"
        if is_px4 and expected.command not in {16, 19, 20, 21, 22}:
            raise MissionUploadError("Comando não validado para releitura PX4.")
        actual_frame = self._int_frame(int(actual.frame))
        expected_frame = self._int_frame(expected.frame)
        nonpositional_command = expected.command == 211
        accepted_frames = {expected_frame}
        expected_altitude = expected.altitude_m
        expected_latitude = expected.latitude
        expected_longitude = expected.longitude
        # ArduCopter returns item 0 from live HOME, with an absolute MSL altitude.
        # Only the canonical relative-zero HOME marker may use this conversion.
        absolute_home = (
            not is_px4
            and expected.sequence == 0
            and expected.command == 16
            and expected_frame == self._int_frame(3)
            and expected.altitude_m == 0
            and actual_frame == self._int_frame(0)
        )
        if absolute_home:
            expected_latitude, expected_longitude, expected_altitude = self._verified_home(expected)
            accepted_frames.add(self._int_frame(0))
        if nonpositional_command and not is_px4:
            # AP_Mission emits frame GLOBAL and zero location for DO_GRIPPER.
            accepted_frames.add(self._int_frame(0))
            accepted_frames.add(getattr(self._required_mavutil().mavlink, "MAV_FRAME_MISSION", 2))
        if actual_frame not in accepted_frames:
            raise MissionUploadError(
                f"Frame relido diverge no waypoint {expected.sequence}: {actual_frame}."
            )
        for actual_field, expected_field in (
            ("seq", "sequence"),
            ("command", "command"),
            ("autocontinue", "autocontinue"),
        ):
            if int(getattr(actual, actual_field)) != int(getattr(expected, expected_field)):
                raise MissionUploadError(
                    f"Campo {actual_field} relido diverge no waypoint {expected.sequence}."
                )
        # current is execution state, not part of the stored mission content.
        if int(actual.current) not in {0, 1}:
            raise MissionUploadError(f"Campo current inválido no waypoint {expected.sequence}.")
        for field in ("param1", "param2", "param3", "param4"):
            actual_value = float(getattr(actual, field))
            expected_field_value = getattr(expected, field)
            if expected_field_value is None:
                if (
                    is_px4
                    and expected.command in {16, 22}
                    and field == "param4"
                    and math.isnan(actual_value)
                ):
                    continue
                raise MissionUploadError(
                    f"Campo {field} relido diverge no waypoint {expected.sequence}."
                )
            expected_value = float(expected_field_value)
            # AP_Mission stores direction flags for LOITER_TIME and LAND.
            # Its default zero input is returned as +1; do not generalize this
            # to arbitrary radii, yaw requests, commands, or other parameters.
            if (
                not is_px4
                and (expected.command, field) in {(19, "param3"), (21, "param4")}
                and expected_value == 0
                and actual_value == 1
            ):
                continue
            if not math.isclose(
                actual_value,
                expected_value,
                rel_tol=1e-6,
                abs_tol=1e-5,
            ):
                raise MissionUploadError(
                    f"Campo {field} relido diverge no waypoint {expected.sequence}."
                )
        if nonpositional_command:
            return
        if message_type == "MISSION_ITEM_INT":
            latitude = float(actual.x) / 10_000_000
            longitude = float(actual.y) / 10_000_000
        else:
            latitude = float(actual.x)
            longitude = float(actual.y)
        if not math.isclose(
            latitude, expected_latitude, rel_tol=0, abs_tol=1e-6
        ) or not math.isclose(longitude, expected_longitude, rel_tol=0, abs_tol=1e-6):
            raise MissionUploadError(
                f"Coordenadas relidas divergem no waypoint {expected.sequence}."
            )
        if not math.isclose(float(actual.z), expected_altitude, rel_tol=0, abs_tol=0.05):
            raise MissionUploadError(f"Altitude relida diverge no waypoint {expected.sequence}.")

    def _verified_home(self, expected: MissionWaypoint) -> tuple[float, float, float]:
        if (
            not self._message_is_fresh("HOME_POSITION")
            or self._home_altitude_m is None
            or not math.isfinite(self._home_altitude_m)
            or self._origin_latitude is None
            or self._origin_longitude is None
            or not -90 <= self._origin_latitude <= 90
            or not -180 <= self._origin_longitude <= 180
        ):
            raise MissionUploadError(
                "HOME_POSITION ausente, vencida ou divergente da origem da missão."
            )
        # AP_Mission item 0 is live AHRS Home, not the stored route origin.
        # Reuse the preflight origin bound; all flight items still compare exactly.
        if (
            distance_m(
                self._origin_latitude, self._origin_longitude, expected.latitude, expected.longitude
            )
            > self._settings.max_origin_deviation_m
        ):
            raise MissionUploadError("HOME_POSITION fora do limite de desvio da origem da missão.")
        return self._origin_latitude, self._origin_longitude, self._home_altitude_m

    async def start_mission(self, mission: AuthorizedMission) -> None:
        self._require_live_heartbeat("start")
        if not self._settings.allow_flight_commands or not self._settings.allow_mission_start:
            raise UnsafeOperationError(
                "ALLOW_FLIGHT_COMMANDS e ALLOW_MISSION_START devem estar habilitados."
            )
        if self._armed is not True:
            raise UnsafeOperationError(
                "Veículo não está comprovadamente armado; o gateway não arma automaticamente. "
                "Operador deve seguir o procedimento."
            )
        await asyncio.to_thread(self._verify_mission_sync, mission)
        if self._settings.px4_sitl_plan_validation:
            await asyncio.to_thread(self._start_px4_sitl_sync)
            return
        await asyncio.to_thread(self._command_and_wait, "MISSION_START")

    def _start_px4_sitl_sync(self) -> None:
        if not self._drain_messages():
            raise UnsafeOperationError("Fila MAVLink indisponível para iniciar a missão.")
        self._require_live_heartbeat("START PX4 SITL")
        if self._armed is not True:
            raise UnsafeOperationError("Heartbeat do PX4 SITL já não confirma armamento.")
        if (self._mode or "").strip().upper() == "MISSION":
            raise UnsafeOperationError("PX4 SITL já está em modo de missão.")
        previous_heartbeat = self._last_heartbeat_monotonic
        self._reached_sequences.clear()
        self._saw_sitl_airborne = False
        self._saw_sitl_destination = False
        self._command_and_wait("PX4_SITL_MISSION_MODE")
        self._confirm_px4_mode("MISSION", previous_heartbeat)

    async def synchronize_progress(
        self,
        mission: AuthorizedMission,
        last_reported_status: MissionStatus | None,
    ) -> None:
        if last_reported_status not in MISSION_PROGRESS_STATUSES:
            return
        reported = self._reported_progress.setdefault(str(mission.id), set())
        last_index = MISSION_PROGRESS_STATUSES.index(last_reported_status)
        reported.update(MISSION_PROGRESS_STATUSES[: last_index + 1])

    def _command_and_wait(self, command_name: str) -> None:
        connection = self._required_connection()
        mavutil = self._required_mavutil()
        command_by_name = {
            "MISSION_START": mavutil.mavlink.MAV_CMD_MISSION_START,
            "PAUSE": mavutil.mavlink.MAV_CMD_DO_PAUSE_CONTINUE,
            "CONTINUE": mavutil.mavlink.MAV_CMD_DO_PAUSE_CONTINUE,
            "RTL": mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
        }
        parameters = (1 if command_name == "CONTINUE" else 0, 0, 0)
        if command_name == "PX4_SITL_MISSION_MODE":
            # Change mode only; some PX4 versions can arm as part of MISSION_START.
            command = mavutil.mavlink.MAV_CMD_DO_SET_MODE
            parameters = mavutil.px4_map["MISSION"]
        else:
            command = command_by_name[command_name]
        while (
            connection.recv_match(
                type="COMMAND_ACK",
                condition=f"COMMAND_ACK.command=={command}",
                blocking=False,
            )
            is not None
        ):
            pass
        connection.mav.command_long_send(
            connection.target_system,
            connection.target_component,
            command,
            0,
            *parameters,
            0,
            0,
            0,
            0,
        )
        result = self._receive_command_ack_result(
            command,
            timeout=self._settings.mission_command_timeout_seconds,
        )
        if result is None:
            raise VehicleTimeoutError(f"Timeout aguardando ACK válido de {command_name}.")
        if result != mavutil.mavlink.MAV_RESULT_ACCEPTED:
            raise UnsafeOperationError(f"{command_name} rejeitado pelo veículo: {result}")

    async def pause_mission(self) -> None:
        self._require_live_heartbeat("pause")
        if not self._settings.allow_flight_commands:
            raise UnsafeOperationError("ALLOW_FLIGHT_COMMANDS não foi habilitado.")
        await asyncio.to_thread(self._command_and_wait, "PAUSE")

    async def continue_mission(self) -> None:
        self._require_live_heartbeat("continue")
        if not self._settings.allow_flight_commands:
            raise UnsafeOperationError("ALLOW_FLIGHT_COMMANDS não foi habilitado.")
        await asyncio.to_thread(self._command_and_wait, "CONTINUE")

    async def read_telemetry(self) -> TelemetrySnapshot:
        await asyncio.to_thread(self._drain_messages)
        self._refresh_connection_state()
        heartbeat_fresh = self._connection_state is ConnectionState.CONNECTED
        if not heartbeat_fresh:
            raise VehicleTimeoutError("Heartbeat ficou vencido durante a missão.")
        if self._latitude is None or self._longitude is None:
            raise VehicleTimeoutError("GLOBAL_POSITION_INT ainda não está disponível.")
        if (
            self._last_position_monotonic is None
            or time.monotonic() - self._last_position_monotonic
            > self._settings.heartbeat_timeout_seconds
            or self._last_position_recorded_at is None
        ):
            raise VehicleTimeoutError("GLOBAL_POSITION_INT ficou vencido durante a missão.")
        try:
            telemetry = TelemetrySnapshot(
                source=self._operational_source(),
                latitude=self._latitude,
                longitude=self._longitude,
                relative_altitude_m=self._relative_altitude_m,
                ground_speed_m_s=self._ground_speed_m_s,
                battery_percent=(
                    self._battery_percent if self._message_is_fresh("BATTERY") else None
                ),
                gps_fix_type=(self._gps_fix if self._message_is_fresh("GPS_RAW_INT") else None),
                satellites=(self._satellites if self._message_is_fresh("GPS_RAW_INT") else None),
                flight_mode=self._mode,
                armed=self._armed,
                recorded_at=self._last_position_recorded_at,
            )
        except ValidationError as exc:
            raise VehicleConnectionError(
                "Telemetria MAVLink contém valores fora do contrato do backend."
            ) from exc
        return telemetry

    async def poll_mission(self, mission: AuthorizedMission) -> VehiclePoll:
        telemetry = await self.read_telemetry()
        suggested_status = self._next_progress_status(mission)
        events = await self.drain_events()
        return VehiclePoll(
            telemetry=telemetry,
            suggested_status=suggested_status,
            events=events,
        )

    def _next_progress_status(self, mission: AuthorizedMission) -> MissionStatus | None:
        ordered = sorted(mission.waypoints, key=lambda item: item.sequence)
        destination = next(
            (
                item
                for item in ordered
                if item.command == 16
                and distance_m(
                    item.latitude,
                    item.longitude,
                    mission.destination_latitude,
                    mission.destination_longitude,
                )
                <= 2.0
            ),
            None,
        )
        if self._settings.px4_sitl_plan_validation:
            return (
                self._next_px4_sitl_progress(mission, destination, ordered[-1]) if ordered else None
            )
        gripper = next((item for item in ordered if item.command == 211), None)
        returning = next(
            (
                item
                for item in ordered
                if gripper is not None
                and item.sequence > gripper.sequence
                and item.command == 16
                and distance_m(
                    item.latitude,
                    item.longitude,
                    mission.origin_latitude,
                    mission.origin_longitude,
                )
                <= self._settings.max_origin_deviation_m
            ),
            None,
        )
        landing = next(
            (
                item
                for item in reversed(ordered)
                if item.command == 21
                and distance_m(
                    item.latitude,
                    item.longitude,
                    mission.origin_latitude,
                    mission.origin_longitude,
                )
                <= self._settings.max_origin_deviation_m
            ),
            None,
        )
        if any(item is None for item in (destination, gripper, returning, landing)):
            return None

        assert destination is not None
        assert gripper is not None
        assert returning is not None
        assert landing is not None
        current_sequence = self._last_current_sequence
        delivery_evidence = gripper.sequence in self._reached_sequences or (
            current_sequence is not None and current_sequence > gripper.sequence
        )
        return_evidence = (
            current_sequence is not None and current_sequence >= returning.sequence
        ) or returning.sequence in self._reached_sequences
        at_origin = (
            self._latitude is not None
            and self._longitude is not None
            and distance_m(
                self._latitude,
                self._longitude,
                mission.origin_latitude,
                mission.origin_longitude,
            )
            <= self._settings.max_origin_deviation_m
        )
        evidence = (
            (
                MissionStatus.DESTINATION_REACHED,
                destination.sequence in self._reached_sequences,
                destination.sequence,
            ),
            (MissionStatus.DELIVERY_CONFIRMED, delivery_evidence, gripper.sequence),
            (MissionStatus.RETURNING, return_evidence, returning.sequence),
            (
                MissionStatus.COMPLETED,
                landing.sequence in self._reached_sequences and not self._armed and at_origin,
                landing.sequence,
            ),
        )
        mission_key = str(mission.id)
        reported = self._reported_progress.setdefault(mission_key, set())
        for status, confirmed, sequence in evidence:
            if status in reported:
                continue
            if not confirmed:
                return None
            reported.add(status)
            self._queue_progress_event(status, sequence, current_sequence)
            return status
        return None

    def _next_px4_sitl_progress(
        self, mission: AuthorizedMission, destination: MissionWaypoint | None, last: MissionWaypoint
    ) -> MissionStatus | None:
        if destination is None or last.command != 20:
            return None
        reported = self._reported_progress.setdefault(str(mission.id), set())
        returning = MissionStatus.RETURNING in reported
        at_destination = (
            self._last_current_sequence == destination.sequence
            and self._mode == "MISSION"
            and self._armed is True
            and self._latitude is not None
            and self._longitude is not None
            and self._message_is_fresh("GLOBAL_POSITION_INT")
            and distance_m(
                self._latitude, self._longitude, destination.latitude, destination.longitude
            )
            <= 2.0
        )
        self._saw_sitl_destination |= (
            at_destination or destination.sequence in self._reached_sequences
        )
        reached = self._saw_sitl_destination
        if not returning and reached and MissionStatus.DESTINATION_REACHED not in reported:
            status = MissionStatus.DESTINATION_REACHED
        elif (
            not returning
            and reached
            and (self._last_current_sequence == last.sequence or self._mode == "RTL")
        ):
            status = MissionStatus.RETURNING
        elif (
            returning
            and self._saw_sitl_airborne
            and self._armed is False
            and self._message_is_fresh("EXTENDED_SYS_STATE")
            and self._landed_state == self._required_mavutil().mavlink.MAV_LANDED_STATE_ON_GROUND
        ):
            status = MissionStatus.COMPLETED if reached else MissionStatus.ABORTED
        else:
            return None
        if status in reported:
            return None
        reported.add(status)
        return status

    def _queue_progress_event(
        self,
        status: MissionStatus,
        sequence: int,
        current_sequence: int | None,
    ) -> None:
        event_by_status = {
            MissionStatus.DESTINATION_REACHED: (
                "MAVLINK_DESTINATION_SEQUENCE_CONFIRMED",
                "INFO",
                "MISSION_ITEM_REACHED confirmou o waypoint canônico de destino.",
            ),
            MissionStatus.DELIVERY_CONFIRMED: (
                "MAVLINK_DELIVERY_MECHANISM_SEQUENCE_CONFIRMED",
                "WARNING",
                (
                    "A sequência MAV_CMD_DO_GRIPPER foi alcançada ou ultrapassada. "
                    "Isso confirma o comando do mecanismo, não comprova fisicamente o pacote."
                ),
            ),
            MissionStatus.RETURNING: (
                "MAVLINK_RETURN_SEQUENCE_STARTED",
                "INFO",
                "MISSION_CURRENT/ITEM_REACHED confirmou o início da sequência de retorno.",
            ),
            MissionStatus.COMPLETED: (
                "MAVLINK_LANDING_COMPLETION_CONFIRMED",
                "INFO",
                (
                    "LAND final foi alcançado, o veículo está desarmado e a posição está "
                    "próxima da origem."
                ),
            ),
        }
        event_type, severity, message = event_by_status[status]
        self._queue_event(
            event_type=event_type,
            severity=severity,
            message=message,
            metadata={
                "sequence": sequence,
                "current_sequence": current_sequence,
                "derived_status": status.value,
            },
        )

    async def request_rtl(self) -> None:
        self._require_live_heartbeat("RTL")
        if not self._settings.allow_flight_commands:
            raise UnsafeOperationError("ALLOW_FLIGHT_COMMANDS não foi habilitado.")
        if self._settings.autopilot_system.strip().upper() == "PX4":
            if self._passive_connection:
                raise UnsafeOperationError("Conexão de observação não pode enviar RTL.")
            await asyncio.to_thread(self._request_px4_rtl_sync)
            return
        await asyncio.to_thread(self._command_and_wait, "RTL")

    def _request_px4_rtl_sync(self) -> None:
        if not self._drain_messages():
            raise UnsafeOperationError("RTL bloqueado: fila de telemetria ainda não processada.")
        self._require_live_heartbeat("RTL")
        latitude = self._origin_latitude
        longitude = self._origin_longitude
        if not self._settings.px4_sitl_plan_validation and (
            self._armed is not True
            or not self._message_is_fresh("HOME_POSITION")
            or latitude is None
            or longitude is None
            or not -90 <= latitude <= 90
            or not -180 <= longitude <= 180
        ):
            raise UnsafeOperationError("RTL PX4 exige veículo armado e Home atual do autopiloto.")
        previous_heartbeat = self._last_heartbeat_monotonic
        self._command_and_wait("RTL")
        self._confirm_px4_mode("RTL", previous_heartbeat)

    def _confirm_px4_mode(self, mode: str, previous_heartbeat: float | None) -> None:
        connection = self._required_connection()
        deadline = time.monotonic() + self._settings.mission_command_timeout_seconds
        while time.monotonic() < deadline:
            self._send_gcs_heartbeat_if_due()
            message = connection.recv_match(
                blocking=True,
                timeout=min(0.5, max(0.01, deadline - time.monotonic())),
            )
            if message is None:
                continue
            self._ingest_message(message)
            if (
                message.get_type() == "HEARTBEAT"
                and self._last_heartbeat_monotonic is not None
                and previous_heartbeat is not None
                and self._last_heartbeat_monotonic > previous_heartbeat
                and (self._mode or "").strip().upper() == mode
            ):
                return
        raise VehicleTimeoutError(f"PX4 aceitou o comando, mas não confirmou o modo {mode}.")

    async def abort(self) -> None:
        raise UnsafeOperationError(
            "Abortamento real não envia flight termination. "
            "Use RTL quando seguro ou intervenção do operador."
        )

    async def close(self) -> None:
        async with self._connection_lock:
            await self._close_unlocked()
