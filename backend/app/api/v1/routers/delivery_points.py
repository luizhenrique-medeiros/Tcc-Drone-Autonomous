from typing import Annotated

from fastapi import APIRouter, Header, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api.dependencies import AppSettings, CustomerUser, DatabaseSession
from app.modules.delivery_points.models import DeliveryPoint
from app.modules.delivery_points.schemas import (
    DeliveryPointInput,
    DeliveryPointRead,
    DeliveryPointValidation,
)
from app.modules.delivery_points.service import (
    create_delivery_point,
    validate_delivery_point,
)
from app.modules.idempotency.service import execute_idempotently

router = APIRouter(prefix="/delivery-points", tags=["Pontos de entrega"])


@router.post(
    "/validate",
    response_model=DeliveryPointValidation,
    summary="Validar segunda etapa e cobertura do ponto",
)
def validate_point(
    payload: DeliveryPointInput, settings: AppSettings, _customer: CustomerUser
) -> DeliveryPointValidation:
    return validate_delivery_point(payload, settings)


@router.post(
    "",
    response_model=DeliveryPointRead,
    status_code=status.HTTP_201_CREATED,
    summary="Persistir ponto exato confirmado",
)
def create_point(
    payload: DeliveryPointInput,
    session: DatabaseSession,
    settings: AppSettings,
    customer: CustomerUser,
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", min_length=8, max_length=200),
    ] = None,
) -> JSONResponse:
    def action() -> dict[str, object]:
        point = create_delivery_point(session, customer.id, payload, settings, commit=False)
        return DeliveryPointRead.model_validate(point).model_dump(mode="json")

    result = execute_idempotently(
        session,
        user_id=customer.id,
        operation="delivery-points.create",
        key=idempotency_key,
        request_payload=payload.model_dump(mode="json"),
        response_status=status.HTTP_201_CREATED,
        action=action,
    )
    return JSONResponse(
        content=result.body,
        status_code=result.status_code,
        headers={"Idempotency-Replayed": str(result.replayed).lower()},
    )


@router.get("", response_model=list[DeliveryPointRead], summary="Listar pontos do cliente")
def list_points(
    session: DatabaseSession,
    customer: CustomerUser,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[DeliveryPoint]:
    return list(
        session.scalars(
            select(DeliveryPoint)
            .where(DeliveryPoint.user_id == customer.id)
            .order_by(DeliveryPoint.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )
