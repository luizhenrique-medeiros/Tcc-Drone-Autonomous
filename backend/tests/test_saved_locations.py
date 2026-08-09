from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql

from app.database.session import SessionLocal
from app.database.types import point_ewkt
from app.modules.delivery_points.models import DeliveryPoint
from app.modules.orders.models import Order
from app.modules.saved_locations.models import SavedLocation
from app.modules.saved_locations.service import saved_location_creation_lock


def _register_and_login(client: TestClient, email: str) -> dict[str, str]:
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Cliente de localizações",
            "email": email,
            "phone": "+5511988888888",
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


def _payload(index: int = 1) -> dict[str, object]:
    return {
        "name": f"Local {index}",
        "final_latitude": -23.117 + index / 10_000,
        "final_longitude": -46.55 - index / 10_000,
        "address_reference": f"Referência {index}",
        "instructions": f"Instrução {index}",
        "accuracy_meters": 3.5,
        "map_provider": "maptiler",
        "map_type": "hybrid",
        "region_confirmed": True,
        "exact_point_selected": True,
        "user_confirmed": True,
        "user_confirmed_safe_area": True,
    }


def _create_location(
    client: TestClient,
    headers: dict[str, str],
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/saved-locations",
        headers=headers,
        json=payload or _payload(),
    )
    assert response.status_code == 201, response.text
    return response.json()


