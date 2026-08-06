from typing import Protocol

from app.models import (
    AuthorizedMission,
    MissionStatus,
    UploadResult,
    VehicleEvent,
    VehicleHealth,
    VehiclePoll,
)


class VehicleGateway(Protocol):
    async def connect(self) -> None: ...

    async def read_health(self) -> VehicleHealth: ...

    async def drain_events(self) -> list[VehicleEvent]: ...

    async def upload_mission(
        self, mission: AuthorizedMission, mission_file: str
    ) -> UploadResult: ...

    async def start_mission(self, mission: AuthorizedMission) -> None: ...

    async def synchronize_progress(
        self,
        mission: AuthorizedMission,
        last_reported_status: MissionStatus | None,
    ) -> None: ...

    async def poll_mission(self, mission: AuthorizedMission) -> VehiclePoll: ...

    async def request_rtl(self) -> None: ...

    async def abort(self) -> None: ...

    async def close(self) -> None: ...
