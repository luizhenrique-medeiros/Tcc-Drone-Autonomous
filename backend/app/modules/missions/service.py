from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.enums import (
    AuthorizationStatus,
    EventSeverity,
    GatewayCommandStatus,
    GatewayCommandType,
    MissionStatus,
    OrderStatus,
)
from app.core.exceptions import ConflictError, InvalidStateError, NotFoundError
from app.database.types import point_ewkt
from app.modules.approvals.models import FlightAuthorization
from app.modules.delivery_points.models import DeliveryPoint
from app.modules.missions.models import GatewayCommand, Mission, MissionWaypoint
from app.modules.missions.schemas import (
    AdminMissionRead,
    FlightAuthorizationCreate,
    GatewayCommandAck,
    MissionAuthorizationRead,
    VehicleArmRequest,
)
from app.modules.orders.models import Order
from app.modules.system_events.models import SystemEvent
from app.modules.system_events.service import record_event
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle, VehicleHealthSnapshot
from app.modules.vehicles.service import health_failures, health_is_stale, latest_health


def _authorization_to_read(
    authorization: FlightAuthorization, administrator_name: str
) -> MissionAuthorizationRead:
    return MissionAuthorizationRead(
        id=authorization.id,
        administrator_id=authorization.administrator_id,
        administrator_name=administrator_name,
        operator_name=authorization.operator_name,
        status=authorization.status,
        mission_version=authorization.mission_version,
        issued_at=authorization.issued_at,
        expires_at=authorization.expires_at,
        used_at=authorization.used_at,
    )


def admin_missions_to_read(session: Session, missions: list[Mission]) -> list[AdminMissionRead]:
    if not missions:
        return []
    mission_ids = [mission.id for mission in missions]
    latest_by_mission: dict[UUID, MissionAuthorizationRead] = {}
    authorization_rows = session.execute(
        select(FlightAuthorization, User.name)
        .join(User, User.id == FlightAuthorization.administrator_id)
        .where(FlightAuthorization.mission_id.in_(mission_ids))
        .order_by(
            FlightAuthorization.mission_id,
            FlightAuthorization.issued_at.desc(),
            FlightAuthorization.id.desc(),
        )
    )
    for authorization, administrator_name in authorization_rows:
        if authorization.mission_id not in latest_by_mission:
            latest_by_mission[authorization.mission_id] = _authorization_to_read(
                authorization, administrator_name
            )

    return [
        AdminMissionRead.model_validate(mission).model_copy(
            update={"authorization": latest_by_mission.get(mission.id)}
        )
        for mission in missions
    ]


def admin_mission_to_read(session: Session, mission: Mission) -> AdminMissionRead:
    return admin_missions_to_read(session, [mission])[0]


def _waypoint(
    sequence: int,
    command: int,
    latitude: Decimal,
    longitude: Decimal,
    altitude: Decimal,
    label: str,
    *,
    current: int = 0,
    param1: float = 0,
) -> MissionWaypoint:
    return MissionWaypoint(
        sequence=sequence,
        command=command,
        frame=3,
        current=current,
        autocontinue=1,
        param1=param1,
        param2=0,
        param3=0,
        param4=0,
        latitude=latitude,
        longitude=longitude,
        altitude_m=altitude,
        label=label,
    )


def _mission_file(waypoints: list[MissionWaypoint]) -> str:
    lines = ["QGC WPL 110"]
    for waypoint in waypoints:
        lines.append(
            "\t".join(
                (
                    str(waypoint.sequence),
                    str(waypoint.current),
                    str(waypoint.frame),
                    str(waypoint.command),
                    f"{waypoint.param1:.6f}",
                    f"{waypoint.param2:.6f}",
                    f"{waypoint.param3:.6f}",
                    f"{waypoint.param4:.6f}",
                    f"{waypoint.latitude:.7f}",
                    f"{waypoint.longitude:.7f}",
                    f"{waypoint.altitude_m:.2f}",
                    str(waypoint.autocontinue),
                )
            )
        )
    return "\n".join(lines) + "\n"


