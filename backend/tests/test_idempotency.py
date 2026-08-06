from __future__ import annotations

from copy import deepcopy

from fastapi.testclient import TestClient


def test_delivery_point_replay_and_payload_mismatch(
    client: TestClient,
    customer_headers: dict[str, str],
    valid_point_payload: dict[str, object],
) -> None:
    headers = {**customer_headers, "Idempotency-Key": "attempt-001:point"}
    first = client.post("/api/v1/delivery-points", json=valid_point_payload, headers=headers)
    replay = client.post("/api/v1/delivery-points", json=valid_point_payload, headers=headers)

    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()
    assert first.headers["idempotency-replayed"] == "false"
    assert replay.headers["idempotency-replayed"] == "true"
    listed = client.get("/api/v1/delivery-points", headers=customer_headers)
    assert len(listed.json()) == 1

    changed = deepcopy(valid_point_payload)
    changed["label"] = "Outro ponto"
    mismatch = client.post("/api/v1/delivery-points", json=changed, headers=headers)
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert mismatch.json()["fields"] == {"Idempotency-Key": "payload_mismatch"}


def test_order_and_submit_are_replayed_without_duplicate_side_effects(
    client: TestClient,
    customer_headers: dict[str, str],
    valid_point_payload: dict[str, object],
) -> None:
    point = client.post(
        "/api/v1/delivery-points",
        json=valid_point_payload,
        headers={**customer_headers, "Idempotency-Key": "attempt-002:point"},
    ).json()
    product = client.get("/api/v1/products", headers=customer_headers).json()[0]
    payload = {
        "delivery_point_id": point["id"],
        "payment_method": "PIX",
        "items": [{"product_id": product["id"], "quantity": 1}],
    }
    order_headers = {**customer_headers, "Idempotency-Key": "attempt-002:order"}
    first = client.post("/api/v1/orders", json=payload, headers=order_headers)
    replay = client.post("/api/v1/orders", json=payload, headers=order_headers)
    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()
    assert replay.headers["idempotency-replayed"] == "true"
    assert len(client.get("/api/v1/orders", headers=customer_headers).json()) == 1

    changed = deepcopy(payload)
    changed["items"][0]["quantity"] = 2
    mismatch = client.post("/api/v1/orders", json=changed, headers=order_headers)
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "IDEMPOTENCY_KEY_REUSED"

    submit_headers = {**customer_headers, "Idempotency-Key": "attempt-002:submit"}
    submitted = client.post(f"/api/v1/orders/{first.json()['id']}/submit", headers=submit_headers)
    submit_replay = client.post(
        f"/api/v1/orders/{first.json()['id']}/submit", headers=submit_headers
    )
    assert submitted.status_code == submit_replay.status_code == 200
    assert submitted.json() == submit_replay.json()
    assert submit_replay.json()["status"] == "PENDING_ADMIN_APPROVAL"
    assert submit_replay.headers["idempotency-replayed"] == "true"


def test_cors_allows_idempotency_header(client: TestClient) -> None:
    response = client.options(
        "/api/v1/orders",
        headers={
            "Origin": "http://localhost:5174",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type,idempotency-key",
        },
    )
    assert response.status_code == 200
    allowed = response.headers["access-control-allow-headers"].lower()
    assert "idempotency-key" in allowed
