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


def test_validates_coverage_and_persists_final_point(
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


def test_rejects_point_outside_coverage(
    client: TestClient,
    customer_headers: dict[str, str],
    valid_point_payload: dict[str, object],
) -> None:
    payload = deepcopy(valid_point_payload)
    payload["final_latitude"] = -22.9
    response = client.post("/api/v1/delivery-points", json=payload, headers=customer_headers)
    assert response.status_code == 422
    assert response.json()["code"] == "OUTSIDE_COVERAGE"