def prepare_mission(session: Session, order: Order, admin: User, settings: Settings) -> Mission:
    if order.status != OrderStatus.APPROVED:
        raise InvalidStateError("A missão só pode ser preparada para um pedido aprovado")
    existing = session.scalar(select(Mission).where(Mission.order_id == order.id))
    if existing:
        raise ConflictError("O pedido já possui uma missão")
    point = session.get(DeliveryPoint, order.delivery_point_id)
    if not point:
        raise NotFoundError("Ponto de entrega do pedido não encontrado")
    order.status = OrderStatus.MISSION_PREPARING
    origin_lat = Decimal(str(settings.maps_default_latitude))
    origin_lon = Decimal(str(settings.maps_default_longitude))
    destination_lat = point.final_latitude
    destination_lon = point.final_longitude
    altitude = Decimal(str(settings.default_takeoff_altitude_m))
    waypoints = [
        _waypoint(0, 16, origin_lat, origin_lon, Decimal("0"), "Origem", current=1),
        _waypoint(1, 22, origin_lat, origin_lon, altitude, "Decolagem"),
        _waypoint(2, 16, destination_lat, destination_lon, altitude, "Destino"),
        _waypoint(
            3,
            19,
            destination_lat,
            destination_lon,
            altitude,
            "Espera para entrega",
            param1=5,
        ),
        _waypoint(4, 211, destination_lat, destination_lon, altitude, "Entrega"),
        _waypoint(5, 16, origin_lat, origin_lon, altitude, "Retorno"),
        _waypoint(6, 21, origin_lat, origin_lon, Decimal("0"), "Pouso"),
    ]
    mission_file = _mission_file(waypoints)
    mission = Mission(
        order_id=order.id,
        status=MissionStatus.GENERATED,
        origin_latitude=origin_lat,
        origin_longitude=origin_lon,
        origin=point_ewkt(float(origin_lat), float(origin_lon)),
        destination_latitude=destination_lat,
        destination_longitude=destination_lon,
        destination=point_ewkt(float(destination_lat), float(destination_lon)),
        takeoff_altitude_m=altitude,
        estimated_distance_m=point.distance_from_base_m,
        mission_file=mission_file,
        mission_sha256=hashlib.sha256(mission_file.encode()).hexdigest(),
        version=1,
        waypoints=waypoints,
    )
    session.add(mission)
    session.flush()
    order.status = OrderStatus.MISSION_READY
    record_event(
        session,
        actor_type="ADMIN",
        actor_user_id=admin.id,
        order_id=order.id,
        mission_id=mission.id,
        event_type="MISSION_GENERATED",
        message="Missão e arquivo Mission Planner gerados",
        metadata={"version": 1, "sha256": mission.mission_sha256},
    )
    session.commit()
    session.refresh(mission)
    return mission


def export_mission(session: Session, mission: Mission, admin: User) -> str:
    if mission.status in {MissionStatus.GENERATED, MissionStatus.EXPORTED_TO_MISSION_PLANNER}:
        mission.status = MissionStatus.EXPORTED_TO_MISSION_PLANNER
        mission.exported_at = datetime.now(UTC)
        record_event(
            session,
            actor_type="ADMIN",
            actor_user_id=admin.id,
            order_id=mission.order_id,
            mission_id=mission.id,
            event_type="MISSION_EXPORTED",
            message="Arquivo compatível com Mission Planner exportado",
            metadata={"version": mission.version, "sha256": mission.mission_sha256},
        )
        session.commit()
    elif mission.status not in {
        MissionStatus.UNDER_REVIEW,
        MissionStatus.READY_FOR_AUTHORIZATION,
    }:
        raise InvalidStateError("Esta missão não pode ser exportada no estado atual")
    return mission.mission_file


def mark_under_review(session: Session, mission: Mission, admin: User) -> Mission:
    if mission.status not in {
        MissionStatus.GENERATED,
        MissionStatus.EXPORTED_TO_MISSION_PLANNER,
    }:
        raise InvalidStateError("A missão não está disponível para revisão")
    mission.status = MissionStatus.UNDER_REVIEW
    record_event(
        session,
        actor_type="ADMIN",
        actor_user_id=admin.id,
        order_id=mission.order_id,
        mission_id=mission.id,
        event_type="MISSION_REVIEW_STARTED",
        message="Revisão da rota no Mission Planner iniciada",
    )
    session.commit()
    session.refresh(mission)
    return mission


def mark_reviewed(session: Session, mission: Mission, admin: User, notes: str | None) -> Mission:
    if mission.status != MissionStatus.UNDER_REVIEW:
        raise InvalidStateError("A missão precisa estar em revisão")
    mission.status = MissionStatus.READY_FOR_AUTHORIZATION
    mission.reviewed_by_id = admin.id
    mission.reviewed_at = datetime.now(UTC)
    mission.review_notes = notes
    order = session.get(Order, mission.order_id)
    if not order:
        raise NotFoundError("Pedido da missão não encontrado")
    order.status = OrderStatus.WAITING_FLIGHT_AUTHORIZATION
    record_event(
        session,
        actor_type="ADMIN",
        actor_user_id=admin.id,
        order_id=mission.order_id,
        mission_id=mission.id,
        event_type="MISSION_REVIEWED",
        message="Missão revisada; ainda requer autorização de voo separada",
    )
    session.commit()
    session.refresh(mission)
    return mission


