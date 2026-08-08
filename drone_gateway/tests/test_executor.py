from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.core.config import MavlinkMode, Settings
from app.core.exceptions import BackendContractError, BackendUnavailableError
from app.mavlink.fake_gateway import FakeVehicleGateway
from app.mission_planner.waypoint import mission_sha256, render_qgc_wpl
from app.missions.executor import MissionExecutor
from app.models import (
    AuthorizedMission,
    ClaimResponse,
    GatewayCommand,
    GatewayCommandStatus,
    HeartbeatResponse,
    HeartbeatVehicle,
    MissionStatus,
    MissionWaypoint,
    TelemetrySnapshot,
    VehicleHealth,
)


class RecordingBackend:
    def __init__(self, claim: ClaimResponse) -> None:
        self.claim_response = claim
        self.claim_count = 0
        self.upload_statuses: list[MissionStatus] = []
        self.statuses: list[MissionStatus] = []
        self.status_details: list[tuple[MissionStatus, str | None]] = []
        self.telemetry: list[TelemetrySnapshot] = []
        self.events: list[str] = []

    async def heartbeat(self, health: VehicleHealth) -> HeartbeatResponse:
        vehicle_id = self.claim_response.mission.vehicle_id
        assert vehicle_id is not None
        failures: list[str] = []
        if not health.connected or not health.heartbeat:
            failures.append("NO_HEARTBEAT")
        if health.armed:
            failures.append("VEHICLE_ALREADY_ARMED")
        return HeartbeatResponse(
            vehicle=HeartbeatVehicle(
                id=vehicle_id,
                identifier="academic-vehicle-01",
                gateway_id="dev-gateway-01",
            ),
            authorization_eligible=not failures,
            failures=failures,
        )

    async def authorized_missions(self) -> list[AuthorizedMission]:
        if self.claim_count != 0:
            return []
        return [self.claim_response.mission.model_copy(update={"status": MissionStatus.AUTHORIZED})]

    async def claim(self, mission_id: UUID) -> ClaimResponse:
        assert mission_id == self.claim_response.mission.id
        self.claim_count += 1
        return self.claim_response

    async def pending_commands(self, limit: int = 20) -> list[GatewayCommand]:
        return []

    async def acknowledge_command(
        self,
        command_id: UUID,
        status: GatewayCommandStatus,
        *,
        detail: str | None = None,
        event_id: UUID | None = None,
    ) -> UUID:
        return event_id or uuid4()

    async def report_upload(
        self,
        mission_id: UUID,
        status: MissionStatus,
        *,
        detail: str | None = None,
        event_id: UUID | None = None,
    ) -> UUID:
        self.upload_statuses.append(status)
        return event_id or uuid4()

    async def report_status(
        self,
        mission_id: UUID,
        status: MissionStatus,
        *,
        detail: str | None = None,
        event_id: UUID | None = None,
    ) -> UUID:
        self.statuses.append(status)
        self.status_details.append((status, detail))
        return event_id or uuid4()

    async def report_telemetry(
        self,
        mission_id: UUID,
        vehicle_id: UUID,
        telemetry: TelemetrySnapshot,
        *,
        event_id: UUID | None = None,
    ) -> UUID:
        self.telemetry.append(telemetry)
        return event_id or uuid4()

    async def report_event(
        self,
        mission_id: UUID,
        *,
        event_type: str,
        severity: str,
        message: str,
        metadata: dict[str, str | int | float | bool | None] | None = None,
        occurred_at: datetime | None = None,
        event_id: UUID | None = None,
    ) -> UUID:
        self.events.append(event_type)
        return event_id or uuid4()


class ControllableFakeGateway(FakeVehicleGateway):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.armed = False
        self.mode = "STANDBY"
        self.link_connected = True
        self.start_count = 0

    async def read_health(self) -> VehicleHealth:
        health = await super().read_health()
        return health.model_copy(
            update={
                "connected": self.link_connected,
                "heartbeat": self.link_connected,
                "armed": self.armed,
                "flight_mode": self.mode,
            }
        )

    async def start_mission(self, mission: AuthorizedMission) -> None:
        self.start_count += 1
        await super().start_mission(mission)


class FlakyExecutingBackend(RecordingBackend):
    def __init__(self, claim: ClaimResponse) -> None:
        super().__init__(claim)
        self.executing_attempt_ids: list[UUID | None] = []
        self.fail_executing_once = True

    async def report_status(
        self,
        mission_id: UUID,
        status: MissionStatus,
        *,
        detail: str | None = None,
        event_id: UUID | None = None,
    ) -> UUID:
        if status is MissionStatus.EXECUTING:
            self.executing_attempt_ids.append(event_id)
            if self.fail_executing_once:
                self.fail_executing_once = False
                raise BackendUnavailableError("outage after MISSION_START")
        return await super().report_status(
            mission_id,
            status,
            detail=detail,
            event_id=event_id,
        )


