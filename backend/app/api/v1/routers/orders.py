from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, status
from fastapi.responses import JSONResponse

from app.api.dependencies import AppSettings, CustomerUser, DatabaseSession
from app.core.websocket import manager
from app.modules.idempotency.service import execute_idempotently
from app.modules.orders.schemas import OrderCreate, OrderDetailRead, OrderGroup, OrderRead
from app.modules.orders.service import (
    cancel_order,
    create_order,
    get_order_for_user,
    list_orders_for_customer,
    order_detail_to_read,
    order_to_read,
    orders_to_read,
    submit_order,
)

router = APIRouter(prefix="/orders", tags=["Pedidos"])


@router.post(
    "",
    response_model=OrderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar pedido em rascunho",
)
def create(
    payload: OrderCreate,
    session: DatabaseSession,
    settings: AppSettings,
    customer: CustomerUser,
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", min_length=8, max_length=200),
    ] = None,
) -> JSONResponse:
    def action() -> dict[str, object]:
        order = create_order(
            session,
            customer,
            payload,
            Decimal(str(settings.delivery_fee)),
            commit=False,
        )
        return order_to_read(session, order).model_dump(mode="json")

    result = execute_idempotently(
        session,
        user_id=customer.id,
        operation="orders.create",
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


@router.get("", response_model=list[OrderRead], summary="Listar pedidos do cliente")
def list_orders(
    session: DatabaseSession,
    customer: CustomerUser,
    group: OrderGroup = Query(default=OrderGroup.ALL),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[OrderRead]:
    orders = list_orders_for_customer(session, customer, group, limit, offset)
    return orders_to_read(session, orders)


@router.get("/{order_id}", response_model=OrderDetailRead, summary="Detalhar pedido do cliente")
def get_order(order_id: UUID, session: DatabaseSession, customer: CustomerUser) -> OrderDetailRead:
    return order_detail_to_read(session, get_order_for_user(session, order_id, customer))


@router.post("/{order_id}/submit", response_model=OrderRead, summary="Enviar para aprovação")
async def submit(
    order_id: UUID,
    session: DatabaseSession,
    customer: CustomerUser,
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key", min_length=8, max_length=200),
    ] = None,
) -> JSONResponse:
    def action() -> dict[str, object]:
        order = submit_order(
            session,
            get_order_for_user(session, order_id, customer),
            customer,
            commit=False,
        )
        return order_to_read(session, order).model_dump(mode="json")

    result = execute_idempotently(
        session,
        user_id=customer.id,
        operation=f"orders.submit:{order_id}",
        key=idempotency_key,
        request_payload={"order_id": str(order_id)},
        response_status=status.HTTP_200_OK,
        action=action,
    )
    payload = {"type": "order.status", "data": result.body}
    await manager.broadcast_order(order_id, payload)
    await manager.broadcast_admin(payload)
    return JSONResponse(
        content=result.body,
        status_code=result.status_code,
        headers={"Idempotency-Replayed": str(result.replayed).lower()},
    )


@router.post("/{order_id}/cancel", response_model=OrderRead, summary="Cancelar pedido")
async def cancel(order_id: UUID, session: DatabaseSession, customer: CustomerUser) -> OrderRead:
    order = cancel_order(session, get_order_for_user(session, order_id, customer), customer)
    response = order_to_read(session, order)
    payload = {"type": "order.status", "data": response.model_dump(mode="json")}
    await manager.broadcast_order(order.id, payload)
    await manager.broadcast_admin(payload)
    return response
