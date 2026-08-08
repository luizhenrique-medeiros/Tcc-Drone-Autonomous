from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["AUTO_CREATE_SCHEMA"] = "true"
os.environ["JWT_SECRET"] = "test-secret-that-is-not-used-outside-tests"
os.environ["GATEWAY_API_KEY"] = "test-gateway-key"
os.environ["ADMIN_INITIAL_EMAIL"] = "admin@example.local"
os.environ["ADMIN_INITIAL_PASSWORD"] = "Admin-pass-123"
os.environ["MAX_MISSION_DISTANCE_M"] = "500"

from app.database.base import Base
from app.database.session import engine, import_models
from app.main import app


@pytest.fixture
def client() -> Generator[TestClient]:
    import_models()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def gateway_headers() -> dict[str, str]:
    return {"X-Gateway-API-Key": "test-gateway-key"}


def register_and_login(client: TestClient, email: str = "cliente@example.com") -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Cliente Teste",
            "email": email,
            "phone": "+5511999999999",
            "password": "Customer-pass-123",
            "role": "ADMIN",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["role"] == "CUSTOMER"
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Customer-pass-123"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def admin_login(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.local", "password": "Admin-pass-123"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["user"]["role"] == "ADMIN"
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def customer_headers(client: TestClient) -> dict[str, str]:
    return register_and_login(client)


@pytest.fixture
def admin_headers(client: TestClient) -> dict[str, str]:
    return admin_login(client)


@pytest.fixture
def valid_point_payload() -> dict[str, object]:
    return {
        "searched_address": "Base acadêmica",
        "address_reference": "Área aberta próxima à base",
        "selection_source": "ADDRESS_SEARCH",
        "approximate_latitude": -23.1175,
        "approximate_longitude": -46.5502,
        "final_latitude": -23.117,
        "final_longitude": -46.55,
        "label": "Ponto exato",
        "instructions": "Pousar no centro da área isolada",
        "map_provider": "maptiler",
        "map_type": "hybrid",
        "accuracy_meters": 3.0,
        "region_confirmed": True,
        "exact_point_selected": True,
        "user_confirmed": True,
        "user_confirmed_safe_area": True,
    }
