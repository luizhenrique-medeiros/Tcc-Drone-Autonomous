from datetime import UTC, datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import OperationalSource
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.bench_arm.models import BenchArmRequest
from app.modules.system_events.service import record_event
from app.modules.vehicles.models import Vehicle, VehicleHealthSnapshot
from app.modules.vehicles.service import health_is_stale

REQUEST_TTL = timedelta(seconds=30)
RESULT_WINDOW = timedelta(seconds=30)
BENCH_MODE = "px4_bench_arm"


class ArmConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmed: StrictBool
    session_id: UUID

    @model_validator(mode="after")
    def validate_confirmation(self) -> "ArmConfirmation":
        if self.confirmed is not True:
            raise ValueError("Confirme explicitamente a solicitação de ARM")
        return self


class ArmClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vehicle_id: UUID
    session_id: UUID


class ArmReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transmitted: bool | None
    ack_result: int | None = Field(ge=0, le=255)
    confirmed_snapshot_id: UUID | None = None
    detail: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_evidence(self) -> "ArmReport":
        if self.ack_result is not None and self.transmitted is not True:
            raise ValueError("ACK exige transmissão registrada")
        if self.confirmed_snapshot_id is not None and self.ack_result != 0:
            raise ValueError("Confirmação exige ACK de aceitação")
        return self


def utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def require_enabled(settings: Settings) -> None:
    if not settings.px4_bench_arm_enabled:
        raise NotFoundError("Ensaio físico de ARM indisponível")


