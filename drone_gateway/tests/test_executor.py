from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.core.config import MavlinkMode, Settings
from app.core.exceptions import BackendContractError, BackendUnavailableError, VehicleTimeoutError
from app.mavlink.fake_gateway import FakeVehicleGateway
from app.mission_planner.waypoint import mission_sha256, render_qgc_wpl
from app.missions.executor import ActivePhase, MissionExecutor
from app.models import (
    AuthorizedMission,
    ClaimResponse,
    GatewayCommand,
    GatewayCommandStatus,
    GatewayCommandType,
    HeartbeatResponse,
    HeartbeatVehicle,
    MissionStatus,
    MissionWaypoint,
    OperationalSource,
    TelemetrySnapshot,
    VehicleArmResult,
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
        self.commands: list[GatewayCommand] = []
        self.command_acks: list[tuple[UUID, GatewayCommandStatus, str | None]] = []

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
        return self.commands[:limit]

    def queue_command(
        self,
        command: GatewayCommandType,
        *,
        requested_at: datetime | None = None,
    ) -> GatewayCommand:
        queued = GatewayCommand(
            id=uuid4(),
            mission_id=self.claim_response.mission.id,
            command=command,
            status=GatewayCommandStatus.PENDING,
            requested_at=requested_at or datetime.now(UTC),
        )
        self.commands.append(queued)
        return queued

    async def acknowledge_command(
        self,
        command_id: UUID,
        status: GatewayCommandStatus,
        *,
        detail: str | None = None,
        event_id: UUID | None = None,
    ) -> UUID:
        self.command_acks.append((command_id, status, detail))
        for index, command in enumerate(self.commands):
            if command.id != command_id:
                continue
            if status in {GatewayCommandStatus.COMPLETED, GatewayCommandStatus.FAILED}:
                self.commands.pop(index)
            else:
                self.commands[index] = command.model_copy(update={"status": status})
            break
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


class ArmRecordingGateway(FakeVehicleGateway):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.arm_count = 0

    async def arm_vehicle(self) -> VehicleArmResult:
        self.arm_count += 1
        return await super().arm_vehicle()

    async def read_health(self) -> VehicleHealth:
        health = await super().read_health()
        return health.model_copy(update={"source": OperationalSource.SITL})


class ExternalArmRaceGateway(ArmRecordingGateway):
    async def arm_vehicle(self) -> VehicleArmResult:
        self.arm_count += 1
        self._armed = True
        return VehicleArmResult(
            command_sent=False,
            command_acknowledged=False,
            armed_heartbeat_confirmed=True,
            external_state_reconciled=True,
        )


class UncertainUploadGateway(FakeVehicleGateway):
    def __init__(self, settings: Settings, *, persisted_before_timeout: bool = True) -> None:
        super().__init__(settings)
        self.upload_attempts = 0
        self.verify_attempts = 0
        self.persisted_before_timeout = persisted_before_timeout

    async def upload_mission(self, mission: AuthorizedMission, mission_file: str):  # type: ignore[no-untyped-def]
        del mission_file
        self.upload_attempts += 1
        if self.persisted_before_timeout:
            self._uploaded[str(mission.id)] = mission.mission_sha256
        raise VehicleTimeoutError("MISSION_ACK não chegou")

    async def verify_mission(self, mission: AuthorizedMission):  # type: ignore[no-untyped-def]
        self.verify_attempts += 1
        return await super().verify_mission(mission)


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


class FlakyCommandCompletionBackend(RecordingBackend):
    def __init__(
        self,
        claim: ClaimResponse,
        fail_command: GatewayCommandType = GatewayCommandType.PAUSE,
    ) -> None:
        super().__init__(claim)
        self.fail_command = fail_command
        self.fail_completion_once = True

    async def acknowledge_command(
        self,
        command_id: UUID,
        status: GatewayCommandStatus,
        *,
        detail: str | None = None,
        event_id: UUID | None = None,
    ) -> UUID:
        command = next((item for item in self.commands if item.id == command_id), None)
        if (
            status is GatewayCommandStatus.COMPLETED
            and command is not None
            and command.command is self.fail_command
            and self.fail_completion_once
        ):
            self.fail_completion_once = False
            raise BackendUnavailableError("command completion outage")
        return await super().acknowledge_command(
            command_id,
            status,
            detail=detail,
            event_id=event_id,
        )


class ArmHealthOrderingBackend(RecordingBackend):
    def __init__(self, claim: ClaimResponse) -> None:
        super().__init__(claim)
        self.latest_armed: bool | None = None
        self.arm_completion_saw_fresh_health = False

    async def heartbeat(self, health: VehicleHealth) -> HeartbeatResponse:
        self.latest_armed = health.armed
        return await super().heartbeat(health)

    async def acknowledge_command(
        self,
        command_id: UUID,
        status: GatewayCommandStatus,
        *,
        detail: str | None = None,
        event_id: UUID | None = None,
    ) -> UUID:
        command = next((item for item in self.commands if item.id == command_id), None)
        if (
            command is not None
            and command.command is GatewayCommandType.ARM
            and status is GatewayCommandStatus.COMPLETED
        ):
            if self.latest_armed is not True:
                raise BackendContractError("backend ainda não recebeu health armado")
            self.arm_completion_saw_fresh_health = True
        return await super().acknowledge_command(
            command_id,
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


def enabled_settings(
    journal_path: Path,
    *,
    mavlink_mode: MavlinkMode = MavlinkMode.SIMULATION,
    allow_vehicle_arm: bool = False,
) -> Settings:
    return Settings(
        _env_file=None,
        mavlink_mode=mavlink_mode,
        allow_mission_upload=True,
        allow_flight_commands=True,
        allow_mission_start=True,
        allow_vehicle_arm=allow_vehicle_arm,
        gateway_journal_path=journal_path,
    )


@pytest.mark.asyncio
async def test_simulation_runs_one_claim_through_return_and_completion(tmp_path: Path) -> None:
    settings = enabled_settings(tmp_path / "executor-journal.json")
    claim = build_claim()
    backend = RecordingBackend(claim)
    vehicle = ControllableFakeGateway(settings)
    await vehicle.connect()
    current_time = [datetime.now(UTC)]
    executor = MissionExecutor(settings, backend, vehicle, now=lambda: current_time[0])

    await executor.run_cycle()
    current_time[0] += timedelta(seconds=settings.telemetry_persist_interval_seconds)
    vehicle.armed = True
    vehicle.mode = "AUTO"
    backend.queue_command(GatewayCommandType.START, requested_at=current_time[0])
    for _ in range(5):
        await executor.run_cycle()
        current_time[0] += timedelta(seconds=settings.telemetry_persist_interval_seconds)

    assert backend.claim_count == 1
    assert backend.upload_statuses == [
        MissionStatus.UPLOADING,
        MissionStatus.UPLOADED,
        MissionStatus.VERIFIED,
    ]
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
async def test_read_only_default_never_claims_or_uploads_authorized_mission(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, gateway_journal_path=tmp_path / "read-only.json")
    claim = build_claim()
    backend = RecordingBackend(claim)
    vehicle = FakeVehicleGateway(settings)
    await vehicle.connect()

    await MissionExecutor(settings, backend, vehicle).run_cycle()

    assert backend.claim_count == 0
    assert backend.upload_statuses == []


@pytest.mark.asyncio
async def test_uncertain_upload_is_not_repeated_after_restart(tmp_path: Path) -> None:
    journal_path = tmp_path / "uncertain-upload.json"
    settings = enabled_settings(journal_path)
    claim = build_claim()
    backend = RecordingBackend(claim)
    vehicle = UncertainUploadGateway(settings)
    await vehicle.connect()

    await MissionExecutor(settings, backend, vehicle).run_cycle()
    restored = MissionExecutor(settings, backend, vehicle)
    await restored.run_cycle()

    assert vehicle.upload_attempts == 1
    assert vehicle.verify_attempts == 1
    assert backend.upload_statuses == [
        MissionStatus.UPLOADING,
        MissionStatus.UPLOADED,
        MissionStatus.VERIFIED,
    ]
    assert "MISSION_UPLOAD_RESULT_UNCERTAIN" in backend.events


@pytest.mark.asyncio
async def test_uncertain_upload_mismatch_blocks_without_reupload(tmp_path: Path) -> None:
    journal_path = tmp_path / "uncertain-upload-mismatch.json"
    settings = enabled_settings(journal_path)
    claim = build_claim()
    backend = RecordingBackend(claim)
    vehicle = UncertainUploadGateway(settings, persisted_before_timeout=False)
    await vehicle.connect()

    await MissionExecutor(settings, backend, vehicle).run_cycle()
    restored = MissionExecutor(settings, backend, vehicle)
    await restored.run_cycle()
    await restored.run_cycle()

    assert vehicle.upload_attempts == 1
    assert vehicle.verify_attempts == 1
    assert backend.upload_statuses == [MissionStatus.UPLOADING]
    assert "MISSION_UPLOAD_RECOVERY_BLOCKED" in backend.events


@pytest.mark.asyncio
async def test_progress_journal_ignores_duplicate_after_executor_restart(tmp_path: Path) -> None:
    journal_path = tmp_path / "progress.json"
    settings = enabled_settings(journal_path)
    claim = build_claim()
    backend = RecordingBackend(claim)
    vehicle = ControllableFakeGateway(settings)
    await vehicle.connect()
    executor = MissionExecutor(settings, backend, vehicle)

    await executor.run_cycle()
    vehicle.armed = True
    vehicle.mode = "AUTO"
    backend.queue_command(GatewayCommandType.START)
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
    settings = enabled_settings(journal_path)
    claim = build_claim()
    backend = FlakyDestinationBackend(claim)
    vehicle = ControllableFakeGateway(settings)
    await vehicle.connect()
    executor = MissionExecutor(settings, backend, vehicle)
    await executor.run_cycle()
    vehicle.armed = True
    vehicle.mode = "AUTO"
    backend.queue_command(GatewayCommandType.START)
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
    settings = enabled_settings(tmp_path / "binding.json")
    claim = build_claim()
    backend = MismatchedHeartbeatBackend(claim)
    vehicle = FakeVehicleGateway(settings)
    await vehicle.connect()

    await MissionExecutor(settings, backend, vehicle).run_cycle()

    assert backend.claim_count == 0
    assert backend.upload_statuses == []


@pytest.mark.asyncio
async def test_executor_rejects_heartbeat_identity_mismatch(tmp_path: Path) -> None:
    settings = enabled_settings(tmp_path / "identity.json")
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
    settings = enabled_settings(journal_path, mavlink_mode=MavlinkMode.SITL)
    claim = build_claim()
    backend = FlakyExecutingBackend(claim)
    vehicle = ControllableFakeGateway(settings)
    await vehicle.connect()
    executor = MissionExecutor(settings, backend, vehicle)
    await executor.run_cycle()
    vehicle.armed = True
    vehicle.mode = "AUTO"
    backend.queue_command(GatewayCommandType.START)

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
    settings = enabled_settings(journal_path)
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
    assert backend.upload_statuses == [
        MissionStatus.UPLOADING,
        MissionStatus.UPLOADED,
        MissionStatus.VERIFIED,
    ]
    assert restored.active_mission_id == claim.mission.id


@pytest.mark.asyncio
async def test_authorization_is_revalidated_before_start(tmp_path: Path) -> None:
    current_time = datetime.now(UTC)
    claim = build_claim()
    claim = claim.model_copy(
        update={"authorization_expires_at": current_time + timedelta(seconds=30)}
    )
    settings = enabled_settings(tmp_path / "expiry.json", mavlink_mode=MavlinkMode.SITL)
    backend = RecordingBackend(claim)
    vehicle = ControllableFakeGateway(settings)
    await vehicle.connect()
    clock = [current_time]
    executor = MissionExecutor(settings, backend, vehicle, now=lambda: clock[0])
    await executor.run_cycle()
    vehicle.armed = True
    vehicle.mode = "AUTO"
    clock[0] = current_time + timedelta(minutes=1)
    backend.queue_command(GatewayCommandType.START, requested_at=clock[0])

    await executor.run_cycle()

    assert vehicle.start_count == 0
    assert backend.statuses == []
    assert backend.command_acks[-1][1] is GatewayCommandStatus.FAILED
    assert "preflight" in (backend.command_acks[-1][2] or "").lower()
    assert executor.active_mission_id == claim.mission.id


@pytest.mark.asyncio
async def test_backend_health_failure_is_revalidated_before_start(tmp_path: Path) -> None:
    settings = enabled_settings(tmp_path / "backend-policy.json", mavlink_mode=MavlinkMode.SITL)
    claim = build_claim()
    backend = StartRejectedHeartbeatBackend(claim)
    vehicle = ControllableFakeGateway(settings)
    await vehicle.connect()
    executor = MissionExecutor(settings, backend, vehicle)
    await executor.run_cycle()
    vehicle.armed = True
    vehicle.mode = "AUTO"
    backend.queue_command(GatewayCommandType.START)

    await executor.run_cycle()

    assert vehicle.start_count == 0
    assert backend.statuses == []
    assert backend.command_acks[-1][1] is GatewayCommandStatus.FAILED
    assert "elegibilidade" in (backend.command_acks[-1][2] or "").lower()
    assert executor.active_mission_id == claim.mission.id


@pytest.mark.asyncio
async def test_expired_start_command_is_rejected_without_vehicle_action(tmp_path: Path) -> None:
    current_time = datetime.now(UTC)
    settings = enabled_settings(tmp_path / "expired-command.json", mavlink_mode=MavlinkMode.SITL)
    claim = build_claim()
    backend = RecordingBackend(claim)
    vehicle = ControllableFakeGateway(settings)
    await vehicle.connect()
    executor = MissionExecutor(settings, backend, vehicle, now=lambda: current_time)
    await executor.run_cycle()
    vehicle.armed = True
    vehicle.mode = "AUTO"
    backend.queue_command(
        GatewayCommandType.START,
        requested_at=current_time - timedelta(seconds=settings.gateway_command_max_age_seconds + 1),
    )

    await executor.run_cycle()

    assert vehicle.start_count == 0
    assert backend.command_acks[-1][1] is GatewayCommandStatus.FAILED
    assert "expirado" in (backend.command_acks[-1][2] or "").lower()


@pytest.mark.asyncio
async def test_pause_and_continue_require_explicit_commands(tmp_path: Path) -> None:
    settings = enabled_settings(tmp_path / "pause-continue.json", mavlink_mode=MavlinkMode.SITL)
    claim = build_claim()
    backend = RecordingBackend(claim)
    vehicle = ControllableFakeGateway(settings)
    await vehicle.connect()
    executor = MissionExecutor(settings, backend, vehicle)
    await executor.run_cycle()
    vehicle.armed = True
    vehicle.mode = "AUTO"
    backend.queue_command(GatewayCommandType.START)
    await executor.run_cycle()

    backend.queue_command(GatewayCommandType.PAUSE)
    await executor.run_cycle()
    assert backend.statuses[-1] is MissionStatus.PAUSED
    assert vehicle._mission_paused is True

    backend.queue_command(GatewayCommandType.CONTINUE)
    await executor.run_cycle()
    assert backend.statuses[-1] is MissionStatus.EXECUTING
    assert vehicle._mission_paused is False


@pytest.mark.asyncio
async def test_pause_completion_is_reconciled_without_resending_vehicle_command(
    tmp_path: Path,
) -> None:
    settings = enabled_settings(
        tmp_path / "pause-reconciliation.json", mavlink_mode=MavlinkMode.SITL
    )
    claim = build_claim()
    backend = FlakyCommandCompletionBackend(claim)
    vehicle = ControllableFakeGateway(settings)
    await vehicle.connect()
    executor = MissionExecutor(settings, backend, vehicle)
    await executor.run_cycle()
    vehicle.armed = True
    vehicle.mode = "AUTO"
    backend.queue_command(GatewayCommandType.START)
    await executor.run_cycle()

    pause_count = 0
    original_pause = vehicle.pause_mission

    async def count_pause() -> None:
        nonlocal pause_count
        pause_count += 1
        await original_pause()

    vehicle.pause_mission = count_pause  # type: ignore[method-assign]
    backend.queue_command(GatewayCommandType.PAUSE)

    with pytest.raises(BackendUnavailableError, match="command completion outage"):
        await executor.run_cycle()

    assert pause_count == 1
    assert backend.commands[0].status is GatewayCommandStatus.ACKNOWLEDGED
    assert backend.statuses[-1] is MissionStatus.PAUSED

    await executor.run_cycle()

    assert pause_count == 1
    assert backend.commands == []
    assert backend.command_acks[-1][1] is GatewayCommandStatus.COMPLETED
    assert "reconciliado" in (backend.command_acks[-1][2] or "").lower()


@pytest.mark.asyncio
async def test_continue_completion_is_reconciled_without_resending_vehicle_command(
    tmp_path: Path,
) -> None:
    settings = enabled_settings(
        tmp_path / "continue-reconciliation.json", mavlink_mode=MavlinkMode.SITL
    )
    claim = build_claim()
    backend = FlakyCommandCompletionBackend(claim, GatewayCommandType.CONTINUE)
    vehicle = ControllableFakeGateway(settings)
    await vehicle.connect()
    executor = MissionExecutor(settings, backend, vehicle)
    await executor.run_cycle()
    vehicle.armed = True
    vehicle.mode = "AUTO"
    backend.queue_command(GatewayCommandType.START)
    await executor.run_cycle()
    backend.queue_command(GatewayCommandType.PAUSE)
    await executor.run_cycle()

    continue_count = 0
    original_continue = vehicle.continue_mission

    async def count_continue() -> None:
        nonlocal continue_count
        continue_count += 1
        await original_continue()

    vehicle.continue_mission = count_continue  # type: ignore[method-assign]
    backend.queue_command(GatewayCommandType.CONTINUE)

    with pytest.raises(BackendUnavailableError, match="command completion outage"):
        await executor.run_cycle()

    assert continue_count == 1
    assert backend.commands[0].status is GatewayCommandStatus.ACKNOWLEDGED
    assert backend.statuses[-1] is MissionStatus.EXECUTING

    await executor.run_cycle()

    assert continue_count == 1
    assert backend.commands == []
    assert backend.command_acks[-1][1] is GatewayCommandStatus.COMPLETED
    assert "reconciliado" in (backend.command_acks[-1][2] or "").lower()


@pytest.mark.asyncio
async def test_link_loss_keeps_active_mission_and_does_not_fabricate_telemetry(
    tmp_path: Path,
) -> None:
    settings = enabled_settings(tmp_path / "link-loss.json", mavlink_mode=MavlinkMode.SITL)
    claim = build_claim()
    backend = RecordingBackend(claim)
    vehicle = ControllableFakeGateway(settings)
    await vehicle.connect()
    executor = MissionExecutor(settings, backend, vehicle)
    await executor.run_cycle()
    vehicle.armed = True
    vehicle.mode = "AUTO"
    backend.queue_command(GatewayCommandType.START)
    await executor.run_cycle()
    telemetry_before_loss = len(backend.telemetry)
    vehicle.link_connected = False

    await executor.run_cycle()

    assert len(backend.telemetry) == telemetry_before_loss
    assert "VEHICLE_LINK_LOST" in backend.events
    assert executor.active_mission_id == claim.mission.id


@pytest.mark.asyncio
async def test_pending_arm_requires_verified_waiting_mission_and_confirms_simulated_state(
    tmp_path: Path,
) -> None:
    settings = enabled_settings(
        tmp_path / "arm-command.json",
        allow_vehicle_arm=True,
    )
    claim = build_claim()
    backend = ArmHealthOrderingBackend(claim)
    vehicle = ArmRecordingGateway(settings)
    await vehicle.connect()
    executor = MissionExecutor(settings, backend, vehicle)
    await executor.run_cycle()
    backend.queue_command(GatewayCommandType.ARM)

    await executor.run_cycle()

    assert vehicle.arm_count == 1
    assert backend.arm_completion_saw_fresh_health
    assert (await vehicle.read_health()).armed is True
    assert [status for _id, status, _detail in backend.command_acks[-2:]] == [
        GatewayCommandStatus.ACKNOWLEDGED,
        GatewayCommandStatus.COMPLETED,
    ]


@pytest.mark.asyncio
async def test_pending_arm_reconciles_already_armed_vehicle_without_resend(
    tmp_path: Path,
) -> None:
    settings = enabled_settings(
        tmp_path / "arm-already-confirmed.json",
        allow_vehicle_arm=True,
    )
    claim = build_claim()
    backend = RecordingBackend(claim)
    vehicle = ArmRecordingGateway(settings)
    await vehicle.connect()
    executor = MissionExecutor(settings, backend, vehicle)
    await executor.run_cycle()
    vehicle._armed = True
    backend.queue_command(GatewayCommandType.ARM)

    await executor.run_cycle()

    assert vehicle.arm_count == 0
    assert backend.command_acks[-1][1] is GatewayCommandStatus.COMPLETED
    assert "sem envio MAVLink" in (backend.command_acks[-1][2] or "")


@pytest.mark.asyncio
async def test_arm_race_reconciles_external_state_without_claiming_command_ack(
    tmp_path: Path,
) -> None:
    settings = enabled_settings(
        tmp_path / "arm-external-race.json",
        allow_vehicle_arm=True,
    )
    claim = build_claim()
    backend = RecordingBackend(claim)
    vehicle = ExternalArmRaceGateway(settings)
    await vehicle.connect()
    executor = MissionExecutor(settings, backend, vehicle)
    await executor.run_cycle()
    backend.queue_command(GatewayCommandType.ARM)

    await executor.run_cycle()

    detail = backend.command_acks[-1][2] or ""
    assert vehicle.arm_count == 1
    assert backend.command_acks[-1][1] is GatewayCommandStatus.COMPLETED
    assert "armamento externo" in detail
    assert "COMMAND_ACK correlacionado" not in detail


@pytest.mark.asyncio
@pytest.mark.parametrize("observed_armed", [False, None])
async def test_acknowledged_arm_after_restart_never_resends_without_armed_confirmation(
    tmp_path: Path,
    observed_armed: bool | None,
) -> None:
    settings = enabled_settings(
        tmp_path / f"arm-restart-{observed_armed}.json",
        allow_vehicle_arm=True,
    )
    claim = build_claim()
    backend = RecordingBackend(claim)
    vehicle = ArmRecordingGateway(settings)
    await vehicle.connect()
    original = MissionExecutor(settings, backend, vehicle)
    await original.run_cycle()
    queued = backend.queue_command(GatewayCommandType.ARM)
    backend.commands[0] = queued.model_copy(update={"status": GatewayCommandStatus.ACKNOWLEDGED})
    vehicle._armed = observed_armed

    restarted = MissionExecutor(settings, backend, vehicle)
    await restarted.run_cycle()

    assert vehicle.arm_count == 0
    assert backend.command_acks[-1][1] is GatewayCommandStatus.FAILED
    assert "incerto" in (backend.command_acks[-1][2] or "")


@pytest.mark.asyncio
async def test_acknowledged_arm_completion_outage_reconciles_true_heartbeat_without_resend(
    tmp_path: Path,
) -> None:
    settings = enabled_settings(
        tmp_path / "arm-completion-outage.json",
        allow_vehicle_arm=True,
    )
    claim = build_claim()
    backend = FlakyCommandCompletionBackend(claim, GatewayCommandType.ARM)
    vehicle = ArmRecordingGateway(settings)
    await vehicle.connect()
    executor = MissionExecutor(settings, backend, vehicle)
    await executor.run_cycle()
    backend.queue_command(GatewayCommandType.ARM)

    with pytest.raises(BackendUnavailableError, match="command completion outage"):
        await executor.run_cycle()

    assert vehicle.arm_count == 1
    assert backend.commands[0].status is GatewayCommandStatus.ACKNOWLEDGED

    restarted = MissionExecutor(settings, backend, vehicle)
    await restarted.run_cycle()

    assert vehicle.arm_count == 1
    assert backend.commands == []
    assert backend.command_acks[-1][1] is GatewayCommandStatus.COMPLETED
    assert "sem reenvio" in (backend.command_acks[-1][2] or "")


@pytest.mark.asyncio
async def test_arm_is_rejected_outside_verified_waiting_phase_without_vehicle_action(
    tmp_path: Path,
) -> None:
    settings = enabled_settings(
        tmp_path / "arm-wrong-phase.json",
        allow_vehicle_arm=True,
    )
    claim = build_claim()
    backend = RecordingBackend(claim)
    vehicle = ArmRecordingGateway(settings)
    await vehicle.connect()
    executor = MissionExecutor(settings, backend, vehicle)
    await executor.run_cycle()
    assert executor._active is not None
    executor._active.phase = ActivePhase.EXECUTING
    executor._active.claim = executor._active.claim.model_copy(
        update={
            "mission": executor._active.claim.mission.model_copy(
                update={"status": MissionStatus.EXECUTING}
            )
        }
    )
    executor._save_active()
    backend.queue_command(GatewayCommandType.ARM)

    await executor.run_cycle()

    assert vehicle.arm_count == 0
    assert backend.command_acks[-1][1] is GatewayCommandStatus.FAILED
    assert "VERIFIED_PENDING_REPORT/WAITING_OPERATOR_ARM" in (backend.command_acks[-1][2] or "")


@pytest.mark.asyncio
async def test_executor_defensively_requires_all_three_arm_gates_before_ack(
    tmp_path: Path,
) -> None:
    settings = enabled_settings(
        tmp_path / "arm-gate-defense.json",
        allow_vehicle_arm=True,
    )
    claim = build_claim()
    backend = RecordingBackend(claim)
    vehicle = ArmRecordingGateway(settings)
    await vehicle.connect()
    executor = MissionExecutor(settings, backend, vehicle)
    await executor.run_cycle()
    executor._settings = settings.model_copy(update={"allow_mission_start": False})
    backend.queue_command(GatewayCommandType.ARM)

    await executor.run_cycle()

    assert vehicle.arm_count == 0
    assert backend.command_acks[-1][1] is GatewayCommandStatus.FAILED
    assert GatewayCommandStatus.ACKNOWLEDGED not in {
        status for _id, status, _detail in backend.command_acks[-1:]
    }
    assert "ALLOW_MISSION_START" in (backend.command_acks[-1][2] or "")
