from copy import deepcopy

from fastapi.testclient import TestClient


def test_requires_second_step_and_satellite_confirmation(
    client: TestClient,
    customer_headers: dict[str, str],
    valid_point_payload: dict[str, object],
) -> None:
    payload = deepcopy(valid_point_payload)
    payload["exact_point_selected"] = False
    response = client.post(
        "/api/v1/delivery-points/validate", json=payload, headers=customer_headers
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_COORDINATES"

    payload = deepcopy(valid_point_payload)
    payload["map_type"] = "normal"
    response = client.post(
        "/api/v1/delivery-points/validate", json=payload, headers=customer_headers
    )
    assert response.status_code == 400


def test_validates_and_persists_final_point(
    client: TestClient,
    customer_headers: dict[str, str],
    valid_point_payload: dict[str, object],
) -> None:
    validation = client.post(
        "/api/v1/delivery-points/validate",
        json=valid_point_payload,
        headers=customer_headers,
    )
    assert validation.status_code == 200, validation.text
    assert validation.json()["within_coverage"] is True
    assert validation.json()["max_distance_m"] is None
    assert float(validation.json()["distance_from_base_m"]) > 0

    created = client.post(
        "/api/v1/delivery-points", json=valid_point_payload, headers=customer_headers
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert float(body["final_latitude"]) == valid_point_payload["final_latitude"]
    assert body["exact_point_selected"] is True

    listed = client.get("/api/v1/delivery-points", headers=customer_headers)
    assert listed.status_code == 200
    assert [point["id"] for point in listed.json()] == [body["id"]]


def test_accepts_distant_point_and_submits_order(
    client: TestClient,
    customer_headers: dict[str, str],
    valid_point_payload: dict[str, object],
) -> None:
    payload = deepcopy(valid_point_payload)
    payload.update(
        {
            "searched_address": "Bom Jesus dos Perdões, SP",
            "address_reference": "Ponto remoto de validação",
            "approximate_latitude": -22.5972,
            "approximate_longitude": -46.2770,
            "final_latitude": -22.5970,
            "final_longitude": -46.2768,
        }
    )

    validation = client.post(
        "/api/v1/delivery-points/validate", json=payload, headers=customer_headers
    )
    assert validation.status_code == 200, validation.text
    assert validation.json()["valid"] is True
    assert validation.json()["within_coverage"] is True
    assert validation.json()["max_distance_m"] is None
    assert float(validation.json()["distance_from_base_m"]) > 500

    point = client.post("/api/v1/delivery-points", json=payload, headers=customer_headers)
    assert point.status_code == 201, point.text

    products = client.get("/api/v1/products", headers=customer_headers)
    assert products.status_code == 200, products.text
    order = client.post(
        "/api/v1/orders",
        headers=customer_headers,
        json={
            "delivery_point_id": point.json()["id"],
            "payment_method": "PIX",
            "items": [{"product_id": products.json()[0]["id"], "quantity": 1}],
        },
    )
    assert order.status_code == 201, order.text

    submitted = client.post(f"/api/v1/orders/{order.json()['id']}/submit", headers=customer_headers)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "PENDING_ADMIN_APPROVAL"
