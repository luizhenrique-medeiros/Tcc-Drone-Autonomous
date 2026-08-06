from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.dependencies import AppSettings, DatabaseSession
from app.core.enums import UserRole
from app.core.exceptions import AuthenticationError, NotFoundError
from app.core.security import decode_access_token
from app.core.websocket import manager
from app.modules.orders.models import Order
from app.modules.orders.service import order_to_read
from app.modules.users.models import User

router = APIRouter(prefix="/ws", tags=["Tempo real"])


def _websocket_user(token: str, session: DatabaseSession, settings: AppSettings) -> User:
    claims = decode_access_token(token, settings)
    try:
        user_id = UUID(str(claims["sub"]))
    except ValueError as exc:
        raise AuthenticationError("Token inválido") from exc
    user = session.get(User, user_id)
    if not user or not user.active or user.role.value != claims["role"]:
        raise AuthenticationError("Usuário inválido")
    return user


async def _websocket_token(websocket: WebSocket) -> str:
    await websocket.accept()
    try:
        message = await asyncio.wait_for(websocket.receive_json(), timeout=10)
    except (TimeoutError, ValueError) as exc:
        raise AuthenticationError("Autenticação WebSocket não recebida") from exc
    if (
        not isinstance(message, dict)
        or message.get("type") != "AUTH"
        or not isinstance(message.get("token"), str)
    ):
        raise AuthenticationError("A primeira mensagem deve ser {type: AUTH, token: ...}")
    return message["token"]


@router.websocket("/orders/{order_id}")
async def order_updates(
    websocket: WebSocket,
    order_id: UUID,
    session: DatabaseSession,
    settings: AppSettings,
) -> None:
    try:
        token = await _websocket_token(websocket)
        user = _websocket_user(token, session, settings)
        order = session.get(Order, order_id)
        if not order or (user.role == UserRole.CUSTOMER and order.customer_id != user.id):
            raise NotFoundError("Pedido não encontrado")
    except AuthenticationError:
        await websocket.close(code=4401)
        return
    except NotFoundError:
        await websocket.close(code=4404)
        return
    await manager.connect_order(order_id, websocket, accept=False)
    await websocket.send_json(
        {
            "type": "order.snapshot",
            "data": order_to_read(session, order).model_dump(mode="json"),
        }
    )
    try:
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect_order(order_id, websocket)


@router.websocket("/admin/operations")
async def admin_operations(
    websocket: WebSocket,
    session: DatabaseSession,
    settings: AppSettings,
) -> None:
    try:
        token = await _websocket_token(websocket)
        user = _websocket_user(token, session, settings)
        if user.role != UserRole.ADMIN:
            await websocket.close(code=4403)
            return
    except AuthenticationError:
        await websocket.close(code=4401)
        return
    await manager.connect_admin(websocket, accept=False)
    await websocket.send_json({"type": "operations.connected"})
    try:
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect_admin(websocket)