class FlakyDestinationBackend(RecordingBackend):
    def __init__(self, claim: ClaimResponse) -> None:
        super().__init__(claim)
        self.destination_attempt_ids: list[UUID | None] = []
        self.fail_destination_once = True

    async def report_status(
        self,
        mission_id: UUID,
        status: MissionStatus,
        *,
        detail: str | None = None,
        event_id: UUID | None = None,
    ) -> UUID:
        if status is MissionStatus.DESTINATION_REACHED:
            self.destination_attempt_ids.append(event_id)
            if self.fail_destination_once:
                self.fail_destination_once = False
                raise BackendUnavailableError("destination report outage")
        return await super().report_status(
            mission_id,
            status,
            detail=detail,
            event_id=event_id,
        )


class AmbiguousClaimBackend(RecordingBackend):
    def __init__(self, claim: ClaimResponse) -> None:
        super().__init__(claim)
        self.claim_attempts = 0

    async def claim(self, mission_id: UUID) -> ClaimResponse:
        assert mission_id == self.claim_response.mission.id
        self.claim_attempts += 1
        if self.claim_attempts == 1:
            self.claim_count += 1
            raise BackendUnavailableError("claim may have committed")
        return self.claim_response


class MismatchedHeartbeatBackend(RecordingBackend):
    async def heartbeat(self, health: VehicleHealth) -> HeartbeatResponse:
        return HeartbeatResponse(
            vehicle=HeartbeatVehicle(
                id=uuid4(),
                identifier="academic-vehicle-01",
                gateway_id="dev-gateway-01",
            ),
            authorization_eligible=health.connected,
        )


class WrongIdentityHeartbeatBackend(RecordingBackend):
    async def heartbeat(self, health: VehicleHealth) -> HeartbeatResponse:
        vehicle_id = self.claim_response.mission.vehicle_id
        assert vehicle_id is not None
        return HeartbeatResponse(
            vehicle=HeartbeatVehicle(
                id=vehicle_id,
                identifier="outro-veiculo",
                gateway_id="outro-gateway",
            ),
            authorization_eligible=health.connected,
        )


class StartRejectedHeartbeatBackend(RecordingBackend):
    async def heartbeat(self, health: VehicleHealth) -> HeartbeatResponse:
        response = await super().heartbeat(health)
        if not health.armed:
            return response
        return response.model_copy(
            update={
                "authorization_eligible": False,
                "failures": ["VEHICLE_ALREADY_ARMED", "BACKEND_POLICY_BLOCK"],
            }
        )


def build_claim() -> ClaimResponse:
    waypoints = [
        MissionWaypoint(
            sequence=0,
            current=1,
            command=16,
            latitude=-23.1175,
            longitude=-46.5502,
            altitude_m=0,
            label="Origem",
        ),
        MissionWaypoint(
            sequence=1,
            command=22,
            latitude=-23.1175,
            longitude=-46.5502,
            altitude_m=10,
            label="Decolagem",
        ),
        MissionWaypoint(
            sequence=2,
            command=16,
            latitude=-23.118,
            longitude=-46.551,
            altitude_m=10,
            label="Destino",
        ),
        MissionWaypoint(
            sequence=3,
            command=19,
            param1=5,
            latitude=-23.118,
            longitude=-46.551,
            altitude_m=10,
            label="Espera para entrega",
        ),
        MissionWaypoint(
            sequence=4,
            command=211,
            latitude=-23.118,
            longitude=-46.551,
            altitude_m=10,
            label="Entrega",
        ),
        MissionWaypoint(
            sequence=5,
            command=16,
            latitude=-23.1175,
            longitude=-46.5502,
            altitude_m=10,
            label="Retorno",
        ),
        MissionWaypoint(
            sequence=6,
            command=21,
            latitude=-23.1175,
            longitude=-46.5502,
            altitude_m=0,
            label="Pouso",
        ),
    ]
    content = render_qgc_wpl(waypoints)
    mission = AuthorizedMission(
        id=uuid4(),
        order_id=uuid4(),
        vehicle_id=uuid4(),
        status=MissionStatus.UPLOADING,
        origin_latitude=-23.1175,
        origin_longitude=-46.5502,
        destination_latitude=-23.118,
        destination_longitude=-46.551,
        takeoff_altitude_m=10,
        estimated_distance_m=100,
        mission_sha256=mission_sha256(content),
        version=1,
        waypoints=waypoints,
    )
    return ClaimResponse(
        mission=mission,
        mission_file=content,
        authorization_id=uuid4(),
        authorization_expires_at=datetime.now(UTC) + timedelta(minutes=2),
    )


