import asyncio
import logging
import math
import os
import time
from collections import deque
from datetime import UTC, datetime
from types import ModuleType
from typing import Any

from pydantic import ValidationError
from serial import SerialException

from app.core.config import MavlinkMode, Settings
from app.core.exceptions import (
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
    ConnectionState,
    MissionStatus,
    MissionVerificationResult,
    OperationalSource,
    TelemetrySnapshot,
    UploadResult,
    VehicleArmResult,
    VehicleEvent,
    VehicleHealth,
    VehiclePoll,
)

logger = logging.getLogger(__name__)

MISSION_PROGRESS_STATUSES = (
    MissionStatus.DESTINATION_REACHED,
    MissionStatus.DELIVERY_CONFIRMED,
    MissionStatus.RETURNING,
    MissionStatus.COMPLETED,
)


class PymavlinkVehicleGateway:
    """Thin pymavlink adapter with explicit, gated commands and no parameter writes."""

    _ARM_MAX_SEND_ATTEMPTS = 3
    _ARM_MAX_DRAIN_MESSAGES = 500

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
        self._rtl_configured: bool | None = None
        self._geofence_enabled: bool | None = None
        self._autopilot_version: str | None = None
        self._origin_latitude: float | None = None
        self._origin_longitude: float | None = None
        self._latitude: float | None = None
        self._longitude: float | None = None
        self._last_position_monotonic: float | None = None
        self._last_position_recorded_at: datetime | None = None
        self._relative_altitude_m = 0.0
        self._ground_speed_m_s = 0.0
        self._uploaded: dict[str, str] = {}
        self._last_current_sequence: int | None = None
        self._reached_sequences: set[int] = set()
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
            # receive-only.  This also suppresses otherwise harmless-looking MAVLink
            # requests and GCS heartbeats so the default cannot affect a live bus.
            self._passive_connection = passive or (
                self._settings.is_hardware_mode and not self._settings.real_hardware_acknowledged
            )
            self._reset_live_state()
            self._mavutil = self._load_mavutil()
            try:
                self._validate_serial_port_exists()
                self._connection = self._mavutil.mavlink_connection(
                    self._settings.effective_mavlink_connection,
                    baud=self._settings.mavlink_baud_rate,
                    autoreconnect=True,
                    source_system=self._settings.mavlink_source_system_id,
                    source_component=self._settings.mavlink_source_component_id,
                    dialect=self._settings.mavlink_dialect,
                )
                self._connection_state = ConnectionState.WAITING_HEARTBEAT
                heartbeat = await asyncio.to_thread(self._wait_for_target_heartbeat)
                if heartbeat is None:
                    raise VehicleTimeoutError(
                        "Conexão aberta, mas nenhum heartbeat ArduPilot válido chegou no timeout."
                    )
                self._ingest_message(heartbeat)
                self._connection_state = ConnectionState.CONNECTED
                if not self._passive_connection:
                    await asyncio.to_thread(self._request_initial_state)
                    await asyncio.to_thread(self._drain_messages, 100)
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
        self._rtl_configured = None
        self._geofence_enabled = None
        self._autopilot_version = None
        self._origin_latitude = None
        self._origin_longitude = None
        self._latitude = None
        self._longitude = None
        self._last_position_monotonic = None
        self._last_position_recorded_at = None
        self._relative_altitude_m = 0.0
        self._ground_speed_m_s = 0.0
        self._last_current_sequence = None
        self._reached_sequences.clear()

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
                f"Porta {endpoint} ocupada ou com acesso negado. Feche o Mission Planner "
                "para usar MAVLINK_MODE=direct, ou mantenha-o aberto e use "
                "MAVLINK_MODE=mission_planner_forward com forwarding UDP."
            )
        if isinstance(exc, PermissionError):
            return VehiclePortAccessError(f"Acesso negado ao abrir {endpoint}.")
        if self._is_serial_connection() and any(
            marker in message for marker in ("access is denied", "permission", "acesso negado")
        ):
            return VehiclePortBusyError(
                f"{endpoint} existe, mas está ocupada ou sem permissão; feche o concorrente "
                "ou use Mission Planner forwarding."
            )
        return VehicleConnectionError(f"Falha ao abrir {endpoint}: {exc}")

    def _wait_for_target_heartbeat(self) -> Any | None:
        connection = self._required_connection()
        mavutil = self._required_mavutil()
        deadline = time.monotonic() + self._settings.heartbeat_timeout_seconds
        invalid_autopilot = getattr(mavutil.mavlink, "MAV_AUTOPILOT_INVALID", 8)
        ardupilot_autopilot = getattr(mavutil.mavlink, "MAV_AUTOPILOT_ARDUPILOTMEGA", 3)
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
            if autopilot in {invalid_autopilot} or autopilot != ardupilot_autopilot:
                continue
            connection.target_system = source_system
            connection.target_component = source_component
            return heartbeat
        return None

    def _request_initial_state(self) -> None:
        if self._passive_connection:
            return
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
        self._request_autopilot_version()
        if not self._request_message_intervals():
            self._request_data_stream_fallback()
        for parameter in (b"FENCE_ENABLE", b"RTL_ALT"):
            connection.mav.param_request_read_send(target_system, target_component, parameter, -1)

    def _request_autopilot_version(self) -> None:
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

    def _drain_messages(self, maximum: int = 50) -> None:
        connection = self._required_connection()
        self._send_gcs_heartbeat_if_due()
        for _ in range(maximum):
            message = connection.recv_match(blocking=False)
            if message is None:
                break
            self._ingest_message(message)

    def _ingest_message(self, message: Any) -> None:
        mavutil = self._required_mavutil()
        message_type = message.get_type()
        if message_type == "BAD_DATA":
            return
        if not self._message_matches_target(message):
            return
        received_monotonic = time.monotonic()
        self._last_message_monotonic[message_type] = received_monotonic
        if message_type == "HEARTBEAT":
            self._last_heartbeat_monotonic = received_monotonic
            self._last_heartbeat_recorded_at = datetime.now(UTC)
            self._connection_state = ConnectionState.CONNECTED
            self._connection_error = None
            self._mode = mavutil.mode_string_v10(message)
            armed_flag = mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
            self._armed = bool(message.base_mode & armed_flag)
        elif message_type == "GPS_RAW_INT":
            self._gps_fix = int(message.fix_type)
            satellites = int(message.satellites_visible)
            self._satellites = satellites if 0 <= satellites <= 100 else None
        elif message_type == "SYS_STATUS":
            if int(message.battery_remaining) >= 0:
                self._battery_percent = float(message.battery_remaining)
            if int(message.voltage_battery) > 0:
                self._battery_voltage = float(message.voltage_battery) / 1000
            prearm_bit = getattr(mavutil.mavlink, "MAV_SYS_STATUS_PREARM_CHECK", 1 << 28)
            self._preflight_ok = bool(int(message.onboard_control_sensors_health) & prearm_bit)
            self._last_message_monotonic["BATTERY"] = received_monotonic
        elif message_type == "BATTERY_STATUS":
            battery_remaining = int(getattr(message, "battery_remaining", -1))
            updated = False
            if battery_remaining >= 0:
                self._battery_percent = float(battery_remaining)
                updated = True
            voltages = getattr(message, "voltages", ())
            valid_voltages = [int(value) for value in voltages if 0 < int(value) < 0xFFFF]
            if valid_voltages:
                self._battery_voltage = sum(valid_voltages) / 1000
                updated = True
            if updated:
                self._last_message_monotonic["BATTERY"] = received_monotonic
        elif message_type == "EKF_STATUS_REPORT":
            attitude = getattr(mavutil.mavlink, "EKF_ATTITUDE", 1)
            velocity = getattr(mavutil.mavlink, "EKF_VELOCITY_HORIZ", 2)
            position = getattr(mavutil.mavlink, "EKF_POS_HORIZ_REL", 8)
            required = attitude | velocity | position
            self._ekf_ok = int(message.flags) & required == required
        elif message_type == "HOME_POSITION":
            self._origin_latitude = float(message.latitude) / 10_000_000
            self._origin_longitude = float(message.longitude) / 10_000_000
        elif message_type == "GLOBAL_POSITION_INT":
            self._latitude = float(message.lat) / 10_000_000
            self._longitude = float(message.lon) / 10_000_000
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
            if parameter_id == "FENCE_ENABLE":
                self._geofence_enabled = float(message.param_value) >= 1
            elif parameter_id == "RTL_ALT":
                self._rtl_configured = float(message.param_value) > 0
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
        elif message_type == "MISSION_CURRENT":
            sequence = int(message.seq)
            if sequence != self._last_current_sequence:
                self._last_current_sequence = sequence
                metadata: dict[str, str | int | float | bool | None] = {"sequence": sequence}
                for field in ("mission_state", "mission_mode"):
                    value = getattr(message, field, None)
                    if value is not None:
                        metadata[field] = int(value)
                self._queue_event(
                    event_type="MAVLINK_MISSION_CURRENT",
                    severity="INFO",
                    message=f"ArduPilot informou waypoint atual {sequence}.",
                    metadata=metadata,
                )
        elif message_type == "MISSION_ITEM_REACHED":
            sequence = int(message.seq)
            self._reached_sequences.add(sequence)
            self._queue_event(
                event_type="MAVLINK_MISSION_ITEM_REACHED",
                severity="INFO",
                message=f"ArduPilot informou waypoint alcançado {sequence}.",
                metadata={"sequence": sequence},
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
        if heartbeat_age is None:
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
                f"{operation} bloqueado: heartbeat ArduPilot válido não está disponível."
            )

    def _message_is_fresh(self, *message_types: str, timeout: float | None = None) -> bool:
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

    async def read_health(self) -> VehicleHealth:
        if self._connection is not None:
            await asyncio.to_thread(self._drain_messages)
        self._refresh_connection_state()
        heartbeat_age = self._heartbeat_age_seconds()
        heartbeat = self._connection_state is ConnectionState.CONNECTED
        connected = self._connection is not None and heartbeat
        gps_fresh = self._message_is_fresh("GPS_RAW_INT")
        battery_fresh = self._message_is_fresh("BATTERY")
        ekf_fresh = self._message_is_fresh("EKF_STATUS_REPORT")
        status_fresh = self._message_is_fresh("SYS_STATUS")
        position_fresh = self._message_is_fresh("GLOBAL_POSITION_INT")
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
                rtl_configured=self._rtl_configured,
                geofence_enabled=self._geofence_enabled,
                origin_latitude=self._origin_latitude,
                origin_longitude=self._origin_longitude,
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
                mission_upload_enabled=self._settings.allow_mission_upload,
                flight_commands_enabled=self._settings.allow_flight_commands,
                mission_start_enabled=self._settings.allow_mission_start,
                vehicle_arm_enabled=self._settings.allow_vehicle_arm,
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
        if not self._settings.allow_flight_commands or not self._settings.allow_mission_start:
            raise UnsafeOperationError(
                "Armamento exige ALLOW_FLIGHT_COMMANDS e ALLOW_MISSION_START habilitados."
            )
        if self._passive_connection:
            raise UnsafeOperationError("Conexão receive-only não pode armar o veículo.")
        async with self._arm_command_lock:
            await asyncio.to_thread(self._prepare_arm_transaction)
            self._require_live_heartbeat("armamento")
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
        connection = self._required_connection()
        self._send_gcs_heartbeat_if_due()
        for _ in range(self._ARM_MAX_DRAIN_MESSAGES):
            message = connection.recv_match(blocking=False)
            if message is None:
                return
            self._ingest_message(message)
        raise UnsafeOperationError(
            "Armamento bloqueado: a fila MAVLink não estabilizou antes da transação."
        )

    def _arm_vehicle_sync(self) -> None:
        connection = self._required_connection()
        mavlink = self._required_mavutil().mavlink
        command = mavlink.MAV_CMD_COMPONENT_ARM_DISARM
        accepted = mavlink.MAV_RESULT_ACCEPTED
        first_heartbeat = self._last_heartbeat_monotonic
        transaction_deadline = time.monotonic() + self._settings.mission_command_timeout_seconds

        for attempt in range(self._ARM_MAX_SEND_ATTEMPTS):
            remaining = transaction_deadline - time.monotonic()
            if remaining <= 0:
                break
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
            except (AttributeError, OSError, TypeError, ValueError) as exc:
                raise VehicleConnectionError(
                    "Falha ao enviar o comando MAVLink normal de armamento."
                ) from exc

            ack_deadline = min(
                transaction_deadline,
                time.monotonic() + self._settings.mission_protocol_step_timeout_seconds,
            )
            result, armed_heartbeat_seen = self._receive_strict_arm_ack(
                command,
                first_heartbeat=first_heartbeat,
                deadline=ack_deadline,
            )
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
            waypoint.param4,
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
        deadline = time.monotonic() + (
            timeout or self._settings.mission_protocol_step_timeout_seconds
        )
        while time.monotonic() < deadline:
            self._send_gcs_heartbeat_if_due()
            message = connection.recv_match(
                type=message_types,
                blocking=True,
                timeout=max(0.1, deadline - time.monotonic()),
            )
            if message is None or not self._message_matches_mission_operation(message):
                continue
            if sequence is not None and int(getattr(message, "seq", -1)) != sequence:
                continue
            return message
        expected = ", ".join(message_types) if isinstance(message_types, list) else message_types
        raise VehicleTimeoutError(f"Timeout aguardando {expected} na verificação da missão.")

    def _verify_mission_sync(self, mission: AuthorizedMission) -> None:
        connection = self._required_connection()
        mavutil = self._required_mavutil()
        target_system = connection.target_system
        target_component = connection.target_component
        ordered = sorted(mission.waypoints, key=lambda item: item.sequence)
        count_message = None
        for attempt in range(self._settings.mission_protocol_retries + 1):
            connection.mav.mission_request_list_send(target_system, target_component)
            try:
                count_message = self._recv_mission_message("MISSION_COUNT")
                break
            except VehicleTimeoutError:
                if attempt >= self._settings.mission_protocol_retries:
                    raise
        if count_message is None:  # pragma: no cover - guarded by the retry loop
            raise VehicleTimeoutError("MISSION_COUNT não chegou durante a verificação.")
        if int(count_message.count) != len(ordered):
            raise MissionUploadError(
                f"Veículo armazenou {count_message.count} waypoints; esperado {len(ordered)}."
            )
        for sequence, expected in enumerate(ordered):
            actual = None
            for attempt in range(self._settings.mission_protocol_retries + 1):
                connection.mav.mission_request_int_send(target_system, target_component, sequence)
                try:
                    actual = self._recv_mission_message(
                        ["MISSION_ITEM_INT", "MISSION_ITEM"], sequence=sequence
                    )
                    break
                except VehicleTimeoutError:
                    if attempt >= self._settings.mission_protocol_retries:
                        raise
            if actual is None:  # pragma: no cover - guarded by the retry loop
                raise VehicleTimeoutError(f"Waypoint {sequence} não chegou durante a verificação.")
            self._verify_downloaded_waypoint(actual, expected)
        connection.mav.mission_ack_send(
            target_system,
            target_component,
            mavutil.mavlink.MAV_MISSION_ACCEPTED,
        )

    def _verify_downloaded_waypoint(self, actual: Any, expected: Any) -> None:
        message_type = actual.get_type()
        actual_frame = int(actual.frame)
        expected_frame = (
            self._int_frame(expected.frame)
            if message_type == "MISSION_ITEM_INT"
            else expected.frame
        )
        nonpositional_command = expected.command == 211
        accepted_frames = {expected_frame}
        if nonpositional_command:
            accepted_frames.add(getattr(self._required_mavutil().mavlink, "MAV_FRAME_MISSION", 2))
        if actual_frame not in accepted_frames:
            raise MissionUploadError(
                f"Frame relido diverge no waypoint {expected.sequence}: {actual_frame}."
            )
        for field in ("command", "current", "autocontinue"):
            if int(getattr(actual, field)) != int(getattr(expected, field)):
                raise MissionUploadError(
                    f"Campo {field} relido diverge no waypoint {expected.sequence}."
                )
        for field in ("param1", "param2", "param3", "param4"):
            if not math.isclose(
                float(getattr(actual, field)),
                float(getattr(expected, field)),
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
        if not math.isclose(latitude, expected.latitude, abs_tol=1e-6) or not math.isclose(
            longitude, expected.longitude, abs_tol=1e-6
        ):
            raise MissionUploadError(
                f"Coordenadas relidas divergem no waypoint {expected.sequence}."
            )
        if not math.isclose(float(actual.z), expected.altitude_m, abs_tol=0.05):
            raise MissionUploadError(f"Altitude relida diverge no waypoint {expected.sequence}.")

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
        await asyncio.to_thread(self._command_and_wait, "MISSION_START")

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
        command = command_by_name[command_name]
        first_parameter = 1 if command_name == "CONTINUE" else 0
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
            first_parameter,
            0,
            0,
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

    async def poll_mission(self, mission: AuthorizedMission) -> VehiclePoll:
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
        await asyncio.to_thread(self._command_and_wait, "RTL")

    async def abort(self) -> None:
        raise UnsafeOperationError(
            "Abortamento real não envia flight termination. "
            "Use RTL quando seguro ou intervenção do operador."
        )

    async def close(self) -> None:
        async with self._connection_lock:
            await self._close_unlocked()