def configured_vehicle(
    session: Session, settings: Settings, *, lock: bool = False
) -> Vehicle | None:
    query = select(Vehicle).where(
        Vehicle.identifier == settings.px4_bench_arm_vehicle_identifier,
        Vehicle.gateway_id == settings.gateway_id,
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    return session.scalar(query)


def current_snapshot(session: Session, vehicle: Vehicle) -> VehicleHealthSnapshot | None:
    return session.scalar(
        select(VehicleHealthSnapshot)
        .where(VehicleHealthSnapshot.vehicle_id == vehicle.id)
        .order_by(VehicleHealthSnapshot.received_at.desc(), VehicleHealthSnapshot.id.desc())
        .limit(1)
    )


def bench_snapshot(snapshot: VehicleHealthSnapshot) -> bool:
    return (
        snapshot.source == OperationalSource.HARDWARE_REAL
        and snapshot.connection_mode == BENCH_MODE
        and snapshot.bench_arm_session_id is not None
        and snapshot.vehicle_arm_enabled is True
        and snapshot.connected
        and snapshot.heartbeat
        and snapshot.mavlink_system_id is not None
        and snapshot.mavlink_component_id is not None
        and snapshot.mavlink_system_id > 0
        and snapshot.mavlink_component_id > 0
        and snapshot.last_heartbeat_at is not None
    )


def eligible(vehicle: Vehicle, snapshot: VehicleHealthSnapshot | None, settings: Settings) -> bool:
    return (
        vehicle.autopilot_system.upper() == "PX4"
        and vehicle.operational_source == OperationalSource.HARDWARE_REAL
        and snapshot is not None
        and bench_snapshot(snapshot)
        and not health_is_stale(snapshot, settings)
    )


def latest_request(session: Session, vehicle_id: UUID) -> BenchArmRequest | None:
    return session.scalar(
        select(BenchArmRequest)
        .where(BenchArmRequest.vehicle_id == vehicle_id)
        .order_by(BenchArmRequest.requested_at.desc(), BenchArmRequest.id.desc())
        .limit(1)
    )


def request_status(command: BenchArmRequest, active_session_id: UUID | None, now: datetime) -> str:
    if command.completed_at:
        if command.confirmed_heartbeat_at:
            return "CONFIRMED"
        if command.ack_result not in (None, 0):
            return "REJECTED"
        return "NOT_SENT" if command.transmitted is False else "UNCONFIRMED"
    if command.claimed_at:
        if now >= utc(command.claimed_at) + RESULT_WINDOW:
            return "UNCONFIRMED"
        return "DISPATCHING"
    if now >= utc(command.expires_at) or command.session_id != active_session_id:
        return "EXPIRED"
    return "PENDING"


def view_command(command: BenchArmRequest, active_session_id: UUID | None) -> dict[str, object]:
    return {
        "id": str(command.id),
        "vehicle_id": str(command.vehicle_id),
        "status": request_status(command, active_session_id, datetime.now(UTC)),
        "requested_at": utc(command.requested_at).isoformat(),
        "expires_at": utc(command.expires_at).isoformat(),
        "transmitted": command.transmitted,
        "ack_result": command.ack_result,
        "confirmed_heartbeat_at": (
            utc(command.confirmed_heartbeat_at).isoformat()
            if command.confirmed_heartbeat_at
            else None
        ),
        "detail": command.detail,
    }


def register_arm(
    session: Session, settings: Settings, actor_id: UUID, vehicle_id: UUID, payload: ArmConfirmation
) -> dict[str, object]:
    vehicle = configured_vehicle(session, settings, lock=True)
    if vehicle is None or vehicle.id != vehicle_id:
        raise NotFoundError("Veículo de ensaio não encontrado")
    snapshot = current_snapshot(session, vehicle)
    if (
        snapshot is None
        or not eligible(vehicle, snapshot, settings)
        or snapshot.bench_arm_session_id != payload.session_id
    ):
        raise ConflictError("A conexão de ensaio mudou ou está indisponível")
    now = datetime.now(UTC)
    latest = latest_request(session, vehicle.id)
    if latest and request_status(latest, payload.session_id, now) in {"PENDING", "DISPATCHING"}:
        raise ConflictError("Já existe uma solicitação de ARM em andamento")
    command = BenchArmRequest(
        vehicle_id=vehicle.id,
        requested_by_id=actor_id,
        gateway_id=vehicle.gateway_id,
        session_id=payload.session_id,
        target_system=snapshot.mavlink_system_id,
        target_component=snapshot.mavlink_component_id,
        requested_at=now,
        expires_at=now + REQUEST_TTL,
    )
    session.add(command)
    session.flush()
    record_event(
        session,
        actor_type="ADMIN",
        actor_user_id=actor_id,
        vehicle_id=vehicle.id,
        event_type="BENCH_ARM_REQUESTED",
        message="Solicitação de ARM normal de bancada registrada",
        metadata={"command_id": str(command.id), "gateway_id": vehicle.gateway_id},
    )
    return view_command(command, payload.session_id)


def claim_arm(
    session: Session, settings: Settings, gateway_id: str, payload: ArmClaim
) -> dict[str, object] | None:
    vehicle = configured_vehicle(session, settings, lock=True)
    if vehicle is None or vehicle.id != payload.vehicle_id or vehicle.gateway_id != gateway_id:
        raise NotFoundError("Veículo de ensaio não encontrado")
    snapshot = current_snapshot(session, vehicle)
    command = latest_request(session, vehicle.id)
    now = datetime.now(UTC)
    if (
        command is None
        or snapshot is None
        or not eligible(vehicle, snapshot, settings)
        or snapshot.bench_arm_session_id != payload.session_id
        or request_status(command, payload.session_id, now) != "PENDING"
        or command.gateway_id != gateway_id
        or snapshot.mavlink_system_id != command.target_system
        or snapshot.mavlink_component_id != command.target_component
    ):
        return None
    command.claimed_at = now
    record_event(
        session,
        actor_type="GATEWAY",
        vehicle_id=vehicle.id,
        event_type="BENCH_ARM_CLAIMED",
        message="Solicitação reservada pelo gateway de bancada",
        metadata={"command_id": str(command.id), "gateway_id": gateway_id},
    )
    session.commit()
    return {
        "id": str(command.id),
        "vehicle_id": str(command.vehicle_id),
        "session_id": str(command.session_id),
        "target_system": command.target_system,
        "target_component": command.target_component,
        "expires_at": utc(command.expires_at).isoformat(),
    }


def report_arm(session: Session, gateway_id: str, command_id: UUID, report: ArmReport) -> None:
    command = session.scalar(
        select(BenchArmRequest).where(BenchArmRequest.id == command_id).with_for_update()
    )
    if command is None or command.gateway_id != gateway_id:
        raise NotFoundError("Solicitação de ensaio não encontrada")
    if command.claimed_at is None:
        raise ConflictError("A solicitação ainda não foi reservada")
    saved = (command.transmitted, command.ack_result, command.confirmed_snapshot_id, command.detail)
    reported = (report.transmitted, report.ack_result, report.confirmed_snapshot_id, report.detail)
    if command.completed_at:
        if saved != reported:
            raise ConflictError("O resultado da solicitação já foi registrado")
        return

    if report.confirmed_snapshot_id:
        evidence = session.get(VehicleHealthSnapshot, report.confirmed_snapshot_id)
        if (
            evidence is None
            or evidence.vehicle_id != command.vehicle_id
            or not bench_snapshot(evidence)
            or evidence.bench_arm_session_id != command.session_id
            or evidence.mavlink_system_id != command.target_system
            or evidence.mavlink_component_id != command.target_component
            or evidence.armed is not True
            or evidence.last_heartbeat_at is None
            or utc(evidence.last_heartbeat_at) <= utc(command.claimed_at)
            or utc(evidence.received_at) > utc(command.claimed_at) + RESULT_WINDOW
        ):
            raise ConflictError("Heartbeat de confirmação não corresponde ao ensaio")
        command.confirmed_heartbeat_at = evidence.last_heartbeat_at
    command.transmitted, command.ack_result, command.confirmed_snapshot_id, command.detail = (
        reported
    )
    command.completed_at = datetime.now(UTC)
    record_event(
        session,
        actor_type="GATEWAY",
        vehicle_id=command.vehicle_id,
        event_type="BENCH_ARM_RESULT",
        message=report.detail,
        metadata={
            "command_id": str(command.id),
            "gateway_id": gateway_id,
            "transmitted": report.transmitted,
            "ack_result": report.ack_result,
            "armed_confirmed": command.confirmed_heartbeat_at is not None,
        },
    )
    session.commit()
