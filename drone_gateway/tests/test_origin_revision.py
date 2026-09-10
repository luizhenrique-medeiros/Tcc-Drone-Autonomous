from pathlib import Path
from uuid import uuid4

import pytest
from test_executor import RecordingBackend, build_claim

from app.core.config import Settings
from app.core.exceptions import BackendContractError, BackendUnavailableError, UnsafeOperationError
from app.mavlink.fake_gateway import FakeVehicleGateway
from app.missions.executor import ActiveMission, ActivePhase, MissionExecutor
from app.missions.journal import MissionJournal
from app.models import OperationalSource, RetiredVersionReleaseResult


class RevisionBackend(RecordingBackend):
    def __init__(self, claim):
        super().__init__(claim)
        self.release_count = 0
        self.result = RetiredVersionReleaseResult(
            mission_id=claim.mission.id,
            version=claim.mission.version,
            mission_sha256=claim.mission.mission_sha256,
            released=True,
        )
        self.fail = False

    async def release_retired_version(self, mission):
        self.release_count += 1
        if self.fail:
            raise BackendUnavailableError("Resposta perdida")
        return self.result


class ObservingVehicle(FakeVehicleGateway):
    arm_after_reply = False

    async def read_health(self):
        health = await super().read_health()
        return health.model_copy(
            update={
                "source": OperationalSource.SITL,
                "flight_mode": "STABILIZE",
                "heartbeat_age_seconds": 0.1,
                "armed": self.arm_after_reply,
            }
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fault",
    [None, "armed", "stale", "unknown", "gate", "phase", "binding", "denied", "offline", "race"],
)
async def test_retirement_never_sends_mavlink_and_only_clears_matching_waiting_journal(
    tmp_path: Path, fault
):
    settings = Settings(_env_file=None, gateway_journal_path=tmp_path / "journal.json")
    claim = build_claim()
    backend = RevisionBackend(claim)
    vehicle = ObservingVehicle(settings)
    await vehicle.connect()
    health = (await vehicle.read_health()).model_copy(
        update={
            "source": OperationalSource.SITL,
            "flight_mode": "STABILIZE",
            "heartbeat_age_seconds": 0.1,
        }
    )
    journal = MissionJournal(settings.gateway_journal_path)
    executor = MissionExecutor(settings, backend, vehicle, journal=journal)
    executor._backend_vehicle_id = claim.mission.vehicle_id
    executor._active = ActiveMission(claim=claim, phase=ActivePhase.WAITING_OPERATOR_ARM)
    if fault == "armed":
        health = health.model_copy(update={"armed": True})
    elif fault == "stale":
        health = health.model_copy(update={"heartbeat_age_seconds": 100})
    elif fault == "unknown":
        health = health.model_copy(update={"heartbeat_age_seconds": None})
    elif fault == "gate":
        settings.allow_vehicle_arm = True
    elif fault == "phase":
        executor._active.phase = ActivePhase.START_COMMAND_SENT
    elif fault == "binding":
        backend.result = backend.result.model_copy(update={"mission_id": uuid4()})
    elif fault == "denied":
        backend.result = backend.result.model_copy(update={"released": False})
    elif fault == "offline":
        backend.fail = True
    elif fault == "race":
        vehicle.arm_after_reply = True
    executor._save_active()
    if fault in {"binding", "offline", "race"}:
        with pytest.raises((BackendContractError, BackendUnavailableError, UnsafeOperationError)):
            await executor._release_retired_preflight(health)
    else:
        assert await executor._release_retired_preflight(health) is (fault is None)
    assert (journal.load() is None) is (fault is None)
    assert vehicle._uploaded == {}
    assert vehicle._active_mission_id is None
    assert not vehicle._armed
    assert backend.claim_count == 0
    assert backend.commands == []
