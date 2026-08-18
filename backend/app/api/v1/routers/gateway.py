from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import and_, or_, select

from app.api.dependencies import AppSettings, DatabaseSession, GatewayAuth
from app.core.enums import GatewayCommandStatus, MissionStatus
from app.core.exceptions import DomainError, InvalidStateError, NotFoundError
from app.core.websocket import manager
from app.modules.missions.models import GatewayCommand, Mission
from app.modules.missions.schemas import (
    GatewayClaim,
    GatewayClaimResult,
    GatewayCommandAck,
    GatewayCommandRead,
    GatewayMissionStatus,
    GatewayUploadStatus,
    MissionRead,
)
from app.modules.missions.service import (
    acknowledge_gateway_command,
    active_authorization,
    apply_gateway_status,
    claim_mission,
)
from app.modules.system_events.schemas import GatewayEventCreate, SystemEventRead
from app.modules.system_events.service import record_event
from app.modules.telemetry.schemas import TelemetryCreate, TelemetryRead
from app.modules.telemetry.service import record_telemetry, telemetry_to_read
from app.modules.vehicles.schemas import (
    VehicleHealthInput,
    VehicleHeartbeatResult,
    VehicleRead,
)
from app.modules.vehicles.service import health_to_read, record_heartbeat

router = APIRouter(prefix="/gateway", tags=["Gateway"])


async def _broadcast_mission(mission: Mission) -> None:
    payload = {
        "type": "mission.status",
        "data": MissionRead.model_validate(mission).model_dump(mode="json"),
    }
    await manager.broadcast_order(mission.order_id, payload)
    await manager.broadcast_admin(payload)


@router.post(
    "/heartbeat",
    response_model=VehicleHeartbeatResult,
    summary="Registrar heartbeat e snapshot de pré-voo",
)
async def heartbeat(
    payload: VehicleHealthInput,
    session: DatabaseSession,
    settings: AppSettings,
    _gateway: GatewayAuth,
) -> VehicleHeartbeatResult:
    vehicle, health, failures = record_heartbeat(session, payload, settings)
    response = VehicleHeartbeatResult(
        vehicle=VehicleRead.model_validate(vehicle),
        health=health_to_read(health, settings),
        authorization_eligible=not failures,
        failures=failures,
    )
    await manager.broadcast_admin(
        {"type": "vehicle.health", "data": response.model_dump(mode="json")}
    )
    return response


@router.get(
    "/missions/authorized",
    response_model=list[MissionRead],
    summary="Listar missões com autorização válida não consumida",
)
def authorized_missions(
    session: DatabaseSession,
    _gateway: GatewayAuth,
    limit: int = Query(default=10, ge=1, le=50),
) -> list[Mission]:
    missions = session.scalars(
        select(Mission)
        .where(Mission.status == MissionStatus.AUTHORIZED)
        .order_by(Mission.created_at)
        .limit(limit)
    ).all()
    available: list[Mission] = []
    for mission in missions:
        try:
            active_authorization(session, mission)
        except DomainError:
            continue
        available.append(mission)
    return available


@router.post(
    "/missions/{mission_id}/claim",
    response_model=GatewayClaimResult,
    summary="Consumir autorização e assumir missão idempotentemente",
)
async def claim(
    mission_id: UUID,
    payload: GatewayClaim,
    session: DatabaseSession,
    settings: AppSettings,
    _gateway: GatewayAuth,
) -> GatewayClaimResult:
    mission = session.get(Mission, mission_id)
    if not mission:
        raise NotFoundError("Missão não encontrada")
    authorization = claim_mission(session, mission, payload.gateway_id, settings)
    await _broadcast_mission(mission)
    return GatewayClaimResult(
        mission=MissionRead.model_validate(mission),
        mission_file=mission.mission_file,
        authorization_id=authorization.id,
        authorization_expires_at=authorization.expires_at,
    )


@router.post(
    "/missions/{mission_id}/upload-status",
    response_model=MissionRead,
    summary="Registrar resultado idempotente do upload MAVLink",
)
async def upload_status(
    mission_id: UUID,
    payload: GatewayUploadStatus,
    session: DatabaseSession,
    _gateway: GatewayAuth,
) -> Mission:
    if payload.status not in {
        MissionStatus.UPLOADING,
        MissionStatus.UPLOADED,
        MissionStatus.VERIFIED,
        MissionStatus.FAILED,
    }:
        raise InvalidStateError("Estado inválido para o endpoint de upload")
    mission = session.get(Mission, mission_id)
    if not mission:
        raise NotFoundError("Missão não encontrada")
    result, _created = apply_gateway_status(
        session, mission, payload.status, payload.event_id, payload.detail
    )
    await _broadcast_mission(result)
    return result


