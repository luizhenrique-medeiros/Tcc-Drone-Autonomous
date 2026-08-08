from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api.dependencies import AdminUser, AppSettings, DatabaseSession
from app.core.enums import MissionStatus, OrderStatus
from app.core.exceptions import NotFoundError
from app.core.websocket import manager
from app.modules.idempotency.service import execute_idempotently
from app.modules.missions.models import Mission
from app.modules.missions.schemas import (
    FlightAuthorizationCreate,
    FlightAuthorizationRead,
    MissionAuthorizationResult,
    MissionRead,
    MissionReview,
    SafetyActionRequest,
)
from app.modules.missions.service import (
    authorize_flight,
    export_mission,
    mark_reviewed,
    mark_under_review,
    prepare_mission,
    request_safety_action,
)
from app.modules.orders.admin_schemas import (
    AdminOrderRead,
    ApproveOrderRequest,
    RejectOrderRequest,
)
from app.modules.orders.models import Order
from app.modules.orders.service import (
    admin_order_to_read,
    approve_order,
    get_order_for_user,
    order_to_read,
    reject_order,
)
from app.modules.system_events.models import SystemEvent
from app.modules.system_events.schemas import SystemEventRead
from app.modules.telemetry.models import TelemetryLog
from app.modules.telemetry.schemas import TelemetryRead
from app.modules.telemetry.service import telemetry_to_read
from app.modules.vehicles.models import Vehicle
from app.modules.vehicles.schemas import VehicleHealthRead, VehicleRead
from app.modules.vehicles.service import health_to_read, latest_health

router = APIRouter(prefix="/admin", tags=["Administração"])


async def _broadcast_order(session: DatabaseSession, order: Order) -> None:
    customer_response = order_to_read(session, order).model_dump(mode="json")
    admin_response = admin_order_to_read(session, order).model_dump(mode="json")
    await manager.broadcast_order(order.id, {"type": "order.status", "data": customer_response})
    await manager.broadcast_admin({"type": "order.status", "data": admin_response})


async def _broadcast_mission(mission: Mission) -> None:
    payload = {
        "type": "mission.status",
        "data": MissionRead.model_validate(mission).model_dump(mode="json"),
    }
    await manager.broadcast_order(mission.order_id, payload)
    await manager.broadcast_admin(payload)


@router.get("/orders", response_model=list[AdminOrderRead], summary="Listar todos os pedidos")
def list_admin_orders(
    session: DatabaseSession,
    _admin: AdminUser,
    order_status: OrderStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AdminOrderRead]:
    query = select(Order).order_by(Order.created_at.desc()).offset(offset).limit(limit)
    if order_status:
        query = query.where(Order.status == order_status)
    return [admin_order_to_read(session, order) for order in session.scalars(query).all()]


@router.get("/orders/{order_id}", response_model=AdminOrderRead, summary="Analisar pedido")
def admin_order_detail(
    order_id: UUID, session: DatabaseSession, admin: AdminUser
) -> AdminOrderRead:
    return admin_order_to_read(session, get_order_for_user(session, order_id, admin))


@router.post("/orders/{order_id}/approve", response_model=AdminOrderRead, summary="Aprovar pedido")
async def admin_approve_order(
    order_id: UUID,
    session: DatabaseSession,
    admin: AdminUser,
    payload: ApproveOrderRequest | None = None,
) -> AdminOrderRead:
    order = approve_order(
        session,
        get_order_for_user(session, order_id, admin),
        admin,
        payload.reason if payload else None,
    )
    await _broadcast_order(session, order)
    return admin_order_to_read(session, order)


@router.post("/orders/{order_id}/reject", response_model=AdminOrderRead, summary="Rejeitar pedido")
async def admin_reject_order(
    order_id: UUID,
    payload: RejectOrderRequest,
    session: DatabaseSession,
    admin: AdminUser,
) -> AdminOrderRead:
    order = reject_order(
        session, get_order_for_user(session, order_id, admin), admin, payload.reason
    )
    await _broadcast_order(session, order)
    return admin_order_to_read(session, order)


