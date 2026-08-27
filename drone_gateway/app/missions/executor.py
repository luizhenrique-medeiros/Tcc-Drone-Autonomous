import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol
from uuid import UUID, uuid4

from app.clients.backend_client import BackendClient
from app.core.config import Settings
from app.core.exceptions import (
    BackendContractError,
    BackendUnavailableError,
    ConfigurationError,
    GatewayError,
    MissionValidationError,
    UnsafeOperationError,
    VehicleTimeoutError,
)
from app.mavlink.vehicle_gateway import VehicleGateway
from app.missions.journal import JournalRecord, MissionJournal
from app.missions.validator import validate_claimed_mission
from app.models import (
    AuthorizedMission,
    ClaimResponse,
    GatewayCommand,
    GatewayCommandStatus,
    GatewayCommandType,
    HeartbeatResponse,
    MissionStatus,
    OperationalSource,
    TelemetrySnapshot,
    VehicleEvent,
    VehicleHealth,
)
from app.safety.preflight import evaluate_preflight, evaluate_start_readiness

logger = logging.getLogger(__name__)


class BackendPort(Protocol):
    async def heartbeat(self, health: VehicleHealth) -> HeartbeatResponse: ...

    async def authorized_missions(self) -> list[AuthorizedMission]: ...

    async def claim(self, mission_id: UUID) -> ClaimResponse: ...

    async def pending_commands(self, limit: int = 20) -> list[GatewayCommand]: ...

    async def acknowledge_command(
        self,
        command_id: UUID,
        status: GatewayCommandStatus,
        *,
        detail: str | None = None,
        event_id: UUID | None = None,
    ) -> UUID: ...

    async def report_upload(
        self,
        mission_id: UUID,
        status: MissionStatus,
        *,
        detail: str | None = None,
        event_id: UUID | None = None,
    ) -> UUID: ...

    async def report_status(
        self,
        mission_id: UUID,
        status: MissionStatus,
        *,
        detail: str | None = None,
        event_id: UUID | None = None,
    ) -> UUID: ...

    async def report_telemetry(
        self,
        mission_id: UUID,
        vehicle_id: UUID,
        telemetry: TelemetrySnapshot,
        *,
        event_id: UUID | None = None,
    ) -> UUID: ...

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
    ) -> UUID: ...


class ActivePhase(StrEnum):
    UPLOADING_PENDING_REPORT = "UPLOADING_PENDING_REPORT"
    UPLOADING = "UPLOADING"
    UPLOAD_COMMAND_SENT = "UPLOAD_COMMAND_SENT"
    UPLOAD_RECOVERY_BLOCKED = "UPLOAD_RECOVERY_BLOCKED"
    RECOVERED_UPLOAD_PENDING_REPORT = "RECOVERED_UPLOAD_PENDING_REPORT"
    UPLOADED_PENDING_REPORT = "UPLOADED_PENDING_REPORT"
    VERIFYING = "VERIFYING"
    VERIFIED_PENDING_REPORT = "VERIFIED_PENDING_REPORT"
    WAITING_OPERATOR_ARM = "WAITING_OPERATOR_ARM"
    START_COMMAND_SENT = "START_COMMAND_SENT"
    EXECUTING_PENDING_REPORT = "EXECUTING_PENDING_REPORT"
    EXECUTING = "EXECUTING"
    PAUSED = "PAUSED"


CLAIM_PENDING_PHASE = "CLAIM_PENDING"
PROGRESS_STATUSES = (
    MissionStatus.DESTINATION_REACHED,
    MissionStatus.DELIVERY_CONFIRMED,
    MissionStatus.RETURNING,
    MissionStatus.COMPLETED,
)
PROGRESS_DETAILS = {
    MissionStatus.DESTINATION_REACHED: (
        "MISSION_ITEM_REACHED confirmou o waypoint canônico de destino."
    ),
    MissionStatus.DELIVERY_CONFIRMED: (
        "A sequência MAV_CMD_DO_GRIPPER foi alcançada ou ultrapassada; este estado "
        "confirma o comando do mecanismo e não comprova fisicamente o pacote."
    ),
    MissionStatus.RETURNING: (
        "MISSION_CURRENT/ITEM_REACHED confirmou o início da sequência canônica de retorno."
    ),
    MissionStatus.COMPLETED: (
        "O item LAND final foi alcançado, o veículo está desarmado e a posição está "
        "próxima da origem."
    ),
}


@dataclass(slots=True)
class ActiveMission:
    claim: ClaimResponse
    phase: ActivePhase
    pending_event_id: UUID | None = None
    upload_detail: str | None = None
    upload_uncertain_reported: bool = False
    verification_failure_reported: bool = False
    link_loss_reported: bool = False
    telemetry_stale_reported: bool = False
    start_uncertain_reported: bool = False
    binding_failure_reported: bool = False
    pending_status: MissionStatus | None = None
    pending_status_event_id: UUID | None = None
    last_reported_progress_status: MissionStatus | None = None


