from datetime import UTC, datetime

from app.core.config import Settings
from app.core.exceptions import MissionUploadError, UnsafeOperationError, VehicleTimeoutError
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


class FakeVehicleGateway:
    """In-memory simulator/test double; it never represents hardware evidence."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._connected = False
        self._uploaded: dict[str, str] = {}
        self._active_mission_id: str | None = None
        self._mission_paused = False
        self._progress_tick = 0
        self._armed = False
        self._flight_mode = "STABILIZE"

    @property
    def connection_state(self) -> ConnectionState:
        return ConnectionState.CONNECTED if self._connected else ConnectionState.DISCONNECTED

    @property
    def connection_error(self) -> str | None:
        return None

    def mark_reconnecting(self) -> None:
        self._connected = False

    async def connect(self) -> None:
        self._connected = True

    async def read_health(self) -> VehicleHealth:
        return VehicleHealth(
            source=OperationalSource.SIMULATION,
            autopilot_version="FAKE-SIMULATION",
            connected=self._connected,
            heartbeat=self._connected,
            gps_fix_type=3,
            satellites=max(14, self._settings.min_gps_satellites),
            ekf_ok=True,
            battery_percent=88,
            battery_voltage=22.6,
            flight_mode=self._flight_mode,
            armed=self._armed,
            preflight_ok=True,
            rtl_configured=True,
            geofence_enabled=True,
            origin_latitude=self._settings.base_latitude,
            origin_longitude=self._settings.base_longitude,
            connection_state=self.connection_state,
            connection_mode=self._settings.mavlink_mode.value,
            connection_topology=self._settings.connection_topology,
            connection_endpoint=self._settings.sanitized_connection,
            serial_port=None,
            connection_baud=None,
            mission_upload_enabled=self._settings.allow_mission_upload,
            flight_commands_enabled=self._settings.allow_flight_commands,
            mission_start_enabled=self._settings.allow_mission_start,
            vehicle_arm_enabled=self._settings.allow_vehicle_arm,
        )

    async def drain_events(self) -> list[VehicleEvent]:
        return []

    async def upload_mission(self, mission: AuthorizedMission, mission_file: str) -> UploadResult:
        del mission_file
        if not self._settings.allow_mission_upload:
            raise UnsafeOperationError("ALLOW_MISSION_UPLOAD não foi habilitado.")
        if not self._connected:
            raise MissionUploadError("Fake vehicle is disconnected.")
        key = str(mission.id)
        previous_hash = self._uploaded.get(key)
        if previous_hash is not None and previous_hash != mission.mission_sha256:
            raise MissionUploadError("A mesma missão foi reenviada com hash diferente.")
        self._uploaded[key] = mission.mission_sha256
        return UploadResult(
            item_count=len(mission.waypoints),
            acknowledged=True,
            detail="Upload fake confirmado de forma idempotente.",
        )

    async def verify_mission(self, mission: AuthorizedMission) -> MissionVerificationResult:
        if self._uploaded.get(str(mission.id)) != mission.mission_sha256:
            raise MissionUploadError("Missão fake não está carregada com o hash esperado.")
        return MissionVerificationResult(
            item_count=len(mission.waypoints),
            verified=True,
            detail="Conteúdo fake relido e verificado.",
        )

    async def arm_vehicle(self) -> VehicleArmResult:
        if not self._settings.allow_vehicle_arm:
            raise UnsafeOperationError("ALLOW_VEHICLE_ARM não foi habilitado.")
        if not self._settings.allow_flight_commands or not self._settings.allow_mission_start:
            raise UnsafeOperationError(
                "Armamento fake exige ALLOW_FLIGHT_COMMANDS e ALLOW_MISSION_START habilitados."
            )
        if not self._connected:
            raise VehicleTimeoutError("Heartbeat fake não está válido.")
        if self._flight_mode != "STABILIZE":
            raise UnsafeOperationError("Armamento exige modo STABILIZE.")
        if self._armed:
            return VehicleArmResult(
                command_sent=False,
                command_acknowledged=False,
                armed_heartbeat_confirmed=True,
                external_state_reconciled=True,
            )
        self._armed = True
        return VehicleArmResult(
            command_sent=True,
            command_acknowledged=True,
            armed_heartbeat_confirmed=True,
            external_state_reconciled=False,
        )

    async def start_mission(self, mission: AuthorizedMission) -> None:
        if not self._settings.allow_flight_commands or not self._settings.allow_mission_start:
            raise UnsafeOperationError(
                "ALLOW_FLIGHT_COMMANDS e ALLOW_MISSION_START devem estar habilitados."
            )
        if str(mission.id) not in self._uploaded:
            raise UnsafeOperationError("Missão não foi enviada antes do início.")
        if self._active_mission_id not in (None, str(mission.id)):
            raise UnsafeOperationError("Outra missão fake já está ativa.")
        self._active_mission_id = str(mission.id)
        self._mission_paused = False
        self._progress_tick = 0

    async def pause_mission(self) -> None:
        if not self._settings.allow_flight_commands:
            raise UnsafeOperationError("ALLOW_FLIGHT_COMMANDS não foi habilitado.")
        if not self._connected:
            raise VehicleTimeoutError("Heartbeat fake não está válido.")
        if self._active_mission_id is None:
            raise UnsafeOperationError("Nenhuma missão fake ativa para pausar.")
        self._mission_paused = True

    async def continue_mission(self) -> None:
        if not self._settings.allow_flight_commands:
            raise UnsafeOperationError("ALLOW_FLIGHT_COMMANDS não foi habilitado.")
        if not self._connected:
            raise VehicleTimeoutError("Heartbeat fake não está válido.")
        if self._active_mission_id is None or not self._mission_paused:
            raise UnsafeOperationError("Nenhuma missão fake pausada para continuar.")
        self._mission_paused = False

    async def synchronize_progress(
        self,
        mission: AuthorizedMission,
        last_reported_status: MissionStatus | None,
    ) -> None:
        del mission, last_reported_status

    async def poll_mission(self, mission: AuthorizedMission) -> VehiclePoll:
        if self._active_mission_id != str(mission.id):
            raise UnsafeOperationError("Missão não está ativa no veículo fake.")
        if self._mission_paused:
            raise UnsafeOperationError("Missão fake está pausada.")
        self._progress_tick += 1
        fraction = min(self._progress_tick / 5, 1)
        returning = self._progress_tick >= 4
        if returning:
            route_fraction = max(0, 1 - (self._progress_tick - 3) / 2)
        else:
            route_fraction = min(fraction * 1.5, 1)
        latitude = (
            mission.origin_latitude
            + (mission.destination_latitude - mission.origin_latitude) * route_fraction
        )
        longitude = (
            mission.origin_longitude
            + (mission.destination_longitude - mission.origin_longitude) * route_fraction
        )
        status_by_tick = {
            2: MissionStatus.DESTINATION_REACHED,
            3: MissionStatus.DELIVERY_CONFIRMED,
            4: MissionStatus.RETURNING,
            5: MissionStatus.COMPLETED,
        }
        status = status_by_tick.get(self._progress_tick)
        if status is MissionStatus.COMPLETED:
            self._active_mission_id = None
        return VehiclePoll(
            telemetry=TelemetrySnapshot(
                source=OperationalSource.SIMULATION,
                latitude=latitude,
                longitude=longitude,
                relative_altitude_m=0
                if status is MissionStatus.COMPLETED
                else mission.takeoff_altitude_m,
                ground_speed_m_s=0 if status is MissionStatus.COMPLETED else 5,
                battery_percent=max(60, 88 - self._progress_tick * 4),
                gps_fix_type=3,
                satellites=14,
                flight_mode="LAND" if status is MissionStatus.COMPLETED else "AUTO",
                armed=status is not MissionStatus.COMPLETED,
                recorded_at=datetime.now(UTC),
            ),
            suggested_status=status,
        )

    async def request_rtl(self) -> None:
        if not self._settings.allow_flight_commands:
            raise UnsafeOperationError("ALLOW_FLIGHT_COMMANDS não foi habilitado.")
        if not self._connected:
            raise VehicleTimeoutError("Heartbeat fake não está válido.")
        if self._active_mission_id is None:
            raise UnsafeOperationError("Nenhuma missão fake ativa para RTL.")
        self._progress_tick = 3

    async def abort(self) -> None:
        if not self._settings.allow_flight_commands:
            raise UnsafeOperationError("ALLOW_FLIGHT_COMMANDS não foi habilitado.")
        self._active_mission_id = None
        self._mission_paused = False

    async def close(self) -> None:
        self._connected = False