def _first_product_id(client: TestClient, headers: dict[str, str]) -> str:
    response = client.get("/api/v1/products", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()[0]["id"]


def test_lists_zero_then_one_two_three_and_rejects_fourth(
    client: TestClient,
    customer_headers: dict[str, str],
) -> None:
    empty = client.get("/api/v1/saved-locations", headers=customer_headers)
    assert empty.status_code == 200
    assert empty.json() == []

    created_ids: list[str] = []
    for expected_count in range(1, 4):
        created = _create_location(client, customer_headers, _payload(expected_count))
        created_ids.append(str(created["id"]))
        listed = client.get("/api/v1/saved-locations", headers=customer_headers)
        assert listed.status_code == 200
        assert len(listed.json()) == expected_count
        assert [item["id"] for item in listed.json()] == created_ids

    fourth = client.post(
        "/api/v1/saved-locations",
        headers=customer_headers,
        json=_payload(4),
    )
    assert fourth.status_code == 409
    assert fourth.json() == {
        "code": "SAVED_LOCATION_LIMIT_REACHED",
        "detail": "Você pode salvar no máximo 3 localizações.",
        "fields": {},
    }


def test_crud_trims_name_updates_coordinates_and_allows_missing_address(
    client: TestClient,
    customer_headers: dict[str, str],
) -> None:
    payload = {
        **_payload(),
        "name": "  Sítio  ",
        "final_latitude": -23.5,
        "final_longitude": -46.8,
        "address_reference": None,
        "instructions": "Pousar perto do portão",
        "accuracy_meters": None,
    }
    created = _create_location(client, customer_headers, payload)
    assert created["name"] == "Sítio"
    assert created["address_reference"] is None
    assert created["accuracy_meters"] is None
    assert created["created_at"]
    assert created["updated_at"]

    detail = client.get(
        f"/api/v1/saved-locations/{created['id']}",
        headers=customer_headers,
    )
    assert detail.status_code == 200
    assert detail.json() == created

    updated = client.patch(
        f"/api/v1/saved-locations/{created['id']}",
        headers=customer_headers,
        json={
            "name": "  Casa  ",
            "final_latitude": -22.9,
            "final_longitude": -46.2,
            "address_reference": "Portão azul",
            "instructions": None,
            "accuracy_meters": 8,
            "map_provider": "maptiler",
            "map_type": "satellite",
            "region_confirmed": True,
            "exact_point_selected": True,
            "user_confirmed": True,
            "user_confirmed_safe_area": True,
        },
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["name"] == "Casa"
    assert float(body["final_latitude"]) == -22.9
    assert float(body["final_longitude"]) == -46.2
    assert body["address_reference"] == "Portão azul"
    assert body["instructions"] is None
    assert float(body["accuracy_meters"]) == 8
    assert body["map_provider"] == "maptiler"
    assert body["map_type"] == "satellite"
    assert body["region_confirmed"] is True
    assert body["exact_point_selected"] is True
    assert body["user_confirmed"] is True
    assert body["user_confirmed_safe_area"] is True

    deleted = client.delete(
        f"/api/v1/saved-locations/{created['id']}",
        headers=customer_headers,
    )
    assert deleted.status_code == 204
    assert deleted.content == b""
    missing = client.get(
        f"/api/v1/saved-locations/{created['id']}",
        headers=customer_headers,
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "NOT_FOUND"


def test_saved_location_quantizes_numeric_columns_and_geography_together(
    client: TestClient,
    customer_headers: dict[str, str],
) -> None:
    created = _create_location(
        client,
        customer_headers,
        {
            **_payload(),
            "final_latitude": -23.12345678,
            "final_longitude": -46.76543218,
        },
    )

    with SessionLocal() as session:
        location = session.get(SavedLocation, UUID(str(created["id"])))
        assert location is not None
        assert str(location.final_latitude) == "-23.1234568"
        assert str(location.final_longitude) == "-46.7654322"
        assert location.location == point_ewkt(
            location.final_latitude,
            location.final_longitude,
        )


def test_saved_location_ownership_is_non_enumerable(
    client: TestClient,
    customer_headers: dict[str, str],
) -> None:
    created = _create_location(client, customer_headers)
    other_headers = _register_and_login(client, "outro-local@example.com")
    path = f"/api/v1/saved-locations/{created['id']}"

    foreign_list = client.get("/api/v1/saved-locations", headers=other_headers)
    assert foreign_list.status_code == 200
    assert foreign_list.json() == []

    foreign_get = client.get(path, headers=other_headers)
    foreign_patch = client.patch(path, headers=other_headers, json={"name": "Invasão"})
    foreign_delete = client.delete(path, headers=other_headers)
    for response in (foreign_get, foreign_patch, foreign_delete):
        assert response.status_code == 404
        assert response.json()["code"] == "NOT_FOUND"

    owner_detail = client.get(path, headers=customer_headers)
    assert owner_detail.status_code == 200
    assert owner_detail.json()["name"] == created["name"]


@pytest.mark.parametrize(
    "payload",
    [
        {**_payload(), "name": "   "},
        {**_payload(), "name": "x" * 41},
        {**_payload(), "final_latitude": 90.0001},
        {**_payload(), "final_longitude": -180.0001},
        {**_payload(), "accuracy_meters": -0.01},
        {**_payload(), "user_id": "00000000-0000-0000-0000-000000000001"},
    ],
)
def test_rejects_invalid_saved_location_payloads(
    client: TestClient,
    customer_headers: dict[str, str],
    payload: dict[str, object],
) -> None:
    response = client.post(
        "/api/v1/saved-locations",
        headers=customer_headers,
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_create_requires_complete_true_confirmation_and_satellite_map(
    client: TestClient,
    customer_headers: dict[str, str],
) -> None:
    missing_confirmation = _payload()
    missing_confirmation.pop("user_confirmed_safe_area")
    missing = client.post(
        "/api/v1/saved-locations",
        headers=customer_headers,
        json=missing_confirmation,
    )
    assert missing.status_code == 422

    for field in (
        "region_confirmed",
        "exact_point_selected",
        "user_confirmed",
        "user_confirmed_safe_area",
    ):
        rejected = client.post(
            "/api/v1/saved-locations",
            headers=customer_headers,
            json={**_payload(), field: False},
        )
        assert rejected.status_code == 400
        assert rejected.json()["code"] == "INVALID_COORDINATES"
        assert rejected.json()["fields"] == {field: "confirmation_required"}

    invalid_map = client.post(
        "/api/v1/saved-locations",
        headers=customer_headers,
        json={**_payload(), "map_type": "normal"},
    )
    assert invalid_map.status_code == 400
    assert invalid_map.json()["code"] == "INVALID_COORDINATES"
    assert invalid_map.json()["fields"] == {"map_type": "satellite_required"}


def test_patch_requires_nonempty_changes_and_coordinate_pair(
    client: TestClient,
    customer_headers: dict[str, str],
) -> None:
    created = _create_location(client, customer_headers)
    path = f"/api/v1/saved-locations/{created['id']}"

    empty = client.patch(path, headers=customer_headers, json={})
    only_latitude = client.patch(
        path,
        headers=customer_headers,
        json={"final_latitude": -23.2},
    )
    null_name = client.patch(path, headers=customer_headers, json={"name": None})
    for response in (empty, only_latitude, null_name):
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION_ERROR"

    missing_confirmations = client.patch(
        path,
        headers=customer_headers,
        json={"final_latitude": -23.2, "final_longitude": -46.2},
    )
    assert missing_confirmations.status_code == 400
    assert missing_confirmations.json()["code"] == "INVALID_COORDINATES"
    assert set(missing_confirmations.json()["fields"]) == {
        "exact_point_selected",
        "map_provider",
        "map_type",
        "region_confirmed",
        "user_confirmed",
        "user_confirmed_safe_area",
    }

    false_confirmation = client.patch(
        path,
        headers=customer_headers,
        json={
            "final_latitude": -23.2,
            "final_longitude": -46.2,
            "map_provider": "maptiler",
            "map_type": "hybrid",
            "region_confirmed": True,
            "exact_point_selected": True,
            "user_confirmed": True,
            "user_confirmed_safe_area": False,
        },
    )
    assert false_confirmation.status_code == 400
    assert false_confirmation.json()["code"] == "INVALID_COORDINATES"

    invalid_map = client.patch(
        path,
        headers=customer_headers,
        json={
            "final_latitude": -23.2,
            "final_longitude": -46.2,
            "map_provider": "maptiler",
            "map_type": "streets",
            "region_confirmed": True,
            "exact_point_selected": True,
            "user_confirmed": True,
            "user_confirmed_safe_area": True,
        },
    )
    assert invalid_map.status_code == 400
    assert invalid_map.json()["code"] == "INVALID_COORDINATES"

    provenance_only = client.patch(
        path,
        headers=customer_headers,
        json={"map_type": "satellite"},
    )
    assert provenance_only.status_code == 400
    assert provenance_only.json()["code"] == "INVALID_COORDINATES"
    assert "final_latitude" in provenance_only.json()["fields"]


def test_create_saved_location_is_idempotent(
    client: TestClient,
    customer_headers: dict[str, str],
) -> None:
    headers = {**customer_headers, "Idempotency-Key": "saved-location-create-001"}
    first = client.post("/api/v1/saved-locations", headers=headers, json=_payload())
    replay = client.post("/api/v1/saved-locations", headers=headers, json=_payload())

    assert first.status_code == 201, first.text
    assert replay.status_code == 201, replay.text
    assert replay.json() == first.json()
    assert first.headers["Idempotency-Replayed"] == "false"
    assert replay.headers["Idempotency-Replayed"] == "true"
    listed = client.get("/api/v1/saved-locations", headers=customer_headers)
    assert len(listed.json()) == 1

    mismatch = client.post(
        "/api/v1/saved-locations",
        headers=headers,
        json={**_payload(), "name": "Outro conteúdo"},
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_order_from_saved_location_keeps_snapshot_after_edit_and_delete(
    client: TestClient,
    customer_headers: dict[str, str],
) -> None:
    saved_payload = {
        **_payload(),
        "name": "Casa",
        "map_type": "satellite",
        "final_latitude": -23.1234567,
        "final_longitude": -46.7654321,
        "address_reference": "Portão branco",
        "instructions": "Usar o marcador no quintal",
        "accuracy_meters": 4,
    }
    saved = _create_location(client, customer_headers, saved_payload)
    product_id = _first_product_id(client, customer_headers)
    order = client.post(
        "/api/v1/orders",
        headers=customer_headers,
        json={
            "saved_location_id": saved["id"],
            "saved_location_review_confirmed": True,
            "saved_location_safe_area_confirmed": True,
            "payment_method": "PIX",
            "items": [{"product_id": product_id, "quantity": 1}],
        },
    )
    assert order.status_code == 201, order.text
    order_body = order.json()
    snapshot = order_body["delivery_point"]
    assert order_body["delivery_point_id"] != saved["id"]
    assert snapshot["selection_source"] == "SAVED_POINT"
    assert snapshot["label"] == saved_payload["name"]
    assert float(snapshot["final_latitude"]) == saved_payload["final_latitude"]
    assert float(snapshot["final_longitude"]) == saved_payload["final_longitude"]
    assert snapshot["address_reference"] == saved_payload["address_reference"]
    assert snapshot["instructions"] == saved_payload["instructions"]
    assert snapshot["map_provider"] == saved_payload["map_provider"]
    assert snapshot["map_type"] == saved_payload["map_type"]
    assert snapshot["region_confirmed"] is True
    assert snapshot["exact_point_selected"] is True
    assert snapshot["user_confirmed"] is True
    assert snapshot["user_confirmed_safe_area"] is True

    changed = client.patch(
        f"/api/v1/saved-locations/{saved['id']}",
        headers=customer_headers,
        json={
            "name": "Casa nova",
            "final_latitude": -22.1,
            "final_longitude": -45.2,
            "instructions": "Nova instrução",
            "map_provider": "maptiler",
            "map_type": "hybrid",
            "region_confirmed": True,
            "exact_point_selected": True,
            "user_confirmed": True,
            "user_confirmed_safe_area": True,
        },
    )
    assert changed.status_code == 200, changed.text

    after_edit = client.get(
        f"/api/v1/orders/{order_body['id']}",
        headers=customer_headers,
    )
    assert after_edit.status_code == 200, after_edit.text
    edited_snapshot = after_edit.json()["delivery_point"]
    assert edited_snapshot["label"] == saved_payload["name"]
    assert float(edited_snapshot["final_latitude"]) == saved_payload["final_latitude"]
    assert float(edited_snapshot["final_longitude"]) == saved_payload["final_longitude"]
    assert edited_snapshot["instructions"] == saved_payload["instructions"]

    deleted = client.delete(
        f"/api/v1/saved-locations/{saved['id']}",
        headers=customer_headers,
    )
    assert deleted.status_code == 204
    after_delete = client.get(
        f"/api/v1/orders/{order_body['id']}",
        headers=customer_headers,
    )
    assert after_delete.status_code == 200, after_delete.text
    assert after_delete.json()["delivery_point"] == edited_snapshot


def test_order_rejects_foreign_saved_location_and_ambiguous_source(
    client: TestClient,
    customer_headers: dict[str, str],
    valid_point_payload: dict[str, object],
) -> None:
    other_headers = _register_and_login(client, "dono-local@example.com")
    foreign_saved = _create_location(client, other_headers)
    own_saved = _create_location(client, customer_headers, {**_payload(), "name": "Minha casa"})
    product_id = _first_product_id(client, customer_headers)
    base_order = {
        "payment_method": "PIX",
        "items": [{"product_id": product_id, "quantity": 1}],
    }

    foreign = client.post(
        "/api/v1/orders",
        headers=customer_headers,
        json={
            **base_order,
            "saved_location_id": foreign_saved["id"],
            "saved_location_review_confirmed": True,
            "saved_location_safe_area_confirmed": True,
        },
    )
    assert foreign.status_code == 404
    assert foreign.json()["code"] == "NOT_FOUND"

    missing_review = client.post(
        "/api/v1/orders",
        headers=customer_headers,
        json={**base_order, "saved_location_id": own_saved["id"]},
    )
    false_review = client.post(
        "/api/v1/orders",
        headers=customer_headers,
        json={
            **base_order,
            "saved_location_id": own_saved["id"],
            "saved_location_review_confirmed": True,
            "saved_location_safe_area_confirmed": False,
        },
    )
    assert missing_review.status_code == 422
    assert false_review.status_code == 422

    manual_point = client.post(
        "/api/v1/delivery-points",
        headers=customer_headers,
        json=valid_point_payload,
    )
    assert manual_point.status_code == 201, manual_point.text
    both = client.post(
        "/api/v1/orders",
        headers=customer_headers,
        json={
            **base_order,
            "delivery_point_id": manual_point.json()["id"],
            "saved_location_id": foreign_saved["id"],
            "saved_location_review_confirmed": True,
            "saved_location_safe_area_confirmed": True,
        },
    )
    neither = client.post(
        "/api/v1/orders",
        headers=customer_headers,
        json=base_order,
    )
    assert both.status_code == 422
    assert neither.status_code == 422

    manual_with_saved_review = client.post(
        "/api/v1/orders",
        headers=customer_headers,
        json={
            **base_order,
            "delivery_point_id": manual_point.json()["id"],
            "saved_location_review_confirmed": True,
            "saved_location_safe_area_confirmed": True,
        },
    )
    assert manual_with_saved_review.status_code == 422

    forged_owner = client.post(
        "/api/v1/orders",
        headers=customer_headers,
        json={
            **base_order,
            "saved_location_id": own_saved["id"],
            "saved_location_review_confirmed": True,
            "saved_location_safe_area_confirmed": True,
            "user_id": foreign_saved["user_id"],
        },
    )
    assert forged_owner.status_code == 422


def test_saved_location_order_idempotency_creates_one_snapshot(
    client: TestClient,
    customer_headers: dict[str, str],
) -> None:
    saved = _create_location(client, customer_headers)
    product_id = _first_product_id(client, customer_headers)
    headers = {**customer_headers, "Idempotency-Key": "saved-order-create-001"}
    payload = {
        "saved_location_id": saved["id"],
        "saved_location_review_confirmed": True,
        "saved_location_safe_area_confirmed": True,
        "payment_method": "PIX",
        "items": [{"product_id": product_id, "quantity": 1}],
    }

    first = client.post("/api/v1/orders", headers=headers, json=payload)
    replay = client.post("/api/v1/orders", headers=headers, json=payload)
    assert first.status_code == 201, first.text
    assert replay.status_code == 201, replay.text
    assert replay.json() == first.json()
    assert first.headers["Idempotency-Replayed"] == "false"
    assert replay.headers["Idempotency-Replayed"] == "true"

    with SessionLocal() as session:
        user_id = UUID(str(saved["user_id"]))
        point_count = session.scalar(
            select(func.count()).select_from(DeliveryPoint).where(DeliveryPoint.user_id == user_id)
        )
        order_count = session.scalar(
            select(func.count()).select_from(Order).where(Order.customer_id == user_id)
        )
    assert point_count == 1
    assert order_count == 1


def test_invalid_product_rolls_back_saved_location_snapshot(
    client: TestClient,
    customer_headers: dict[str, str],
) -> None:
    saved = _create_location(client, customer_headers)
    rejected = client.post(
        "/api/v1/orders",
        headers=customer_headers,
        json={
            "saved_location_id": saved["id"],
            "saved_location_review_confirmed": True,
            "saved_location_safe_area_confirmed": True,
            "payment_method": "PIX",
            "items": [{"product_id": str(uuid4()), "quantity": 1}],
        },
    )
    assert rejected.status_code == 404

    with SessionLocal() as session:
        user_id = UUID(str(saved["user_id"]))
        point_count = session.scalar(
            select(func.count()).select_from(DeliveryPoint).where(DeliveryPoint.user_id == user_id)
        )
        order_count = session.scalar(
            select(func.count()).select_from(Order).where(Order.customer_id == user_id)
        )
    assert point_count == 0
    assert order_count == 0


def test_saved_location_lock_compiles_to_for_no_key_update() -> None:
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    compiled = str(saved_location_creation_lock(user_id).compile(dialect=postgresql.dialect()))
    assert compiled.rstrip().endswith("FOR NO KEY UPDATE")