class MissionExecutor:
    def __init__(
        self,
        settings: Settings,
        backend: BackendPort | BackendClient,
        vehicle: VehicleGateway,
        *,
        journal: MissionJournal | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._settings = settings
        self._backend = backend
        self._vehicle = vehicle
        self._journal = journal or MissionJournal(settings.gateway_journal_path)
        self._now = now or (lambda: datetime.now(UTC))
        self._backend_vehicle_id: UUID | None = None
        self._backend_health_failures: list[str] = []
        self._last_telemetry_report_at: datetime | None = None
        self._pending_claim: AuthorizedMission | None = None
        self._active = self._restore_active()

    @property
    def active_mission_id(self) -> UUID | None:
        return self._active.claim.mission.id if self._active else None

    def _restore_active(self) -> ActiveMission | None:
        record = self._journal.load()
        if record is None:
            return None
        if record.phase == CLAIM_PENDING_PHASE:
            if record.offered_mission is None or record.claim is not None:
                raise ConfigurationError("Journal contém intenção de claim inválida.")
            self._pending_claim = record.offered_mission
            return None
        if record.claim is None or record.offered_mission is not None:
            raise ConfigurationError("Journal contém missão ativa inválida.")
        try:
            phase = ActivePhase(record.phase)
        except ValueError as exc:
            raise ConfigurationError(
                f"Fase desconhecida no journal do gateway: {record.phase}."
            ) from exc
        claim = record.claim
        if phase in {
            ActivePhase.VERIFIED_PENDING_REPORT,
            ActivePhase.WAITING_OPERATOR_ARM,
        }:
            claim = claim.model_copy(
                update={
                    "mission": claim.mission.model_copy(update={"status": MissionStatus.VERIFIED})
                }
            )
        return ActiveMission(
            claim=claim,
            phase=phase,
            pending_event_id=record.pending_event_id,
            upload_detail=record.upload_detail,
            upload_uncertain_reported=record.upload_uncertain_reported,
            verification_failure_reported=record.verification_failure_reported,
            link_loss_reported=record.link_loss_reported,
            telemetry_stale_reported=record.telemetry_stale_reported,
            start_uncertain_reported=record.start_uncertain_reported,
            binding_failure_reported=record.binding_failure_reported,
            pending_status=record.pending_status,
            pending_status_event_id=record.pending_status_event_id,
            last_reported_progress_status=record.last_reported_progress_status,
        )

    def _save_active(self) -> None:
        active = self._active
        if active is None:
            self._journal.clear()
            return
        self._journal.save(
            JournalRecord(
                claim=active.claim,
                phase=active.phase,
                pending_event_id=active.pending_event_id,
                upload_detail=active.upload_detail,
                upload_uncertain_reported=active.upload_uncertain_reported,
                verification_failure_reported=active.verification_failure_reported,
                link_loss_reported=active.link_loss_reported,
                telemetry_stale_reported=active.telemetry_stale_reported,
                start_uncertain_reported=active.start_uncertain_reported,
                binding_failure_reported=active.binding_failure_reported,
                pending_status=active.pending_status,
                pending_status_event_id=active.pending_status_event_id,
                last_reported_progress_status=active.last_reported_progress_status,
            )
        )

    def _save_claim_intent(self, offered_mission: AuthorizedMission) -> None:
        self._pending_claim = offered_mission
        self._journal.save(
            JournalRecord(
                offered_mission=offered_mission,
                phase=CLAIM_PENDING_PHASE,
            )
        )

    def _clear_active(self) -> None:
        self._active = None
        self._pending_claim = None
        self._last_telemetry_report_at = None
        self._journal.clear()

    async def run_cycle(self) -> None:
        health = await self._vehicle.read_health()
        heartbeat = await self._backend.heartbeat(health)
        if (
            heartbeat.vehicle.identifier != self._settings.vehicle_identifier
            or heartbeat.vehicle.gateway_id != self._settings.gateway_id
            or (
                self._backend_vehicle_id is not None
                and heartbeat.vehicle.id != self._backend_vehicle_id
            )
        ):
            raise BackendContractError(
                "Heartbeat retornou identidade de veículo ou gateway diferente da solicitada."
            )
        self._backend_vehicle_id = heartbeat.vehicle.id
        self._backend_health_failures = heartbeat.failures
        await self._forward_vehicle_events(await self._vehicle.drain_events())
        if self._pending_claim is not None:
            if (
                not self._settings.allow_mission_upload
                or not health.connected
                or not health.heartbeat
            ):
                return
            if not self._mission_matches_vehicle(self._pending_claim):
                logger.error(
                    "pending claim does not match connected vehicle",
                    extra={"gateway_id": self._settings.gateway_id},
                )
                return
            await self._claim_and_stage(
                self._pending_claim,
                health,
                authorization_eligible=heartbeat.authorization_eligible,
            )
            return
        commands = await self._backend.pending_commands(limit=20)
        if commands:
            await self._process_command(
                commands[0],
                health,
                authorization_eligible=heartbeat.authorization_eligible,
            )
            return
        if self._active is not None:
            await self._continue_active(
                health,
                authorization_eligible=heartbeat.authorization_eligible,
            )
            return
        if (
            not self._settings.allow_mission_upload
            or not health.connected
            or not health.heartbeat
            or not heartbeat.authorization_eligible
        ):
            return
        missions = await self._backend.authorized_missions()
        offered = next((item for item in missions if self._mission_matches_vehicle(item)), None)
        if offered is None:
            if missions:
                logger.error(
                    "authorized mission does not match connected vehicle",
                    extra={"gateway_id": self._settings.gateway_id},
                )
            return
        await self._claim_and_stage(
            offered,
            health,
            authorization_eligible=heartbeat.authorization_eligible,
        )

    def _mission_matches_vehicle(self, mission: AuthorizedMission) -> bool:
        return mission.vehicle_id is not None and mission.vehicle_id == self._backend_vehicle_id

    def _backend_allows_armed_start(self, authorization_eligible: bool) -> bool:
        if authorization_eligible:
            return True
        return set(self._backend_health_failures) == {"VEHICLE_ALREADY_ARMED"}

    async def _forward_vehicle_events(self, events: list[VehicleEvent]) -> None:
        active = self._active
        for event in events:
            if active is None:
                log_method = (
                    logger.warning
                    if event.severity in {"WARNING", "ERROR", "CRITICAL"}
                    else logger.info
                )
                log_method(
                    event.message,
                    extra={"gateway_id": self._settings.gateway_id},
                )
                continue
            await self._backend.report_event(
                active.claim.mission.id,
                event_type=event.event_type,
                severity=event.severity,
                message=event.message,
                metadata=event.metadata,
                occurred_at=event.occurred_at,
            )

    async def _process_command(
        self,
        command: GatewayCommand,
        health: VehicleHealth,
        *,
        authorization_eligible: bool,
    ) -> None:
        active = self._active
        if active is None or active.claim.mission.id != command.mission_id:
            await self._backend.acknowledge_command(
                command.id,
                GatewayCommandStatus.FAILED,
                detail=(
                    "Gateway não possui esta missão como ativa; "
                    "intervenção do operador é necessária."
                ),
            )
            return
        if command.command is GatewayCommandType.ARM:
            await self._process_arm_command(
                command,
                active,
                health,
                authorization_eligible=authorization_eligible,
            )
            return
        if command.command is GatewayCommandType.START and active.phase in {
            ActivePhase.EXECUTING_PENDING_REPORT,
            ActivePhase.EXECUTING,
        }:
            if active.phase is ActivePhase.EXECUTING_PENDING_REPORT:
                await self._continue_active(
                    health,
                    authorization_eligible=authorization_eligible,
                )
            await self._backend.acknowledge_command(
                command.id,
                GatewayCommandStatus.COMPLETED,
                detail="START já confirmado localmente; estado reconciliado sem reenvio.",
            )
            return
        if (
            command.command is GatewayCommandType.START
            and active.phase is ActivePhase.START_COMMAND_SENT
        ):
            await self._backend.acknowledge_command(
                command.id,
                GatewayCommandStatus.FAILED,
                detail=(
                    "Resultado anterior de START é incerto; o gateway não repetirá o comando "
                    "automaticamente. Confirme o estado físico no Mission Planner."
                ),
            )
            return
        if command.status is GatewayCommandStatus.ACKNOWLEDGED:
            reconciled_detail = None
            if command.command is GatewayCommandType.PAUSE and active.phase is ActivePhase.PAUSED:
                reconciled_detail = (
                    "PAUSE já confirmado localmente; estado reconciliado sem reenviar o comando."
                )
            elif (
                command.command is GatewayCommandType.CONTINUE
                and active.phase is ActivePhase.EXECUTING
            ):
                reconciled_detail = (
                    "CONTINUE já confirmado localmente; estado reconciliado sem reenviar o comando."
                )
            if reconciled_detail is not None:
                await self._backend.acknowledge_command(
                    command.id,
                    GatewayCommandStatus.COMPLETED,
                    detail=reconciled_detail,
                )
                return
        requested_at = command.requested_at
        if requested_at.tzinfo is None:
            requested_at = requested_at.replace(tzinfo=UTC)
        if self._now() - requested_at > timedelta(
            seconds=self._settings.gateway_command_max_age_seconds
        ):
            await self._backend.acknowledge_command(
                command.id,
                GatewayCommandStatus.FAILED,
                detail="Comando expirado; solicite uma nova ação administrativa.",
            )
            return
        if not self._settings.allow_flight_commands:
            await self._backend.acknowledge_command(
                command.id,
                GatewayCommandStatus.FAILED,
                detail="ALLOW_FLIGHT_COMMANDS não foi habilitado.",
            )
            return
        if not health.connected or not health.heartbeat:
            await self._backend.acknowledge_command(
                command.id,
                GatewayCommandStatus.FAILED,
                detail="Comando bloqueado: heartbeat MAVLink válido não está disponível.",
            )
            return
        if command.status is GatewayCommandStatus.PENDING:
            await self._backend.acknowledge_command(
                command.id,
                GatewayCommandStatus.ACKNOWLEDGED,
                detail="Comando recebido pelo gateway.",
            )
        reason_suffix = f" Motivo administrativo: {command.reason}" if command.reason else ""
        try:
            if command.command is GatewayCommandType.START:
                if not self._settings.allow_mission_start:
                    raise UnsafeOperationError("ALLOW_MISSION_START não foi habilitado.")
                if active.phase is not ActivePhase.WAITING_OPERATOR_ARM:
                    raise UnsafeOperationError("Missão não está aguardando início explícito.")
                if health.armed is not True:
                    raise UnsafeOperationError(
                        "Veículo não está comprovadamente armado; o gateway nunca arma sozinho."
                    )
                if not self._backend_allows_armed_start(authorization_eligible):
                    raise UnsafeOperationError("Backend bloqueou a elegibilidade para início.")
                readiness = evaluate_start_readiness(
                    health, active.claim, self._settings, now=self._now()
                )
                if not readiness.passed:
                    raise UnsafeOperationError(
                        "Início bloqueado pelo preflight: " + ", ".join(readiness.failures)
                    )
                await self._start(active)
            elif command.command is GatewayCommandType.PAUSE:
                if active.phase is not ActivePhase.EXECUTING:
                    raise UnsafeOperationError("Missão não está em execução para pausar.")
                await self._vehicle.pause_mission()
                await self._backend.report_status(
                    command.mission_id,
                    MissionStatus.PAUSED,
                    detail="ArduPilot confirmou a pausa da missão." + reason_suffix,
                )
                active.phase = ActivePhase.PAUSED
                self._save_active()
            elif command.command is GatewayCommandType.CONTINUE:
                if active.phase is not ActivePhase.PAUSED:
                    raise UnsafeOperationError("Missão não está pausada para continuar.")
                await self._vehicle.continue_mission()
                resumed_status = (
                    active.last_reported_progress_status
                    if active.last_reported_progress_status
                    in {
                        MissionStatus.DESTINATION_REACHED,
                        MissionStatus.DELIVERY_CONFIRMED,
                        MissionStatus.RETURNING,
                    }
                    else MissionStatus.EXECUTING
                )
                await self._backend.report_status(
                    command.mission_id,
                    resumed_status,
                    detail="ArduPilot confirmou a continuação da missão." + reason_suffix,
                )
                active.phase = ActivePhase.EXECUTING
                self._save_active()
            elif command.command is GatewayCommandType.RTL:
                await self._vehicle.request_rtl()
                await self._backend.report_status(
                    command.mission_id,
                    MissionStatus.RETURNING,
                    detail="Adaptador confirmou a solicitação RTL." + reason_suffix,
                )
                active.last_reported_progress_status = MissionStatus.RETURNING
                active.phase = ActivePhase.EXECUTING
                self._save_active()
                await self._backend.report_event(
                    command.mission_id,
                    event_type="MISSION_RTL_ACCEPTED",
                    severity="WARNING",
                    message=(
                        "Veículo aceitou solicitação RTL; o evento não confirma entrega "
                        "nem conclusão da missão."
                    ),
                    metadata={"reason": command.reason},
                )
            else:
                await self._vehicle.abort()
                await self._backend.report_status(
                    command.mission_id,
                    MissionStatus.ABORTED,
                    detail="Adaptador confirmou abortamento controlado." + reason_suffix,
                )
                self._clear_active()
            await self._backend.acknowledge_command(
                command.id,
                GatewayCommandStatus.COMPLETED,
                detail="Comando aceito pelo adaptador do veículo.",
            )
        except BackendUnavailableError:
            raise
        except GatewayError as exc:
            await self._backend.acknowledge_command(
                command.id, GatewayCommandStatus.FAILED, detail=str(exc)
            )

    async def _process_arm_command(
        self,
        command: GatewayCommand,
        active: ActiveMission,
        health: VehicleHealth,
        *,
        authorization_eligible: bool,
    ) -> None:
        if command.status is GatewayCommandStatus.ACKNOWLEDGED:
            if health.connected and health.heartbeat and health.armed is True:
                await self._publish_arm_confirmation_health(health)
                detail = (
                    "Armamento confirmado por heartbeat após reinício; "
                    "estado reconciliado sem reenvio."
                )
                status = GatewayCommandStatus.COMPLETED
            else:
                detail = (
                    "Resultado anterior de ARM é incerto e armed=true não foi confirmado; "
                    "o gateway não reenviará o comando automaticamente."
                )
                status = GatewayCommandStatus.FAILED
            await self._backend.acknowledge_command(command.id, status, detail=detail)
            return

        requested_at = command.requested_at
        if requested_at.tzinfo is None:
            requested_at = requested_at.replace(tzinfo=UTC)
        if self._now() - requested_at > timedelta(
            seconds=self._settings.gateway_command_max_age_seconds
        ):
            await self._backend.acknowledge_command(
                command.id,
                GatewayCommandStatus.FAILED,
                detail="Comando ARM expirado; solicite uma nova ação administrativa.",
            )
            return

        armable_phases = {
            ActivePhase.VERIFIED_PENDING_REPORT,
            ActivePhase.WAITING_OPERATOR_ARM,
        }
        if (
            active.phase not in armable_phases
            or active.claim.mission.status is not MissionStatus.VERIFIED
        ):
            await self._backend.acknowledge_command(
                command.id,
                GatewayCommandStatus.FAILED,
                detail=(
                    "ARM exige missão VERIFIED na fase local VERIFIED_PENDING_REPORT/"
                    "WAITING_OPERATOR_ARM."
                ),
            )
            return
        if not (
            self._settings.allow_vehicle_arm
            and self._settings.allow_flight_commands
            and self._settings.allow_mission_start
        ):
            await self._backend.acknowledge_command(
                command.id,
                GatewayCommandStatus.FAILED,
                detail=(
                    "ARM exige ALLOW_VEHICLE_ARM, ALLOW_FLIGHT_COMMANDS e "
                    "ALLOW_MISSION_START habilitados."
                ),
            )
            return
        if not health.connected or not health.heartbeat:
            await self._backend.acknowledge_command(
                command.id,
                GatewayCommandStatus.FAILED,
                detail="ARM bloqueado: heartbeat MAVLink válido não está disponível.",
            )
            return

        if health.armed is True:
            await self._backend.acknowledge_command(
                command.id,
                GatewayCommandStatus.ACKNOWLEDGED,
                detail=(
                    "ARM reconciliado com veículo já armado; nenhum comando MAVLink foi enviado."
                ),
            )
            await self._publish_arm_confirmation_health(health)
            await self._backend.acknowledge_command(
                command.id,
                GatewayCommandStatus.COMPLETED,
                detail="Veículo já estava armado; estado reconciliado sem envio MAVLink.",
            )
            return

        preflight = evaluate_preflight(
            health,
            active.claim,
            self._settings,
            now=self._now(),
        )
        if (
            not authorization_eligible
            or not self._mission_matches_vehicle(active.claim.mission)
            or health.source not in {OperationalSource.SITL, OperationalSource.HARDWARE_REAL}
            or (health.flight_mode or "").strip().upper() != "STABILIZE"
            or not preflight.passed
        ):
            failures = list(preflight.failures)
            if not authorization_eligible:
                failures.append("BACKEND_NOT_ELIGIBLE")
            if not self._mission_matches_vehicle(active.claim.mission):
                failures.append("VEHICLE_MISMATCH")
            if health.source not in {OperationalSource.SITL, OperationalSource.HARDWARE_REAL}:
                failures.append("OPERATIONAL_SOURCE_NOT_ALLOWED")
            if (health.flight_mode or "").strip().upper() != "STABILIZE":
                failures.append("ARMING_MODE_NOT_ALLOWED")
            await self._backend.acknowledge_command(
                command.id,
                GatewayCommandStatus.FAILED,
                detail="ARM bloqueado pelo preflight final: " + ", ".join(dict.fromkeys(failures)),
            )
            return

        await self._backend.acknowledge_command(
            command.id,
            GatewayCommandStatus.ACKNOWLEDGED,
            detail="ARM recebido pelo gateway; nenhuma confirmação implica armamento.",
        )

        try:
            arm_result = await self._vehicle.arm_vehicle()
            confirmed_health = await self._vehicle.read_health()
            if confirmed_health.armed is not True:
                raise VehicleTimeoutError(
                    "Adaptador retornou sem heartbeat confirmando armed=true."
                )
            if arm_result.command_sent:
                if (
                    not arm_result.command_acknowledged
                    or not arm_result.armed_heartbeat_confirmed
                    or arm_result.external_state_reconciled
                ):
                    raise UnsafeOperationError(
                        "Adaptador retornou evidência inconsistente para ARM enviado."
                    )
                completion_detail = (
                    "COMMAND_ACK correlacionado e heartbeat novo confirmaram armed=true."
                )
            else:
                if (
                    arm_result.command_acknowledged
                    or not arm_result.armed_heartbeat_confirmed
                    or not arm_result.external_state_reconciled
                ):
                    raise UnsafeOperationError(
                        "Adaptador retornou reconciliação inconsistente de ARM externo."
                    )
                completion_detail = (
                    "Heartbeat mostrou armamento externo durante a preparação; "
                    "estado reconciliado sem enviar ARM e sem alegar COMMAND_ACK."
                )
        except GatewayError as exc:
            await self._backend.acknowledge_command(
                command.id,
                GatewayCommandStatus.FAILED,
                detail=f"ARM não foi confirmado: {exc}",
            )
            return

        await self._publish_arm_confirmation_health(confirmed_health)
        await self._backend.acknowledge_command(
            command.id,
            GatewayCommandStatus.COMPLETED,
            detail=completion_detail,
        )

    async def _publish_arm_confirmation_health(self, health: VehicleHealth) -> None:
        if not health.connected or not health.heartbeat or health.armed is not True:
            raise VehicleTimeoutError(
                "Publicação de ARM exige heartbeat fresco confirmando armed=true."
            )
        heartbeat = await self._backend.heartbeat(health)
        if (
            heartbeat.vehicle.identifier != self._settings.vehicle_identifier
            or heartbeat.vehicle.gateway_id != self._settings.gateway_id
        ):
            raise BackendContractError(
                "Heartbeat pós-armamento retornou identidade de veículo ou gateway diferente."
            )

    async def _claim_and_stage(
        self,
        offered_mission: AuthorizedMission,
        health: VehicleHealth,
        *,
        authorization_eligible: bool,
    ) -> None:
        if not self._settings.allow_mission_upload or not health.connected or not health.heartbeat:
            logger.warning(
                "mission claim blocked by local MAVLink safety gate",
                extra={"gateway_id": self._settings.gateway_id},
            )
            return
        claim: ClaimResponse | None = None
        self._save_claim_intent(offered_mission)
        try:
            claim = await self._backend.claim(offered_mission.id)
            if claim.mission.id != offered_mission.id:
                raise MissionValidationError("Claim retornou uma missão diferente da oferta.")
            if (
                claim.mission.version != offered_mission.version
                or claim.mission.mission_sha256 != offered_mission.mission_sha256
            ):
                raise MissionValidationError("Missão mudou entre a oferta e o claim.")
            if not self._mission_matches_vehicle(claim.mission):
                raise MissionValidationError("Missão não pertence ao veículo conectado.")
            validate_claimed_mission(claim.mission, claim.mission_file, self._settings)
            preflight = evaluate_preflight(health, claim, self._settings, now=self._now())
            if not preflight.passed or not authorization_eligible:
                failures = list(preflight.failures)
                if not authorization_eligible:
                    failures.extend(self._backend_health_failures or ["BACKEND_INELIGIBLE"])
                failures = list(dict.fromkeys(failures))
                await self._backend.report_event(
                    claim.mission.id,
                    event_type="GATEWAY_PREFLIGHT_FAILED",
                    severity="ERROR",
                    message="Gateway bloqueou a missão após o claim.",
                    metadata={"failures": ",".join(failures)},
                )
                await self._backend.report_status(
                    claim.mission.id,
                    MissionStatus.FAILED,
                    detail="Preflight falhou: " + ", ".join(failures),
                )
                self._clear_active()
                return
            self._active = ActiveMission(
                claim=claim,
                phase=ActivePhase.UPLOADING_PENDING_REPORT,
                pending_event_id=uuid4(),
            )
            self._pending_claim = None
            self._save_active()
            await self._continue_active(
                health,
                authorization_eligible=authorization_eligible,
            )
        except BackendUnavailableError:
            raise
        except GatewayError as exc:
            logger.error(
                "mission staging failed",
                extra={"mission_id": str(offered_mission.id)},
                exc_info=True,
            )
            if claim is not None:
                await self._backend.report_event(
                    claim.mission.id,
                    event_type=exc.code,
                    severity="ERROR",
                    message=str(exc),
                )
                await self._backend.report_upload(
                    claim.mission.id, MissionStatus.FAILED, detail=str(exc)
                )
            self._clear_active()

    async def _continue_active(
        self,
        health: VehicleHealth,
        *,
        authorization_eligible: bool,
    ) -> None:
        active = self._active
        if active is None:
            return
        if not self._mission_matches_vehicle(active.claim.mission):
            if not active.binding_failure_reported:
                await self._backend.report_event(
                    active.claim.mission.id,
                    event_type="MISSION_VEHICLE_BINDING_FAILED",
                    severity="ERROR",
                    message="Missão ativa não corresponde ao veículo conectado; ação bloqueada.",
                )
                active.binding_failure_reported = True
                self._save_active()
            return
        if active.binding_failure_reported:
            active.binding_failure_reported = False
            self._save_active()

        if active.phase is ActivePhase.UPLOADING_PENDING_REPORT:
            if not self._settings.allow_mission_upload:
                return
            await self._backend.report_upload(
                active.claim.mission.id,
                MissionStatus.UPLOADING,
                detail="Upload MAVLink será iniciado.",
                event_id=active.pending_event_id,
            )
            active.phase = ActivePhase.UPLOADING
            active.pending_event_id = None
            self._save_active()
            await self._continue_active(
                health,
                authorization_eligible=authorization_eligible,
            )
            return

        if active.phase is ActivePhase.UPLOADING:
            if not self._settings.allow_mission_upload:
                return
            if not health.connected or not health.heartbeat:
                return
            if not authorization_eligible:
                await self._fail_active("Backend bloqueou a elegibilidade antes do upload.")
                return
            preflight = evaluate_preflight(health, active.claim, self._settings, now=self._now())
            if not preflight.passed:
                await self._fail_active(
                    "Preflight mudou antes do upload: " + ", ".join(preflight.failures)
                )
                return
            try:
                active.phase = ActivePhase.UPLOAD_COMMAND_SENT
                active.upload_uncertain_reported = False
                self._save_active()
                result = await self._vehicle.upload_mission(
                    active.claim.mission, active.claim.mission_file
                )
            except GatewayError as exc:
                if not active.upload_uncertain_reported:
                    await self._backend.report_event(
                        active.claim.mission.id,
                        event_type="MISSION_UPLOAD_RESULT_UNCERTAIN",
                        severity="ERROR",
                        message=(
                            f"Não foi possível confirmar o resultado do upload: {exc}. "
                            "O gateway não repetirá o upload automaticamente."
                        ),
                    )
                    active.upload_uncertain_reported = True
                    self._save_active()
                return
            if not result.acknowledged:
                await self._fail_active("Veículo não confirmou e verificou o upload.")
                return
            active.phase = ActivePhase.UPLOADED_PENDING_REPORT
            active.pending_event_id = uuid4()
            active.upload_detail = result.detail
            active.upload_uncertain_reported = False
            self._save_active()
            await self._continue_active(
                health,
                authorization_eligible=authorization_eligible,
            )
            return

        if active.phase is ActivePhase.UPLOAD_COMMAND_SENT:
            if not self._settings.allow_mission_upload:
                return
            if not health.connected or not health.heartbeat:
                return
            try:
                verification = await self._vehicle.verify_mission(active.claim.mission)
            except GatewayError as exc:
                await self._backend.report_event(
                    active.claim.mission.id,
                    event_type="MISSION_UPLOAD_RECOVERY_BLOCKED",
                    severity="ERROR",
                    message=(
                        "O upload anterior ficou sem confirmação e o readback não comprovou "
                        f"o conteúdo: {exc}. O gateway não repetirá o upload automaticamente."
                    ),
                )
                active.phase = ActivePhase.UPLOAD_RECOVERY_BLOCKED
                active.upload_uncertain_reported = True
                self._save_active()
                return
            if not verification.verified:
                await self._backend.report_event(
                    active.claim.mission.id,
                    event_type="MISSION_UPLOAD_RECOVERY_BLOCKED",
                    severity="ERROR",
                    message=(
                        "O upload anterior ficou sem confirmação e o readback divergiu da "
                        "missão autorizada. O gateway não repetirá o upload automaticamente: "
                        f"{verification.detail}"
                    ),
                )
                active.phase = ActivePhase.UPLOAD_RECOVERY_BLOCKED
                active.upload_uncertain_reported = True
                self._save_active()
                return
            active.phase = ActivePhase.RECOVERED_UPLOAD_PENDING_REPORT
            active.pending_event_id = uuid4()
            active.upload_detail = (
                "Upload recuperado sem reenvio: o readback MAVLink corresponde à missão "
                f"autorizada. {verification.detail}"
            )
            active.upload_uncertain_reported = False
            self._save_active()
            await self._continue_active(
                health,
                authorization_eligible=authorization_eligible,
            )
            return

        if active.phase is ActivePhase.UPLOAD_RECOVERY_BLOCKED:
            return

        if active.phase is ActivePhase.RECOVERED_UPLOAD_PENDING_REPORT:
            await self._backend.report_upload(
                active.claim.mission.id,
                MissionStatus.UPLOADED,
                detail=active.upload_detail,
                event_id=active.pending_event_id,
            )
            active.pending_event_id = uuid4()
            active.phase = ActivePhase.VERIFIED_PENDING_REPORT
            active.claim = active.claim.model_copy(
                update={
                    "mission": active.claim.mission.model_copy(
                        update={"status": MissionStatus.VERIFIED}
                    )
                }
            )
            self._save_active()
            await self._continue_active(
                health,
                authorization_eligible=authorization_eligible,
            )
            return

        if active.phase is ActivePhase.UPLOADED_PENDING_REPORT:
            await self._backend.report_upload(
                active.claim.mission.id,
                MissionStatus.UPLOADED,
                detail=active.upload_detail,
                event_id=active.pending_event_id,
            )
            active.pending_event_id = None
            active.phase = ActivePhase.VERIFYING
            self._save_active()
            await self._continue_active(
                health,
                authorization_eligible=authorization_eligible,
            )
            return

        if active.phase is ActivePhase.VERIFYING:
            if not self._settings.allow_mission_upload:
                return
            if not health.connected or not health.heartbeat:
                return
            try:
                verification = await self._vehicle.verify_mission(active.claim.mission)
            except GatewayError as exc:
                if not active.verification_failure_reported:
                    await self._backend.report_event(
                        active.claim.mission.id,
                        event_type="MISSION_VERIFICATION_BLOCKED",
                        severity="ERROR",
                        message=str(exc),
                    )
                    active.verification_failure_reported = True
                    self._save_active()
                return
            if not verification.verified:
                if not active.verification_failure_reported:
                    await self._backend.report_event(
                        active.claim.mission.id,
                        event_type="MISSION_VERIFICATION_FAILED",
                        severity="ERROR",
                        message=verification.detail,
                    )
                    active.verification_failure_reported = True
                    self._save_active()
                return
            active.phase = ActivePhase.VERIFIED_PENDING_REPORT
            active.claim = active.claim.model_copy(
                update={
                    "mission": active.claim.mission.model_copy(
                        update={"status": MissionStatus.VERIFIED}
                    )
                }
            )
            active.pending_event_id = uuid4()
            active.upload_detail = verification.detail
            active.verification_failure_reported = False
            self._save_active()
            await self._continue_active(
                health,
                authorization_eligible=authorization_eligible,
            )
            return

        if active.phase is ActivePhase.VERIFIED_PENDING_REPORT:
            await self._backend.report_upload(
                active.claim.mission.id,
                MissionStatus.VERIFIED,
                detail=active.upload_detail,
                event_id=active.pending_event_id,
            )
            active.pending_event_id = None
            active.phase = ActivePhase.WAITING_OPERATOR_ARM
            self._save_active()
            await self._backend.report_event(
                active.claim.mission.id,
                event_type="MISSION_VERIFIED_WAITING_OPERATOR_ARM",
                severity="WARNING",
                message=(
                    "Missão enviada e verificada. Armamento e início continuam separados: "
                    "cada ação exige seu gate local e comando administrativo explícito."
                ),
            )
            return

        if active.phase is ActivePhase.WAITING_OPERATOR_ARM:
            return

        if active.phase is ActivePhase.PAUSED:
            return

        if active.phase is ActivePhase.START_COMMAND_SENT:
            if not active.start_uncertain_reported:
                await self._backend.report_event(
                    active.claim.mission.id,
                    event_type="MISSION_START_CONFIRMATION_REQUIRED",
                    severity="ERROR",
                    message=(
                        "O comando de início foi enviado sem confirmação persistida; "
                        "o gateway não o repetirá automaticamente."
                    ),
                )
                active.start_uncertain_reported = True
                self._save_active()
            return

        if active.phase is ActivePhase.EXECUTING_PENDING_REPORT:
            await self._backend.report_status(
                active.claim.mission.id,
                MissionStatus.EXECUTING,
                detail="Início confirmado pelo adaptador; nenhum armamento foi automático.",
                event_id=active.pending_event_id,
            )
            active.phase = ActivePhase.EXECUTING
            active.pending_event_id = None
            self._save_active()
            await self._continue_active(
                health,
                authorization_eligible=authorization_eligible,
            )
            return

        await self._continue_executing(active, health)

    async def _start(self, active: ActiveMission) -> None:
        if not self._settings.allow_flight_commands or not self._settings.allow_mission_start:
            return
        active.phase = ActivePhase.START_COMMAND_SENT
        active.pending_event_id = None
        self._save_active()
        try:
            await self._vehicle.start_mission(active.claim.mission)
        except GatewayError as exc:
            if not active.start_uncertain_reported:
                await self._backend.report_event(
                    active.claim.mission.id,
                    event_type="MISSION_START_RESULT_UNCERTAIN",
                    severity="ERROR",
                    message=(
                        f"Não foi possível confirmar o comando de início: {exc}. "
                        "O comando não será repetido automaticamente."
                    ),
                )
                active.start_uncertain_reported = True
                self._save_active()
            raise
        active.phase = ActivePhase.EXECUTING_PENDING_REPORT
        active.pending_event_id = uuid4()
        active.start_uncertain_reported = False
        self._save_active()
        await self._continue_active(
            await self._vehicle.read_health(),
            authorization_eligible=True,
        )

    async def _continue_executing(self, active: ActiveMission, health: VehicleHealth) -> None:
        if active.pending_status is not None:
            await self._flush_pending_status(active)
            if self._active is None:
                return
        if not health.connected or not health.heartbeat:
            if not active.link_loss_reported:
                await self._backend.report_event(
                    active.claim.mission.id,
                    event_type="VEHICLE_LINK_LOST",
                    severity="ERROR",
                    message=(
                        "Heartbeat MAVLink vencido durante a missão. O ArduPilot permanece "
                        "responsável pelos failsafes; telemetria não será fabricada."
                    ),
                )
                active.link_loss_reported = True
                self._save_active()
            return
        if active.link_loss_reported:
            await self._backend.report_event(
                active.claim.mission.id,
                event_type="VEHICLE_LINK_RECOVERED",
                severity="WARNING",
                message="Heartbeat MAVLink voltou após perda de link.",
            )
            active.link_loss_reported = False
            self._save_active()

        try:
            await self._vehicle.synchronize_progress(
                active.claim.mission,
                active.last_reported_progress_status,
            )
            poll = await self._vehicle.poll_mission(active.claim.mission)
        except VehicleTimeoutError as exc:
            if not active.telemetry_stale_reported:
                await self._backend.report_event(
                    active.claim.mission.id,
                    event_type="MISSION_TELEMETRY_STALE",
                    severity="ERROR",
                    message=str(exc),
                )
                active.telemetry_stale_reported = True
                self._save_active()
            return
        except GatewayError as exc:
            await self._backend.report_event(
                active.claim.mission.id,
                event_type="ACTIVE_MISSION_MONITORING_ERROR",
                severity="ERROR",
                message=str(exc),
            )
            return

        if active.telemetry_stale_reported:
            await self._backend.report_event(
                active.claim.mission.id,
                event_type="MISSION_TELEMETRY_RECOVERED",
                severity="WARNING",
                message="Amostras MAVLink atuais voltaram a ser recebidas.",
            )
            active.telemetry_stale_reported = False
            self._save_active()
        progress_prepared = False
        if poll.suggested_status is not None:
            progress_prepared = await self._prepare_suggested_status(active, poll.suggested_status)
        await self._forward_vehicle_events(poll.events)
        vehicle_id = active.claim.mission.vehicle_id
        if vehicle_id is None:
            await self._backend.report_event(
                active.claim.mission.id,
                event_type="MISSION_VEHICLE_BINDING_FAILED",
                severity="ERROR",
                message="Backend não associou vehicle_id após o claim.",
            )
            return
        now = self._now()
        should_persist = (
            self._last_telemetry_report_at is None
            or (now - self._last_telemetry_report_at).total_seconds()
            >= self._settings.telemetry_persist_interval_seconds
        )
        if should_persist:
            await self._backend.report_telemetry(
                active.claim.mission.id, vehicle_id, poll.telemetry
            )
            self._last_telemetry_report_at = now
        if progress_prepared:
            await self._flush_pending_status(active)

    async def _prepare_suggested_status(
        self,
        active: ActiveMission,
        status: MissionStatus,
    ) -> bool:
        if status in PROGRESS_STATUSES:
            suggested_index = PROGRESS_STATUSES.index(status)
            last_index = (
                PROGRESS_STATUSES.index(active.last_reported_progress_status)
                if active.last_reported_progress_status in PROGRESS_STATUSES
                else -1
            )
            if suggested_index <= last_index:
                return False
            if suggested_index != last_index + 1:
                await self._backend.report_event(
                    active.claim.mission.id,
                    event_type="MAVLINK_PROGRESS_OUT_OF_ORDER",
                    severity="ERROR",
                    message=(
                        f"Transição {status.value} foi bloqueada porque a etapa anterior "
                        "ainda não foi confirmada."
                    ),
                    metadata={
                        "suggested_status": status.value,
                        "last_reported_status": (
                            active.last_reported_progress_status.value
                            if active.last_reported_progress_status is not None
                            else None
                        ),
                    },
                )
                return False
        active.pending_status = status
        active.pending_status_event_id = uuid4()
        self._save_active()
        return True

    async def _flush_pending_status(self, active: ActiveMission) -> None:
        status = active.pending_status
        if status is None:
            return
        await self._backend.report_status(
            active.claim.mission.id,
            status,
            detail=PROGRESS_DETAILS.get(
                status,
                "Transição derivada de evento explícito do adaptador do veículo.",
            ),
            event_id=active.pending_status_event_id,
        )
        active.pending_status = None
        active.pending_status_event_id = None
        if status in PROGRESS_STATUSES:
            active.last_reported_progress_status = status
        if status in {MissionStatus.COMPLETED, MissionStatus.ABORTED, MissionStatus.FAILED}:
            self._clear_active()
        else:
            self._save_active()

    async def _fail_active(self, detail: str) -> None:
        active = self._active
        if active is None:
            return
        await self._backend.report_event(
            active.claim.mission.id,
            event_type="ACTIVE_MISSION_FAILED",
            severity="ERROR",
            message=detail,
        )
        await self._backend.report_status(
            active.claim.mission.id, MissionStatus.FAILED, detail=detail
        )
        self._clear_active()