@router.post(
    "/orders/{order_id}/prepare-mission",
    response_model=MissionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Gerar missão Mission Planner",
)
async def admin_prepare_mission(
    order_id: UUID,
    session: DatabaseSession,
    settings: AppSettings,
    admin: AdminUser,
) -> Mission:
    mission = prepare_mission(
        session, get_order_for_user(session, order_id, admin), admin, settings
    )
    await _broadcast_mission(mission)
    return mission


@router.get("/missions", response_model=list[MissionRead], summary="Listar missões")
def list_missions(
    session: DatabaseSession,
    _admin: AdminUser,
    mission_status: MissionStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[Mission]:
    query = select(Mission).order_by(Mission.created_at.desc()).offset(offset).limit(limit)
    if mission_status:
        query = query.where(Mission.status == mission_status)
    return list(session.scalars(query))


@router.get("/missions/{mission_id}", response_model=MissionRead, summary="Detalhar missão")
def admin_mission_detail(mission_id: UUID, session: DatabaseSession, _admin: AdminUser) -> Mission:
    mission = session.get(Mission, mission_id)
    if not mission:
        raise NotFoundError("Missão não encontrada")
    return mission


@router.get(
    "/missions/{mission_id}/export",
    response_class=Response,
    summary="Baixar arquivo QGC WPL 110",
)
def admin_export_mission(mission_id: UUID, session: DatabaseSession, admin: AdminUser) -> Response:
    mission = session.get(Mission, mission_id)
    if not mission:
        raise NotFoundError("Missão não encontrada")
    content = export_mission(session, mission, admin)
    filename = f"mission-{mission.id}-v{mission.version}.waypoints"
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Mission-SHA256": mission.mission_sha256,
        },
    )


@router.post(
    "/missions/{mission_id}/mark-under-review",
    response_model=MissionRead,
    summary="Registrar abertura no Mission Planner",
)
async def admin_mark_under_review(
    mission_id: UUID, session: DatabaseSession, admin: AdminUser
) -> Mission:
    mission = session.get(Mission, mission_id)
    if not mission:
        raise NotFoundError("Missão não encontrada")
    result = mark_under_review(session, mission, admin)
    await _broadcast_mission(result)
    return result


@router.post(
    "/missions/{mission_id}/mark-reviewed",
    response_model=MissionRead,
    summary="Concluir revisão humana da rota",
)
async def admin_mark_reviewed(
    mission_id: UUID,
    session: DatabaseSession,
    admin: AdminUser,
    payload: MissionReview | None = None,
) -> Mission:
    mission = session.get(Mission, mission_id)
    if not mission:
        raise NotFoundError("Missão não encontrada")
    result = mark_reviewed(session, mission, admin, payload.notes if payload else None)
    await _broadcast_mission(result)
    return result


@router.post(
    "/missions/{mission_id}/authorize-flight",
    response_model=MissionAuthorizationResult,
    summary="Emitir autorização de voo explícita e de uso único",
)
async def admin_authorize_flight(
    mission_id: UUID,
    payload: FlightAuthorizationCreate,
    session: DatabaseSession,
    settings: AppSettings,
    admin: AdminUser,
) -> MissionAuthorizationResult:
    mission = session.get(Mission, mission_id)
    if not mission:
        raise NotFoundError("Missão não encontrada")
    authorization = authorize_flight(session, mission, admin, payload, settings)
    session.refresh(mission)
    await _broadcast_mission(mission)
    return MissionAuthorizationResult(
        mission=MissionRead.model_validate(mission),
        authorization=FlightAuthorizationRead.model_validate(authorization),
    )


@router.post("/missions/{mission_id}/abort", response_model=MissionRead, status_code=202)
async def admin_abort(
    mission_id: UUID,
    session: DatabaseSession,
    admin: AdminUser,
    payload: SafetyActionRequest | None = None,
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", min_length=8, max_length=200),
    ] = None,
) -> JSONResponse:
    mission = session.get(Mission, mission_id)
    if not mission:
        raise NotFoundError("Missão não encontrada")
    reason = payload.reason if payload else None

    def action() -> dict[str, object]:
        result = request_safety_action(session, mission, admin, "ABORT", reason, commit=False)
        return MissionRead.model_validate(result).model_dump(mode="json")

    result = execute_idempotently(
        session,
        user_id=admin.id,
        operation=f"admin.missions.abort:{mission_id}",
        key=idempotency_key,
        request_payload={"mission_id": str(mission_id), "action": "ABORT", "reason": reason},
        response_status=status.HTTP_202_ACCEPTED,
        action=action,
    )
    message = {"type": "mission.status", "data": result.body}
    await manager.broadcast_order(mission.order_id, message)
    await manager.broadcast_admin(message)
    return JSONResponse(
        content=result.body,
        status_code=result.status_code,
        headers={"Idempotency-Replayed": str(result.replayed).lower()},
    )


