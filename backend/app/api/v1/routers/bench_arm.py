from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Response
from fastapi.responses import JSONResponse

from app.api.dependencies import AdminUser, AppSettings, DatabaseSession, GatewayAuth
from app.modules.bench_arm.service import (
    ArmClaim,
    ArmConfirmation,
    ArmReport,
    claim_arm,
    configured_vehicle,
    current_snapshot,
    eligible,
    latest_request,
    register_arm,
    report_arm,
    require_enabled,
    utc,
    view_command,
)
from app.modules.idempotency.service import execute_idempotently
from app.modules.vehicles.service import health_is_stale

router = APIRouter(tags=["ARM físico de bancada"])


@router.get("/admin/bench-arm")
def bench_arm_status(
    session: DatabaseSession, settings: AppSettings, _admin: AdminUser
) -> dict[str, object]:
    if not settings.px4_bench_arm_enabled:
        return {"enabled": False, "target": None, "request": None}
    vehicle = configured_vehicle(session, settings)
    if vehicle is None:
        return {"enabled": True, "target": None, "request": None}
    snapshot = current_snapshot(session, vehicle)
    ready = eligible(vehicle, snapshot, settings)
    active_session = snapshot.bench_arm_session_id if ready and snapshot is not None else None
    last = latest_request(session, vehicle.id)
    fresh = snapshot is not None and not health_is_stale(snapshot, settings)
    return {
        "enabled": True,
        "target": {
            "id": str(vehicle.id),
            "name": vehicle.name,
            "session_id": str(active_session) if active_session else None,
            "armed": snapshot.armed if fresh and snapshot is not None else None,
            "heartbeat_at": (
                utc(snapshot.last_heartbeat_at).isoformat()
                if fresh and snapshot is not None and snapshot.last_heartbeat_at
                else None
            ),
        },
        "request": view_command(last, active_session) if last else None,
    }


@router.post("/admin/bench-arm/{vehicle_id}", status_code=202)
def request_bench_arm(
    vehicle_id: UUID,
    payload: ArmConfirmation,
    session: DatabaseSession,
    settings: AppSettings,
    admin: AdminUser,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)],
) -> JSONResponse:
    require_enabled(settings)
    result = execute_idempotently(
        session,
        user_id=admin.id,
        operation=f"admin.bench-arm:{vehicle_id}",
        key=idempotency_key,
        request_payload=payload.model_dump(mode="json"),
        response_status=202,
        action=lambda: register_arm(session, settings, admin.id, vehicle_id, payload),
    )
    return JSONResponse(result.body, result.status_code)


@router.post("/gateway/bench-arm/claim")
def claim_bench_arm(
    payload: ArmClaim, session: DatabaseSession, settings: AppSettings, gateway_id: GatewayAuth
) -> dict[str, object] | None:
    require_enabled(settings)
    return claim_arm(session, settings, gateway_id, payload)


@router.post("/gateway/bench-arm/{command_id}/result", status_code=204)
def report_bench_arm(
    command_id: UUID,
    payload: ArmReport,
    session: DatabaseSession,
    settings: AppSettings,
    gateway_id: GatewayAuth,
) -> Response:
    require_enabled(settings)
    report_arm(session, gateway_id, command_id, payload)
    return Response(status_code=204)
