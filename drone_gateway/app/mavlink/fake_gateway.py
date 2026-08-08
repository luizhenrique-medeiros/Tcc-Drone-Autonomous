from datetime import UTC, datetime

from app.core.config import Settings
from app.core.exceptions import MissionUploadError, UnsafeOperationError
from app.models import (
    AuthorizedMission,
    MissionStatus,
    OperationalSource,
    TelemetrySnapshot,
    UploadResult,
    VehicleEvent,
    VehicleHealth,
    VehiclePoll,
)


class FakeVehicleGateway:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._connected = False
        self._uploaded: dict[str, str] = {}
        self._active_mission_id: str | None = None
        self._progress_tick = 0

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
            flight_mode="STANDBY",
            armed=False,
            preflight_ok=True,
            rtl_configured=True,
            geofence_enabled=True,
            origin_latitude=self._settings.base_latitude,
            origin_longitude=self._settings.base_longitude,
        )

    async def drain_events(self) -> list[VehicleEvent]:
        return []

    async def upload_mission(self, mission: AuthorizedMission, mission_file: str) -> UploadResult:
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

    async def start_mission(self, mission: AuthorizedMission) -> None:
        if str(mission.id) not in self._uploaded:
            raise UnsafeOperationError("Missão não foi enviada antes do início.")
        if self._active_mission_id not in (None, str(mission.id)):
            raise UnsafeOperationError("Outra missão fake já está ativa.")
        self._active_mission_id = str(mission.id)
        self._progress_tick = 0

    async def synchronize_progress(
        self,
        mission: AuthorizedMission,
        last_reported_status: MissionStatus | None,
    ) -> None:
        del mission, last_reported_status

    async def poll_mission(self, mission: AuthorizedMission) -> VehiclePoll:
        if self._active_mission_id != str(mission.id):
            raise UnsafeOperationError("Missão não está ativa no veículo fake.")
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
        if self._active_mission_id is None:
            raise UnsafeOperationError("Nenhuma missão fake ativa para RTL.")
        self._progress_tick = 3

    async def abort(self) -> None:
        self._active_mission_id = None

    async def close(self) -> None:
        self._connected = False