@pytest.mark.asyncio
async def test_simulation_runs_one_claim_through_return_and_completion(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, gateway_journal_path=tmp_path / "executor-journal.json")
    claim = build_claim()
    backend = RecordingBackend(claim)
    vehicle = FakeVehicleGateway(settings)
    await vehicle.connect()
    current_time = [datetime.now(UTC)]
    executor = MissionExecutor(settings, backend, vehicle, now=lambda: current_time[0])

    for _ in range(6):
        await executor.run_cycle()
        current_time[0] += timedelta(seconds=settings.telemetry_persist_interval_seconds)

    assert backend.claim_count == 1
    assert backend.upload_statuses == [MissionStatus.UPLOADING, MissionStatus.UPLOADED]
    assert backend.statuses == [
        MissionStatus.EXECUTING,
        MissionStatus.DESTINATION_REACHED,
        MissionStatus.DELIVERY_CONFIRMED,
        MissionStatus.RETURNING,
        MissionStatus.COMPLETED,
    ]
    assert len(backend.telemetry) == 5
    assert executor.active_mission_id is None
    delivery_detail = next(
        detail
        for status, detail in backend.status_details
        if status is MissionStatus.DELIVERY_CONFIRMED
    )
    assert delivery_detail is not None
    assert "não comprova fisicamente o pacote" in delivery_detail


@pytest.mark.asyncio
async def test_progress_journal_ignores_duplicate_after_executor_restart(tmp_path: Path) -> None:
    journal_path = tmp_path / "progress.json"
    settings = Settings(_env_file=None, gateway_journal_path=journal_path)
    claim = build_claim()
    backend = RecordingBackend(claim)
    vehicle = FakeVehicleGateway(settings)
    await vehicle.connect()
    executor = MissionExecutor(settings, backend, vehicle)

    await executor.run_cycle()
    await executor.run_cycle()
    assert backend.statuses == [
        MissionStatus.EXECUTING,
        MissionStatus.DESTINATION_REACHED,
    ]

    vehicle._progress_tick = 1
    restored = MissionExecutor(settings, backend, vehicle)
    await restored.run_cycle()
    assert backend.statuses == [
        MissionStatus.EXECUTING,
        MissionStatus.DESTINATION_REACHED,
    ]

    await restored.run_cycle()
    assert backend.statuses == [
        MissionStatus.EXECUTING,
        MissionStatus.DESTINATION_REACHED,
        MissionStatus.DELIVERY_CONFIRMED,
    ]


@pytest.mark.asyncio
async def test_progress_outbox_retries_same_event_id_after_restart(tmp_path: Path) -> None:
    journal_path = tmp_path / "progress-outbox.json"
    settings = Settings(_env_file=None, gateway_journal_path=journal_path)
    claim = build_claim()
    backend = FlakyDestinationBackend(claim)
    vehicle = FakeVehicleGateway(settings)
    await vehicle.connect()
    executor = MissionExecutor(settings, backend, vehicle)
    await executor.run_cycle()

    with pytest.raises(BackendUnavailableError, match="destination report outage"):
        await executor.run_cycle()

    restored = MissionExecutor(settings, backend, vehicle)
    await restored.run_cycle()

    assert len(backend.destination_attempt_ids) == 2
    assert backend.destination_attempt_ids[0] == backend.destination_attempt_ids[1]
    assert backend.statuses == [
        MissionStatus.EXECUTING,
        MissionStatus.DESTINATION_REACHED,
        MissionStatus.DELIVERY_CONFIRMED,
    ]


@pytest.mark.asyncio
async def test_executor_only_claims_mission_bound_to_heartbeat_vehicle(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, gateway_journal_path=tmp_path / "binding.json")
    claim = build_claim()
    backend = MismatchedHeartbeatBackend(claim)
    vehicle = FakeVehicleGateway(settings)
    await vehicle.connect()

    await MissionExecutor(settings, backend, vehicle).run_cycle()

    assert backend.claim_count == 0
    assert backend.upload_statuses == []


@pytest.mark.asyncio
async def test_executor_rejects_heartbeat_identity_mismatch(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, gateway_journal_path=tmp_path / "identity.json")
    claim = build_claim()
    backend = WrongIdentityHeartbeatBackend(claim)
    vehicle = FakeVehicleGateway(settings)
    await vehicle.connect()

    with pytest.raises(BackendContractError, match="identidade"):
        await MissionExecutor(settings, backend, vehicle).run_cycle()

    assert backend.claim_count == 0


