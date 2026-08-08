from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app.core.enums import OrderStatus
from app.database.session import SessionLocal
from app.modules.orders.models import Order
from app.modules.products.models import Product
from app.modules.system_events.models import SystemEvent
from app.modules.system_events.service import record_event


def _register_and_login(client: TestClient, email: str) -> dict[str, str]:
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Cliente de pedidos",
            "email": email,
            "phone": "+5511999999999",
            "password": "Customer-pass-123",
        },
    )
    assert registered.status_code == 201, registered.text
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Customer-pass-123"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _create_point(
    client: TestClient,
    headers: dict[str, str],
    point_payload: dict[str, object],
) -> dict[str, object]:
    response = client.post("/api/v1/delivery-points", headers=headers, json=point_payload)
    assert response.status_code == 201, response.text
    return response.json()


def _create_order(
    client: TestClient,
    headers: dict[str, str],
    point_id: str,
    *,
    items: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    products = client.get("/api/v1/products", headers=headers)
    assert products.status_code == 200, products.text
    requested_items = items or [{"product_id": products.json()[0]["id"], "quantity": 1}]
    response = client.post(
        "/api/v1/orders",
        headers=headers,
        json={
            "delivery_point_id": point_id,
            "payment_method": "PIX",
            "items": requested_items,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _token(headers: dict[str, str]) -> str:
    return headers["Authorization"].removeprefix("Bearer ")


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def test_customer_lists_only_own_orders_and_foreign_detail_is_not_found(
    client: TestClient,
    customer_headers: dict[str, str],
    valid_point_payload: dict[str, object],
) -> None:
    own_point = _create_point(client, customer_headers, valid_point_payload)
    own_order = _create_order(client, customer_headers, str(own_point["id"]))
    own_submitted = client.post(
        f"/api/v1/orders/{own_order['id']}/submit", headers=customer_headers
    )
    assert own_submitted.status_code == 200, own_submitted.text
    own_order = own_submitted.json()

    other_headers = _register_and_login(client, "outro-cliente@example.com")
    other_payload = deepcopy(valid_point_payload)
    other_payload["label"] = "Ponto de outro cliente"
    other_point = _create_point(client, other_headers, other_payload)
    other_order = _create_order(client, other_headers, str(other_point["id"]))
    other_submitted = client.post(
        f"/api/v1/orders/{other_order['id']}/submit", headers=other_headers
    )
    assert other_submitted.status_code == 200, other_submitted.text
    other_order = other_submitted.json()

    listed = client.get("/api/v1/orders", headers=customer_headers)
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [own_order["id"]]
    assert other_order["id"] not in {item["id"] for item in listed.json()}

    forbidden = client.get(f"/api/v1/orders/{own_order['id']}", headers=other_headers)
    assert forbidden.status_code == 404
    assert forbidden.json()["code"] == "NOT_FOUND"


def test_order_groups_active_first_deterministic_and_paginated(
    client: TestClient,
    customer_headers: dict[str, str],
    valid_point_payload: dict[str, object],
) -> None:
    point = _create_point(client, customer_headers, valid_point_payload)
    orders = [_create_order(client, customer_headers, str(point["id"])) for _index in range(6)]
    active_same_time = datetime(2026, 8, 1, 12, tzinfo=UTC)
    active_newer = datetime(2026, 8, 2, 12, tzinfo=UTC)
    history_same_time = datetime(2026, 8, 3, 12, tzinfo=UTC)
    history_newer = datetime(2026, 8, 4, 12, tzinfo=UTC)
    configured = (
        (orders[0], OrderStatus.DRAFT, active_same_time),
        (orders[1], OrderStatus.APPROVED, active_same_time),
        (orders[2], OrderStatus.IN_TRANSIT, active_newer),
        (orders[3], OrderStatus.CANCELLED, history_same_time),
        (orders[4], OrderStatus.REJECTED, history_same_time),
        (orders[5], OrderStatus.FAILED, history_newer),
    )
    with SessionLocal() as session:
        for payload, status, created_at in configured:
            order = session.get(Order, UUID(str(payload["id"])))
            assert order is not None
            order.status = status
            order.created_at = created_at
        session.commit()

    history_tied = sorted(
        [orders[3]["id"], orders[4]["id"]],
        key=lambda value: UUID(str(value)),
        reverse=True,
    )
    expected_active = [orders[2]["id"], orders[1]["id"]]
    expected_history = [orders[5]["id"], *history_tied]
    expected_all = [*expected_active, *expected_history]

    all_orders = client.get("/api/v1/orders?group=all", headers=customer_headers)
    assert all_orders.status_code == 200, all_orders.text
    assert [item["id"] for item in all_orders.json()] == expected_all
    assert orders[0]["id"] not in {item["id"] for item in all_orders.json()}

    active = client.get("/api/v1/orders?group=active", headers=customer_headers)
    assert active.status_code == 200, active.text
    assert [item["id"] for item in active.json()] == expected_active

    history = client.get("/api/v1/orders?group=history", headers=customer_headers)
    assert history.status_code == 200, history.text
    assert [item["id"] for item in history.json()] == expected_history

    page = client.get("/api/v1/orders?group=all&limit=2&offset=1", headers=customer_headers)
    assert page.status_code == 200, page.text
    assert [item["id"] for item in page.json()] == expected_all[1:3]


def test_order_detail_contains_snapshot_point_values_and_only_real_safe_milestones(
    client: TestClient,
    customer_headers: dict[str, str],
    admin_headers: dict[str, str],
    valid_point_payload: dict[str, object],
) -> None:
    point_payload = deepcopy(valid_point_payload)
    point_payload.update(
        {
            "searched_address": "Avenida de referencia, 100",
            "address_reference": "Portao ao lado da quadra",
            "label": "Ponto exato do pedido",
            "instructions": "Usar apenas a area demarcada",
        }
    )
    point = _create_point(client, customer_headers, point_payload)
    products = client.get("/api/v1/products", headers=customer_headers).json()
    product_image_url = "https://cdn.example.test/products/first-product.webp"
    with SessionLocal() as session:
        catalog_product = session.get(Product, UUID(products[0]["id"]))
        assert catalog_product is not None
        catalog_product.image_url = product_image_url
        session.commit()
    order = _create_order(
        client,
        customer_headers,
        str(point["id"]),
        items=[
            {"product_id": products[0]["id"], "quantity": 2},
            {"product_id": products[1]["id"], "quantity": 1},
        ],
    )
    submitted = client.post(
        f"/api/v1/orders/{order['id']}/submit",
        headers=customer_headers,
    )
    assert submitted.status_code == 200, submitted.text
    approved = client.post(
        f"/api/v1/admin/orders/{order['id']}/approve",
        headers=admin_headers,
        json={"reason": "Ponto revisado"},
    )
    assert approved.status_code == 200, approved.text

    with SessionLocal() as session:
        record_event(
            session,
            actor_type="SYSTEM",
            order_id=UUID(str(order["id"])),
            event_type="INTERNAL_ONLY_EVENT",
            message="Mensagem que nao deve sair no contrato do cliente",
            metadata={"internal": True},
        )
        session.commit()

    detail = client.get(f"/api/v1/orders/{order['id']}", headers=customer_headers)
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["id"] == order["id"]
    assert body["status"] == "APPROVED"
    assert body["payment_method"] == "PIX"
    for amount_field in ("subtotal", "delivery_fee", "discount", "total"):
        assert Decimal(body[amount_field]) == Decimal(str(order[amount_field]))
    assert [item["product_name"] for item in body["items"]] == [
        products[0]["name"],
        products[1]["name"],
    ]
    assert [item["quantity"] for item in body["items"]] == [2, 1]
    assert [Decimal(item["unit_price"]) for item in body["items"]] == [
        Decimal(products[0]["price"]),
        Decimal(products[1]["price"]),
    ]
    assert body["items"][0]["category"] == products[0]["category"]
    assert body["items"][0]["image_url"] == product_image_url
    assert body["items"][1]["category"] == products[1]["category"]
    assert body["items"][1]["image_url"] is None
    assert body["delivery_point"]["searched_address"] == point_payload["searched_address"]
    assert body["delivery_point"]["address_reference"] == point_payload["address_reference"]
    assert body["delivery_point"]["instructions"] == point_payload["instructions"]
    assert float(body["delivery_point"]["final_latitude"]) == point_payload["final_latitude"]
    assert float(body["delivery_point"]["final_longitude"]) == point_payload["final_longitude"]

    expected_types = ["ORDER_CREATED", "ORDER_SUBMITTED", "ORDER_APPROVED"]
    assert [milestone["event_type"] for milestone in body["milestones"]] == expected_types
    assert all(set(milestone) == {"event_type", "occurred_at"} for milestone in body["milestones"])
    assert "INTERNAL_ONLY_EVENT" not in {
        milestone["event_type"] for milestone in body["milestones"]
    }
    assert "MISSION_EXECUTING" not in {milestone["event_type"] for milestone in body["milestones"]}

    with SessionLocal() as session:
        persisted = session.scalars(
            select(SystemEvent)
            .where(
                SystemEvent.order_id == UUID(str(order["id"])),
                SystemEvent.event_type.in_(expected_types),
            )
            .order_by(SystemEvent.created_at, SystemEvent.id)
        ).all()
    persisted_by_type = {event.event_type: event.created_at for event in persisted}
    for milestone in body["milestones"]:
        returned_at = datetime.fromisoformat(milestone["occurred_at"].replace("Z", "+00:00"))
        assert _utc_naive(returned_at) == _utc_naive(persisted_by_type[milestone["event_type"]])


def test_customer_order_websocket_returns_owned_snapshot_and_hides_foreign_order(
    client: TestClient,
    customer_headers: dict[str, str],
    valid_point_payload: dict[str, object],
) -> None:
    point = _create_point(client, customer_headers, valid_point_payload)
    order = _create_order(client, customer_headers, str(point["id"]))

    with client.websocket_connect(f"/api/v1/ws/orders/{order['id']}") as websocket:
        websocket.send_json({"type": "AUTH", "token": _token(customer_headers)})
        snapshot = websocket.receive_json()
        assert snapshot["type"] == "order.snapshot"
        assert snapshot["data"]["id"] == order["id"]
        assert snapshot["data"]["status"] == "DRAFT"

        submitted = client.post(
            f"/api/v1/orders/{order['id']}/submit",
            headers={**customer_headers, "Idempotency-Key": "ws-order-submit-001"},
        )
        assert submitted.status_code == 200, submitted.text
        update = websocket.receive_json()
        assert update["type"] == "order.status"
        assert update["data"]["id"] == order["id"]
        assert update["data"]["status"] == "PENDING_ADMIN_APPROVAL"

    other_headers = _register_and_login(client, "ws-outro-cliente@example.com")
    with client.websocket_connect(f"/api/v1/ws/orders/{order['id']}") as websocket:
        websocket.send_json({"type": "AUTH", "token": _token(other_headers)})
        with pytest.raises(WebSocketDisconnect) as captured:
            websocket.receive_json()
    assert captured.value.code == 4404