@router.post("/missions/{mission_id}/request-rtl", response_model=MissionRead, status_code=202)
async def admin_request_rtl(
    mission_id: UUID,
    session: DatabaseSession,
    admin: AdminUser,
    payload: SafetyActionRequest | None = None,
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", min_length=8, max_length=200),
    ] = None,
) -> JSONResponse:
    mission = session.get(Mission, mission_id)
    if not mission:
        raise NotFoundError("Missão não encontrada")
    reason = payload.reason if payload else None

    def action() -> dict[str, object]:
        result = request_safety_action(session, mission, admin, "RTL", reason, commit=False)
        return MissionRead.model_validate(result).model_dump(mode="json")

    result = execute_idempotently(
        session,
        user_id=admin.id,
        operation=f"admin.missions.rtl:{mission_id}",
        key=idempotency_key,
        request_payload={"mission_id": str(mission_id), "action": "RTL", "reason": reason},
        response_status=status.HTTP_202_ACCEPTED,
        action=action,
    )
    message = {"type": "mission.status", "data": result.body}
    await manager.broadcast_order(mission.order_id, message)
    await manager.broadcast_admin(message)
    return JSONResponse(
        content=result.body,
        status_code=result.status_code,
        headers={"Idempotency-Replayed": str(result.replayed).lower()},
    )


@router.get("/vehicles", response_model=list[VehicleRead], summary="Listar veículos conhecidos")
def list_vehicles(session: DatabaseSession, _admin: AdminUser) -> list[Vehicle]:
    return list(session.scalars(select(Vehicle).order_by(Vehicle.name)))


@router.get(
    "/vehicles/{vehicle_id}/health",
    response_model=VehicleHealthRead,
    summary="Obter último estado real reportado",
)
def vehicle_health(
    vehicle_id: UUID,
    session: DatabaseSession,
    settings: AppSettings,
    _admin: AdminUser,
) -> VehicleHealthRead:
    return health_to_read(latest_health(session, vehicle_id), settings)


@router.get("/events", response_model=list[SystemEventRead], summary="Consultar auditoria")
def list_events(
    session: DatabaseSession,
    _admin: AdminUser,
    order_id: UUID | None = None,
    mission_id: UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[SystemEvent]:
    query = select(SystemEvent).order_by(SystemEvent.created_at.desc()).offset(offset).limit(limit)
    if order_id:
        query = query.where(SystemEvent.order_id == order_id)
    if mission_id:
        query = query.where(SystemEvent.mission_id == mission_id)
    return list(session.scalars(query))


@router.get(
    "/missions/{mission_id}/telemetry",
    response_model=list[TelemetryRead],
    summary="Consultar telemetria persistida",
)
def mission_telemetry(
    mission_id: UUID,
    session: DatabaseSession,
    settings: AppSettings,
    _admin: AdminUser,
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[TelemetryRead]:
    if not session.get(Mission, mission_id):
        raise NotFoundError("Missão não encontrada")
    telemetry = list(
        session.scalars(
            select(TelemetryLog)
            .where(TelemetryLog.mission_id == mission_id)
            .order_by(TelemetryLog.recorded_at.desc())
            .limit(limit)
        )
    )
    return [telemetry_to_read(item, settings) for item in telemetry]


@router.get(
    "/telemetry",
    response_model=list[TelemetryRead],
    summary="Consultar telemetria por missão",
)
def telemetry_history(
    mission_id: UUID,
    session: DatabaseSession,
    settings: AppSettings,
    _admin: AdminUser,
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[TelemetryRead]:
    return mission_telemetry(mission_id, session, settings, _admin, limit)
