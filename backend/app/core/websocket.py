from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._orders: dict[UUID, set[WebSocket]] = defaultdict(set)
        self._admin: set[WebSocket] = set()

    async def connect_order(
        self, order_id: UUID, websocket: WebSocket, *, accept: bool = True
    ) -> None:
        if accept:
            await websocket.accept()
        self._orders[order_id].add(websocket)

    async def connect_admin(self, websocket: WebSocket, *, accept: bool = True) -> None:
        if accept:
            await websocket.accept()
        self._admin.add(websocket)

    def disconnect_order(self, order_id: UUID, websocket: WebSocket) -> None:
        sockets = self._orders.get(order_id)
        if not sockets:
            return
        sockets.discard(websocket)
        if not sockets:
            self._orders.pop(order_id, None)

    def disconnect_admin(self, websocket: WebSocket) -> None:
        self._admin.discard(websocket)

    async def broadcast_order(self, order_id: UUID, payload: dict[str, object]) -> None:
        await self._broadcast(self._orders.get(order_id, set()), payload)

    async def broadcast_admin(self, payload: dict[str, object]) -> None:
        await self._broadcast(self._admin, payload)

    async def _broadcast(self, sockets: set[WebSocket], payload: dict[str, object]) -> None:
        disconnected: list[WebSocket] = []
        for socket in tuple(sockets):
            try:
                await socket.send_json(payload)
            except RuntimeError:
                disconnected.append(socket)
        for socket in disconnected:
            sockets.discard(socket)


manager = ConnectionManager()