@router.post(
    "/missions/{mission_id}/status",
    response_model=MissionRead,
    summary="Aplicar transição reportada por telemetria real",
)
async def mission_status(
    mission_id: UUID,
    payload: GatewayMissionStatus,
    session: DatabaseSession,
    _gateway: GatewayAuth,
) -> Mission:
    mission = session.get(Mission, mission_id)
    if not mission:
        raise NotFoundError("Missão não encontrada")
    result, _created = apply_gateway_status(
        session, mission, payload.status, payload.event_id, payload.detail
    )
    await _broadcast_mission(result)
    return result


@router.post(
    "/missions/{mission_id}/telemetry",
    response_model=TelemetryRead,
    summary="Persistir telemetria normalizada e deduplicada",
)
async def telemetry(
    mission_id: UUID,
    payload: TelemetryCreate,
    session: DatabaseSession,
    settings: AppSettings,
    _gateway: GatewayAuth,
) -> object:
    mission = session.get(Mission, mission_id)
    if not mission:
        raise NotFoundError("Missão não encontrada")
    result, created = record_telemetry(session, mission, payload, settings)
    response = telemetry_to_read(result, settings)
    if created:
        message = {
            "type": "mission.telemetry",
            "data": response.model_dump(mode="json"),
        }
        await manager.broadcast_order(mission.order_id, message)
        await manager.broadcast_admin(message)
    return response


@router.post(
    "/missions/{mission_id}/events",
    response_model=SystemEventRead,
    summary="Registrar evento operacional deduplicado",
)
async def gateway_event(
    mission_id: UUID,
    payload: GatewayEventCreate,
    session: DatabaseSession,
    _gateway: GatewayAuth,
) -> object:
    mission = session.get(Mission, mission_id)
    if not mission:
        raise NotFoundError("Missão não encontrada")
    event, created = record_event(
        session,
        event_id=payload.event_id,
        actor_type="GATEWAY",
        order_id=mission.order_id,
        mission_id=mission.id,
        vehicle_id=payload.vehicle_id or mission.vehicle_id,
        event_type=payload.event_type,
        severity=payload.severity,
        message=payload.message,
        metadata=payload.metadata,
    )
    if created:
        session.commit()
        session.refresh(event)
        message = {
            "type": "system.event",
            "data": SystemEventRead.model_validate(event).model_dump(mode="json", by_alias=True),
        }
        await manager.broadcast_order(mission.order_id, message)
        await manager.broadcast_admin(message)
    return event


@router.get(
    "/commands/pending",
    response_model=list[GatewayCommandRead],
    summary="Consultar comandos administrativos pendentes",
)
def pending_commands(
    session: DatabaseSession,
    _gateway: GatewayAuth,
    gateway_id: str = Query(min_length=2, max_length=120),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[GatewayCommand]:
    return list(
        session.scalars(
            select(GatewayCommand)
            .join(Mission, Mission.id == GatewayCommand.mission_id)
            .where(
                Mission.claimed_by_gateway == gateway_id,
                or_(
                    GatewayCommand.status == GatewayCommandStatus.PENDING,
                    and_(
                        GatewayCommand.status == GatewayCommandStatus.ACKNOWLEDGED,
                        GatewayCommand.gateway_id == gateway_id,
                    ),
                ),
            )
            .order_by(GatewayCommand.requested_at)
            .limit(limit)
        )
    )


@router.post(
    "/commands/{command_id}/ack",
    response_model=GatewayCommandRead,
    summary="Reconhecer ou concluir comando idempotentemente",
)
async def acknowledge_command(
    command_id: UUID,
    payload: GatewayCommandAck,
    session: DatabaseSession,
    _gateway: GatewayAuth,
) -> GatewayCommand:
    command = session.get(GatewayCommand, command_id)
    if not command:
        raise NotFoundError("Comando não encontrado")
    result = acknowledge_gateway_command(session, command, payload)
    await manager.broadcast_admin(
        {
            "type": "gateway.command",
            "data": GatewayCommandRead.model_validate(result).model_dump(mode="json"),
        }
    )
    return result