@pytest.mark.asyncio
async def test_restart_retries_status_with_same_id_without_repeating_start(tmp_path: Path) -> None:
    journal_path = tmp_path / "start-outbox.json"
    settings = Settings(
        _env_file=None,
        mavlink_mode=MavlinkMode.SITL,
        allow_mission_start=True,
        gateway_journal_path=journal_path,
    )
    claim = build_claim()
    backend = FlakyExecutingBackend(claim)
    vehicle = ControllableFakeGateway(settings)
    await vehicle.connect()
    executor = MissionExecutor(settings, backend, vehicle)
    await executor.run_cycle()
    vehicle.armed = True
    vehicle.mode = "AUTO"

    with pytest.raises(BackendUnavailableError, match="outage"):
        await executor.run_cycle()

    assert vehicle.start_count == 1
    assert journal_path.exists()

    restored = MissionExecutor(settings, backend, vehicle)
    await restored.run_cycle()

    assert vehicle.start_count == 1
    assert backend.statuses == [MissionStatus.EXECUTING]
    assert len(backend.executing_attempt_ids) == 2
    assert backend.executing_attempt_ids[0] == backend.executing_attempt_ids[1]


@pytest.mark.asyncio
async def test_restart_retries_ambiguous_claim_even_when_offer_disappears(tmp_path: Path) -> None:
    journal_path = tmp_path / "claim-intent.json"
    settings = Settings(_env_file=None, gateway_journal_path=journal_path)
    claim = build_claim()
    backend = AmbiguousClaimBackend(claim)
    vehicle = FakeVehicleGateway(settings)
    await vehicle.connect()

    with pytest.raises(BackendUnavailableError, match="may have committed"):
        await MissionExecutor(settings, backend, vehicle).run_cycle()

    assert journal_path.exists()
    assert await backend.authorized_missions() == []

    restored = MissionExecutor(settings, backend, vehicle)
    await restored.run_cycle()

    assert backend.claim_attempts == 2
    assert backend.upload_statuses == [MissionStatus.UPLOADING, MissionStatus.UPLOADED]
    assert restored.active_mission_id == claim.mission.id


@pytest.mark.asyncio
async def test_authorization_is_revalidated_before_start(tmp_path: Path) -> None:
    current_time = datetime.now(UTC)
    claim = build_claim()
    claim = claim.model_copy(
        update={"authorization_expires_at": current_time + timedelta(seconds=30)}
    )
    settings = Settings(
        _env_file=None,
        mavlink_mode=MavlinkMode.SITL,
        allow_mission_start=True,
        gateway_journal_path=tmp_path / "expiry.json",
    )
    backend = RecordingBackend(claim)
    vehicle = ControllableFakeGateway(settings)
    await vehicle.connect()
    clock = [current_time]
    executor = MissionExecutor(settings, backend, vehicle, now=lambda: clock[0])
    await executor.run_cycle()
    vehicle.armed = True
    vehicle.mode = "AUTO"
    clock[0] = current_time + timedelta(minutes=1)

    await executor.run_cycle()

    assert vehicle.start_count == 0
    assert backend.statuses == [MissionStatus.FAILED]
    assert executor.active_mission_id is None


@pytest.mark.asyncio
async def test_backend_health_failure_is_revalidated_before_start(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        mavlink_mode=MavlinkMode.SITL,
        allow_mission_start=True,
        gateway_journal_path=tmp_path / "backend-policy.json",
    )
    claim = build_claim()
    backend = StartRejectedHeartbeatBackend(claim)
    vehicle = ControllableFakeGateway(settings)
    await vehicle.connect()
    executor = MissionExecutor(settings, backend, vehicle)
    await executor.run_cycle()
    vehicle.armed = True
    vehicle.mode = "AUTO"

    await executor.run_cycle()

    assert vehicle.start_count == 0
    assert backend.statuses == [MissionStatus.FAILED]
    assert executor.active_mission_id is None


@pytest.mark.asyncio
async def test_link_loss_keeps_active_mission_and_does_not_fabricate_telemetry(
    tmp_path: Path,
) -> None:
    settings = Settings(
        _env_file=None,
        mavlink_mode=MavlinkMode.SITL,
        allow_mission_start=True,
        gateway_journal_path=tmp_path / "link-loss.json",
    )
    claim = build_claim()
    backend = RecordingBackend(claim)
    vehicle = ControllableFakeGateway(settings)
    await vehicle.connect()
    executor = MissionExecutor(settings, backend, vehicle)
    await executor.run_cycle()
    vehicle.armed = True
    vehicle.mode = "AUTO"
    await executor.run_cycle()
    telemetry_before_loss = len(backend.telemetry)
    vehicle.link_connected = False

    await executor.run_cycle()

    assert len(backend.telemetry) == telemetry_before_loss
    assert "VEHICLE_LINK_LOST" in backend.events
    assert executor.active_mission_id == claim.mission.id
