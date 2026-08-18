from typing import Protocol

from app.models import (
    AuthorizedMission,
    ConnectionState,
    MissionStatus,
    MissionVerificationResult,
    UploadResult,
    VehicleEvent,
    VehicleHealth,
    VehiclePoll,
)


class VehicleGateway(Protocol):
    @property
    def connection_state(self) -> ConnectionState: ...

    @property
    def connection_error(self) -> str | None: ...

    def mark_reconnecting(self) -> None: ...

    async def connect(self) -> None: ...

    async def read_health(self) -> VehicleHealth: ...

    async def drain_events(self) -> list[VehicleEvent]: ...

    async def upload_mission(
        self, mission: AuthorizedMission, mission_file: str
    ) -> UploadResult: ...

    async def verify_mission(self, mission: AuthorizedMission) -> MissionVerificationResult: ...

    async def start_mission(self, mission: AuthorizedMission) -> None: ...

    async def pause_mission(self) -> None: ...

    async def continue_mission(self) -> None: ...

    async def synchronize_progress(
        self,
        mission: AuthorizedMission,
        last_reported_status: MissionStatus | None,
    ) -> None: ...

    async def poll_mission(self, mission: AuthorizedMission) -> VehiclePoll: ...

    async def request_rtl(self) -> None: ...

    async def abort(self) -> None: ...

    async def close(self) -> None: ...