def authorize_flight(
    session: Session,
    mission: Mission,
    admin: User,
    payload: FlightAuthorizationCreate,
    settings: Settings,
    *,
    commit: bool = True,
) -> FlightAuthorization:
    locked_mission = session.scalar(
        select(Mission)
        .where(Mission.id == mission.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not locked_mission:
        raise NotFoundError("Missão não encontrada")
    mission = locked_mission
    if mission.status != MissionStatus.READY_FOR_AUTHORIZATION:
        raise InvalidStateError("A missão ainda não está pronta para autorização")
    if not payload.controlled_area_confirmed:
        raise ConflictError("A área controlada deve ser confirmada explicitamente")
    checklist = payload.checklist.model_dump()
    failed_items = [name for name, passed in checklist.items() if not passed]
    if failed_items:
        raise ConflictError(
            "Todos os itens do checklist devem estar aprovados",
            fields={name: "required" for name in failed_items},
        )
    snapshot = latest_health(session, payload.vehicle_id)
    failures = health_failures(snapshot, settings)
    if failures:
        raise ConflictError(
            "O estado real do veículo não permite autorizar o voo",
            fields={"preflight": ",".join(failures)},
        )
    active = session.scalar(
        select(FlightAuthorization).where(
            FlightAuthorization.mission_id == mission.id,
            FlightAuthorization.status == AuthorizationStatus.ACTIVE,
        )
    )
    if active:
        raise ConflictError("A missão já possui autorização ativa")
    now = datetime.now(UTC)
    authorization = FlightAuthorization(
        mission_id=mission.id,
        administrator_id=admin.id,
        vehicle_health_snapshot_id=snapshot.id,
        mission_version=mission.version,
        mission_sha256=mission.mission_sha256,
        checklist=checklist,
        controlled_area_confirmed=True,
        operator_name=payload.operator_name,
        issued_at=now,
        expires_at=now + timedelta(seconds=settings.flight_authorization_ttl_seconds),
    )
    mission.vehicle_id = payload.vehicle_id
    mission.status = MissionStatus.AUTHORIZED
    session.add(authorization)
    session.flush()
    record_event(
        session,
        actor_type="ADMIN",
        actor_user_id=admin.id,
        order_id=mission.order_id,
        mission_id=mission.id,
        vehicle_id=payload.vehicle_id,
        event_type="FLIGHT_AUTHORIZED",
        message="Autorização de voo de uso único emitida",
        metadata={
            "authorization_id": str(authorization.id),
            "expires_at": authorization.expires_at.isoformat(),
            "operator_name": payload.operator_name,
        },
    )
    session.flush()
    if commit:
        session.commit()
        session.refresh(authorization)
    return authorization


def _invalidate_authorization(
    session: Session,
    mission: Mission,
    authorization: FlightAuthorization,
    *,
    status: AuthorizationStatus,
    reason: str,
    message: str,
) -> None:
    authorization.status = status
    mission.status = MissionStatus.READY_FOR_AUTHORIZATION
    record_event(
        session,
        actor_type="SYSTEM",
        order_id=mission.order_id,
        mission_id=mission.id,
        vehicle_id=mission.vehicle_id,
        event_type=(
            "FLIGHT_AUTHORIZATION_EXPIRED"
            if status == AuthorizationStatus.EXPIRED
            else "FLIGHT_AUTHORIZATION_REVOKED"
        ),
        severity=EventSeverity.WARNING,
        message=message,
        metadata={
            "authorization_id": str(authorization.id),
            "reason": reason,
        },
    )
    session.commit()


def active_authorization(session: Session, mission: Mission) -> FlightAuthorization:
    authorization = session.scalar(
        select(FlightAuthorization)
        .where(
            FlightAuthorization.mission_id == mission.id,
            FlightAuthorization.status == AuthorizationStatus.ACTIVE,
        )
        .order_by(FlightAuthorization.issued_at.desc())
        .limit(1)
    )
    if not authorization:
        raise ConflictError("A missão não possui autorização ativa")
    expires_at = authorization.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        _invalidate_authorization(
            session,
            mission,
            authorization,
            status=AuthorizationStatus.EXPIRED,
            reason="TTL_EXPIRED",
            message="Autorização de voo expirada antes do uso",
        )
        raise ConflictError("A autorização de voo expirou")
    if authorization.mission_version != mission.version:
        _invalidate_authorization(
            session,
            mission,
            authorization,
            status=AuthorizationStatus.REVOKED,
            reason="MISSION_VERSION_CHANGED",
            message="Autorização revogada porque a versão da missão mudou",
        )
        raise ConflictError("A missão mudou após a autorização")
    if authorization.mission_sha256 != mission.mission_sha256:
        _invalidate_authorization(
            session,
            mission,
            authorization,
            status=AuthorizationStatus.REVOKED,
            reason="MISSION_FILE_CHANGED",
            message="Autorização revogada porque o artefato da missão mudou",
        )
        raise ConflictError("O arquivo da missão mudou após a autorização")
    return authorization


def claim_mission(
    session: Session, mission: Mission, gateway_id: str, settings: Settings
) -> FlightAuthorization:
    locked_mission = session.scalar(
        select(Mission)
        .where(Mission.id == mission.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not locked_mission:
        raise NotFoundError("Missão não encontrada")
    mission = locked_mission
    if mission.status == MissionStatus.UPLOADING and mission.claimed_by_gateway == gateway_id:
        authorization = session.scalar(
            select(FlightAuthorization)
            .where(FlightAuthorization.mission_id == mission.id)
            .order_by(FlightAuthorization.issued_at.desc())
            .limit(1)
        )
        if not authorization:
            raise ConflictError("Claim existente sem autorização")
        return authorization
    if mission.status != MissionStatus.AUTHORIZED:
        raise InvalidStateError("A missão não está autorizada para claim")
    vehicle = session.get(Vehicle, mission.vehicle_id)
    if not vehicle or vehicle.gateway_id != gateway_id:
        raise ConflictError("O gateway não está vinculado ao veículo autorizado")
    authorization = active_authorization(session, mission)
    snapshot_at_authorization = session.get(
        VehicleHealthSnapshot, authorization.vehicle_health_snapshot_id
    )
    current_snapshot = latest_health(session, mission.vehicle_id)
    if not snapshot_at_authorization:
        _invalidate_authorization(
            session,
            mission,
            authorization,
            status=AuthorizationStatus.REVOKED,
            reason="AUTHORIZATION_SNAPSHOT_MISSING",
            message="Autorização revogada porque o snapshot original não está disponível",
        )
        raise ConflictError("O snapshot usado na autorização não está disponível")
    failures = health_failures(current_snapshot, settings)
    if failures:
        _invalidate_authorization(
            session,
            mission,
            authorization,
            status=AuthorizationStatus.REVOKED,
            reason="HEALTH_CHECK_FAILED",
            message="Autorização revogada por falha de saúde antes do claim",
        )
        raise ConflictError(
            "O veículo falhou nas verificações antes do claim",
            fields={"preflight": ",".join(failures)},
        )
    now = datetime.now(UTC)
    authorization.status = AuthorizationStatus.CONSUMED
    authorization.used_at = now
    mission.claimed_by_gateway = gateway_id
    mission.claimed_at = now
    mission.status = MissionStatus.UPLOADING
    order = session.get(Order, mission.order_id)
    if order:
        order.status = OrderStatus.MISSION_UPLOADING
    record_event(
        session,
        actor_type="GATEWAY",
        order_id=mission.order_id,
        mission_id=mission.id,
        vehicle_id=mission.vehicle_id,
        event_type="MISSION_CLAIMED",
        message="Gateway consumiu a autorização de uso único",
        metadata={"gateway_id": gateway_id, "authorization_id": str(authorization.id)},
    )
    session.commit()
    session.refresh(mission)
    return authorization


GATEWAY_TRANSITIONS: dict[MissionStatus, set[MissionStatus]] = {
    MissionStatus.UPLOADING: {
        MissionStatus.UPLOADED,
        MissionStatus.ABORTED,
        MissionStatus.FAILED,
    },
    MissionStatus.UPLOADED: {
        MissionStatus.VERIFIED,
        MissionStatus.ABORTED,
        MissionStatus.FAILED,
    },
    MissionStatus.VERIFIED: {
        MissionStatus.EXECUTING,
        MissionStatus.ABORTED,
        MissionStatus.FAILED,
    },
    MissionStatus.EXECUTING: {
        MissionStatus.PAUSED,
        MissionStatus.DESTINATION_REACHED,
        MissionStatus.RETURNING,
        MissionStatus.ABORTED,
        MissionStatus.FAILED,
    },
    MissionStatus.DESTINATION_REACHED: {
        MissionStatus.PAUSED,
        MissionStatus.DELIVERY_CONFIRMED,
        MissionStatus.RETURNING,
        MissionStatus.ABORTED,
        MissionStatus.FAILED,
    },
    MissionStatus.DELIVERY_CONFIRMED: {
        MissionStatus.PAUSED,
        MissionStatus.RETURNING,
        MissionStatus.ABORTED,
        MissionStatus.FAILED,
    },
    MissionStatus.RETURNING: {
        MissionStatus.PAUSED,
        MissionStatus.COMPLETED,
        MissionStatus.ABORTED,
        MissionStatus.FAILED,
    },
    MissionStatus.PAUSED: {
        MissionStatus.EXECUTING,
        MissionStatus.DESTINATION_REACHED,
        MissionStatus.DELIVERY_CONFIRMED,
        MissionStatus.RETURNING,
        MissionStatus.ABORTED,
        MissionStatus.FAILED,
    },
}


ORDER_STATUS_FROM_MISSION: dict[MissionStatus, OrderStatus] = {
    MissionStatus.UPLOADING: OrderStatus.MISSION_UPLOADING,
    MissionStatus.UPLOADED: OrderStatus.MISSION_UPLOADING,
    MissionStatus.VERIFIED: OrderStatus.MISSION_UPLOADING,
    MissionStatus.EXECUTING: OrderStatus.IN_TRANSIT,
    MissionStatus.DESTINATION_REACHED: OrderStatus.AT_DESTINATION,
    MissionStatus.DELIVERY_CONFIRMED: OrderStatus.DELIVERED,
    MissionStatus.RETURNING: OrderStatus.RETURNING,
    MissionStatus.COMPLETED: OrderStatus.COMPLETED,
    MissionStatus.ABORTED: OrderStatus.FAILED,
    MissionStatus.FAILED: OrderStatus.FAILED,
}


def apply_gateway_status(
    session: Session,
    mission: Mission,
    status: MissionStatus,
    event_id: str,
    detail: str | None,
) -> tuple[Mission, bool]:
    _event, created = record_event(
        session,
        event_id=event_id,
        actor_type="GATEWAY",
        order_id=mission.order_id,
        mission_id=mission.id,
        vehicle_id=mission.vehicle_id,
        event_type=f"MISSION_{status.value}",
        message=detail or f"Gateway informou estado {status.value}",
        severity=(
            EventSeverity.ERROR
            if status in {MissionStatus.ABORTED, MissionStatus.FAILED}
            else EventSeverity.INFO
        ),
    )
    if not created:
        return mission, False
    if status == mission.status:
        session.commit()
        return mission, True
    allowed = GATEWAY_TRANSITIONS.get(mission.status, set())
    if status not in allowed:
        session.rollback()
        raise InvalidStateError(
            f"Transição de {mission.status.value} para {status.value} não permitida"
        )
    mission.status = status
    order = session.get(Order, mission.order_id)
    if order and status in ORDER_STATUS_FROM_MISSION:
        order.status = ORDER_STATUS_FROM_MISSION[status]
        if status == MissionStatus.COMPLETED:
            order.completed_at = datetime.now(UTC)
    session.commit()
    session.refresh(mission)
    return mission, True


def request_safety_action(
    session: Session,
    mission: Mission,
    admin: User,
    action: str,
    reason: str | None = None,
    settings: Settings | None = None,
    *,
    commit: bool = True,
) -> Mission:
    command_type = GatewayCommandType(action)
    if command_type == GatewayCommandType.ARM:
        raise InvalidStateError("O armamento exige o fluxo dedicado e suas confirmações")
    locked_mission = session.scalar(
        select(Mission)
        .where(Mission.id == mission.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not locked_mission:
        raise NotFoundError("Missão não encontrada")
    mission = locked_mission
    allowed_states_by_command = {
        GatewayCommandType.START: {MissionStatus.VERIFIED},
        GatewayCommandType.PAUSE: {
            MissionStatus.EXECUTING,
            MissionStatus.DESTINATION_REACHED,
            MissionStatus.DELIVERY_CONFIRMED,
            MissionStatus.RETURNING,
        },
        GatewayCommandType.CONTINUE: {MissionStatus.PAUSED},
        GatewayCommandType.ABORT: {
            MissionStatus.UPLOADING,
            MissionStatus.UPLOADED,
            MissionStatus.VERIFIED,
            MissionStatus.EXECUTING,
            MissionStatus.PAUSED,
            MissionStatus.DESTINATION_REACHED,
            MissionStatus.DELIVERY_CONFIRMED,
            MissionStatus.RETURNING,
        },
        GatewayCommandType.RTL: {
            MissionStatus.EXECUTING,
            MissionStatus.PAUSED,
            MissionStatus.DESTINATION_REACHED,
            MissionStatus.DELIVERY_CONFIRMED,
            MissionStatus.RETURNING,
        },
    }
    allowed_states = allowed_states_by_command[command_type]
    if mission.status not in allowed_states:
        raise InvalidStateError("A ação de segurança não é válida para o estado atual")
    open_commands = list(
        session.scalars(
            select(GatewayCommand)
            .where(
                GatewayCommand.mission_id == mission.id,
                GatewayCommand.status.in_(
                    {GatewayCommandStatus.PENDING, GatewayCommandStatus.ACKNOWLEDGED}
                ),
            )
            .order_by(GatewayCommand.requested_at)
            .with_for_update()
        )
    )
    if command_type == GatewayCommandType.ABORT:
        acknowledged_arm = next(
            (
                command
                for command in open_commands
                if command.command == GatewayCommandType.ARM
                and command.status == GatewayCommandStatus.ACKNOWLEDGED
            ),
            None,
        )
        if acknowledged_arm:
            raise ConflictError(
                "ABORT bloqueado: o resultado físico do ARM reconhecido ainda é incerto"
            )
        unrelated = [
            command
            for command in open_commands
            if command.command not in {GatewayCommandType.ARM, GatewayCommandType.ABORT}
        ]
        if unrelated:
            raise ConflictError("A missão já possui outro comando crítico em andamento")
        now = datetime.now(UTC)
        for pending_arm in (
            command
            for command in open_commands
            if command.command == GatewayCommandType.ARM
            and command.status == GatewayCommandStatus.PENDING
        ):
            pending_arm.status = GatewayCommandStatus.FAILED
            pending_arm.completed_at = now
            pending_arm.result_detail = (
                "ARM cancelado por solicitação ABORT antes do reconhecimento do gateway."
            )
            record_event(
                session,
                actor_type="ADMIN",
                actor_user_id=admin.id,
                order_id=mission.order_id,
                mission_id=mission.id,
                vehicle_id=mission.vehicle_id,
                event_type="ARM_CANCELLED_BY_ABORT",
                message=pending_arm.result_detail,
                severity=EventSeverity.CRITICAL,
                metadata={
                    "command_id": str(pending_arm.id),
                    "reason": reason,
                },
            )
        if any(command.command == GatewayCommandType.ABORT for command in open_commands):
            if commit:
                session.commit()
            return mission
    elif open_commands:
        if all(command.command == command_type for command in open_commands):
            return mission
        raise ConflictError("A missão já possui outro comando crítico em andamento")

    if command_type == GatewayCommandType.START:
        if settings is None:
            raise InvalidStateError("Configuração do backend indisponível para validar START")
        if not mission.vehicle_id or not mission.claimed_by_gateway:
            raise ConflictError("START exige missão vinculada a veículo e gateway")
        vehicle = session.get(Vehicle, mission.vehicle_id)
        identity_matches = (
            vehicle is not None
            and vehicle.gateway_id == mission.claimed_by_gateway
            and mission.claimed_by_gateway == settings.gateway_id
        )
        snapshot = latest_health(session, mission.vehicle_id)
        failures = [
            failure
            for failure in health_failures(snapshot, settings)
            if failure != "VEHICLE_ALREADY_ARMED"
        ]
        if not identity_matches:
            failures.append("GATEWAY_IDENTITY_MISMATCH")
        if snapshot.source.value not in {"SITL", "HARDWARE_REAL"}:
            failures.append("OPERATIONAL_SOURCE_NOT_ALLOWED")
        if snapshot.armed is not True:
            failures.append("VEHICLE_NOT_ARMED")
        if snapshot.flight_commands_enabled is not True:
            failures.append("FLIGHT_COMMANDS_DISABLED")
        if snapshot.mission_start_enabled is not True:
            failures.append("MISSION_START_DISABLED")
        if failures:
            raise ConflictError(
                "O estado real do veículo não permite solicitar START",
                fields={"preflight": ",".join(dict.fromkeys(failures))},
            )

    existing = session.scalar(
        select(GatewayCommand).where(
            GatewayCommand.mission_id == mission.id,
            GatewayCommand.command == command_type,
            GatewayCommand.status.in_(
                {GatewayCommandStatus.PENDING, GatewayCommandStatus.ACKNOWLEDGED}
            ),
        )
    )
    if existing:
        return mission
    command = GatewayCommand(
        mission_id=mission.id,
        requested_by_id=admin.id,
        command=command_type,
        reason=reason,
        status=GatewayCommandStatus.PENDING,
    )
    session.add(command)
    session.flush()
    record_event(
        session,
        actor_type="ADMIN",
        actor_user_id=admin.id,
        order_id=mission.order_id,
        mission_id=mission.id,
        vehicle_id=mission.vehicle_id,
        event_type=f"{action}_REQUESTED",
        message=(
            f"Administrador solicitou {action}; aguarda confirmação do gateway/ArduPilot"
            + (f". Motivo: {reason}" if reason else "")
        ),
        severity=EventSeverity.CRITICAL,
        metadata={"command_id": str(command.id), "reason": reason},
    )
    if commit:
        session.commit()
    return mission


def request_vehicle_arm(
    session: Session,
    mission: Mission,
    admin: User,
    payload: VehicleArmRequest,
    settings: Settings,
    *,
    commit: bool = True,
) -> tuple[Mission, GatewayCommand]:
    """Queue one normal ARM request after a fresh, fail-closed safety review."""

    locked_mission = session.scalar(
        select(Mission)
        .where(Mission.id == mission.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not locked_mission:
        raise NotFoundError("Missão não encontrada")
    mission = locked_mission
    if mission.status != MissionStatus.VERIFIED:
        raise InvalidStateError("O armamento só pode ser solicitado para missão verificada")
    if not mission.vehicle_id or not mission.claimed_by_gateway:
        raise ConflictError("A missão verificada não está vinculada a um gateway e veículo")

    vehicle = session.get(Vehicle, mission.vehicle_id)
    if (
        not vehicle
        or vehicle.gateway_id != mission.claimed_by_gateway
        or mission.claimed_by_gateway != settings.gateway_id
    ):
        raise ConflictError("O gateway da missão não corresponde ao veículo vinculado")

    snapshot = latest_health(session, mission.vehicle_id)
    if snapshot.source.value not in {"SITL", "HARDWARE_REAL"}:
        raise ConflictError("Armamento remoto só é permitido em SITL ou hardware real identificado")

    disabled_gates = [
        name
        for name, enabled in (
            ("VEHICLE_ARM_DISABLED", snapshot.vehicle_arm_enabled),
            ("FLIGHT_COMMANDS_DISABLED", snapshot.flight_commands_enabled),
            ("MISSION_START_DISABLED", snapshot.mission_start_enabled),
        )
        if enabled is not True
    ]
    failures = [*health_failures(snapshot, settings), *disabled_gates]
    if (snapshot.flight_mode or "").upper() != "STABILIZE":
        failures.append("ARMING_MODE_NOT_ALLOWED")
    if failures:
        raise ConflictError(
            "O estado real do veículo não permite solicitar armamento",
            fields={"preflight": ",".join(dict.fromkeys(failures))},
        )

    open_command = session.scalar(
        select(GatewayCommand)
        .where(
            GatewayCommand.mission_id == mission.id,
            GatewayCommand.status.in_(
                {GatewayCommandStatus.PENDING, GatewayCommandStatus.ACKNOWLEDGED}
            ),
        )
        .with_for_update()
    )
    if open_command:
        raise ConflictError("A missão já possui um comando crítico em andamento")

    command = GatewayCommand(
        mission_id=mission.id,
        requested_by_id=admin.id,
        command=GatewayCommandType.ARM,
        reason=payload.reason,
        status=GatewayCommandStatus.PENDING,
    )
    session.add(command)
    session.flush()
    record_event(
        session,
        actor_type="ADMIN",
        actor_user_id=admin.id,
        order_id=mission.order_id,
        mission_id=mission.id,
        vehicle_id=mission.vehicle_id,
        event_type="ARM_REQUESTED",
        message="Administrador solicitou armamento normal; aguarda ACK e heartbeat armado",
        severity=EventSeverity.CRITICAL,
        metadata={
            "command_id": str(command.id),
            "gateway_id": mission.claimed_by_gateway,
            "health_snapshot_id": str(snapshot.id),
            "reason": payload.reason,
            "area_clear_confirmed": payload.area_clear_confirmed,
            "operator_present_confirmed": payload.operator_present_confirmed,
            "safety_switch_ready_confirmed": payload.safety_switch_ready_confirmed,
        },
    )
    if commit:
        session.commit()
        session.refresh(command)
    return mission, command


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def acknowledge_gateway_command(
    session: Session,
    command: GatewayCommand,
    payload: GatewayCommandAck,
    settings: Settings,
) -> GatewayCommand:
    if payload.status not in {
        GatewayCommandStatus.ACKNOWLEDGED,
        GatewayCommandStatus.COMPLETED,
        GatewayCommandStatus.FAILED,
    }:
        raise InvalidStateError("O gateway não pode definir este estado de comando")
    locked_command = session.scalar(
        select(GatewayCommand)
        .where(GatewayCommand.id == command.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not locked_command:
        raise NotFoundError("Comando não encontrado")
    command = locked_command
    mission = session.get(Mission, command.mission_id)
    if not mission:
        raise NotFoundError("Missão do comando não encontrada")
    if mission.claimed_by_gateway != payload.gateway_id:
        raise ConflictError("O comando pertence a outro gateway")
    if command.gateway_id and command.gateway_id != payload.gateway_id:
        raise ConflictError("O comando já foi assumido por outro gateway")
    event_type = f"GATEWAY_COMMAND_{payload.status.value}"
    event_message = payload.detail or f"Comando {command.command.value}: {payload.status.value}"
    event_severity = (
        EventSeverity.ERROR if payload.status == GatewayCommandStatus.FAILED else EventSeverity.INFO
    )
    event_metadata: dict[str, str | int | float | bool | None] = {
        "command_id": str(command.id),
        "gateway_id": payload.gateway_id,
    }
    existing_event = session.scalar(
        select(SystemEvent).where(SystemEvent.event_id == payload.event_id)
    )
    if existing_event:
        replay_metadata = existing_event.event_metadata
        if (
            replay_metadata.get("command_id") != str(command.id)
            or replay_metadata.get("gateway_id") != payload.gateway_id
        ):
            replay_metadata = event_metadata
        _event, created = record_event(
            session,
            event_id=payload.event_id,
            actor_type="GATEWAY",
            order_id=mission.order_id,
            mission_id=command.mission_id,
            vehicle_id=mission.vehicle_id,
            event_type=event_type,
            message=event_message,
            severity=event_severity,
            metadata=replay_metadata,
        )
        if not created:
            return command
    if (
        command.command == GatewayCommandType.ARM
        and payload.status == GatewayCommandStatus.COMPLETED
    ):
        if command.status != GatewayCommandStatus.ACKNOWLEDGED:
            raise InvalidStateError("O armamento deve ser reconhecido antes da conclusão")
        if not mission.vehicle_id or command.acknowledged_at is None:
            raise ConflictError("A missão não possui veículo vinculado")
        vehicle = session.get(Vehicle, mission.vehicle_id)
        if not vehicle or vehicle.gateway_id != payload.gateway_id:
            raise ConflictError("A identidade do veículo não corresponde ao gateway do comando")
        snapshot = latest_health(session, mission.vehicle_id)
        acknowledged_at = _as_utc(command.acknowledged_at)
        received_at = _as_utc(snapshot.received_at)
        last_heartbeat_at = (
            _as_utc(snapshot.last_heartbeat_at) if snapshot.last_heartbeat_at is not None else None
        )
        if (
            health_is_stale(snapshot, settings)
            or not snapshot.connected
            or not snapshot.heartbeat
            or snapshot.armed is not True
            or snapshot.source.value not in {"SITL", "HARDWARE_REAL"}
            or received_at <= acknowledged_at
            or last_heartbeat_at is None
            or last_heartbeat_at <= acknowledged_at
        ):
            raise ConflictError(
                "ARM só pode ser concluído após heartbeat novo e fresco confirmando armed=true"
            )
        event_metadata.update(
            {
                "health_snapshot_id": str(snapshot.id),
                "health_received_at": received_at.isoformat(),
                "last_heartbeat_at": last_heartbeat_at.isoformat(),
                "acknowledged_at": acknowledged_at.isoformat(),
                "source": snapshot.source.value,
                "connected": snapshot.connected,
                "heartbeat": snapshot.heartbeat,
                "armed": snapshot.armed,
            }
        )
    if command.status in {GatewayCommandStatus.COMPLETED, GatewayCommandStatus.FAILED}:
        session.rollback()
        raise InvalidStateError("O comando já está encerrado")
    record_event(
        session,
        event_id=payload.event_id,
        actor_type="GATEWAY",
        order_id=mission.order_id,
        mission_id=command.mission_id,
        vehicle_id=mission.vehicle_id,
        event_type=event_type,
        message=event_message,
        severity=event_severity,
        metadata=event_metadata,
    )
    now = datetime.now(UTC)
    if payload.status == GatewayCommandStatus.ACKNOWLEDGED:
        if command.status != GatewayCommandStatus.PENDING:
            session.rollback()
            raise InvalidStateError("O comando já foi reconhecido")
        command.gateway_id = payload.gateway_id
        command.status = GatewayCommandStatus.ACKNOWLEDGED
        command.acknowledged_at = now
    else:
        if command.status == GatewayCommandStatus.PENDING:
            command.gateway_id = payload.gateway_id
            command.acknowledged_at = now
        command.status = payload.status
        command.completed_at = now
        command.result_detail = payload.detail
    session.commit()
    session.refresh(command)
    return command
