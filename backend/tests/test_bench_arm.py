from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.router import api_router
from app.api.v1.routers.bench_arm import router as experimental_arm_router
from app.core.config import get_settings
from app.main import app as operational_app

app = FastAPI(exception_handlers=operational_app.exception_handlers)
app.include_router(api_router)
app.include_router(experimental_arm_router, prefix="/api/v1")

ADMIN = "/api/v1/admin/bench-arm"
GATEWAY = "/api/v1/gateway/bench-arm"


@pytest.fixture
def client(client: TestClient) -> TestClient:
    # The parent fixture initializes the database only. The lab routes stay on this test app.
    return TestClient(app)


@pytest.fixture
def bench_profile():
    original = get_settings()
    app.dependency_overrides[get_settings] = lambda: original.model_copy(
        update={
            "px4_bench_arm_enabled": True,
            "px4_bench_arm_vehicle_identifier": "test-pixhawk",
        }
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_settings)


@pytest.fixture
def publish(client, gateway_headers):
    session_id = str(uuid4())

    def heartbeat(*, armed=False, **overrides):
        response = client.post(
            "/api/v1/gateway/heartbeat",
            headers=gateway_headers,
            json={
                "gateway_id": gateway_headers["X-Gateway-ID"],
                "vehicle_identifier": "test-pixhawk",
                "autopilot_system": "PX4",
                "source": "HARDWARE_REAL",
                "connection_mode": "px4_bench_arm",
                "connected": True,
                "heartbeat": True,
                "armed": armed,
                "last_heartbeat_at": datetime.now(UTC).isoformat(),
                "mavlink_system_id": 1,
                "mavlink_component_id": 42,
                "vehicle_arm_enabled": True,
                "bench_arm_session_id": session_id,
                **overrides,
            },
        )
        assert response.status_code == 200, response.text
        return response.json()

    return heartbeat, session_id


@pytest.mark.parametrize(
    ("ack", "observed", "status"),
    [(0, True, "CONFIRMED"), (2, False, "REJECTED"), (None, True, "UNCONFIRMED")],
)
def test_bench_queue_lifecycle(
    client, admin_headers, gateway_headers, bench_profile, publish, ack, observed, status
):
    heartbeat, session_id = publish
    vehicle = heartbeat()["vehicle"]["id"]
    payload = {"session_id": session_id, "confirmed": True}
    headers = {**admin_headers, "Idempotency-Key": str(uuid4())}
    sent = client.post(f"{ADMIN}/{vehicle}", headers=headers, json=payload)
    assert sent.status_code == 202, sent.text
    assert client.post(f"{ADMIN}/{vehicle}", headers=headers, json=payload).json() == sent.json()
    conflicting = {**admin_headers, "Idempotency-Key": str(uuid4())}
    assert client.post(f"{ADMIN}/{vehicle}", headers=conflicting, json=payload).status_code == 409

    claim = {"vehicle_id": vehicle, "session_id": session_id}
    assert (
        client.post(
            f"{GATEWAY}/claim",
            headers=gateway_headers,
            json={
                **claim,
                "session_id": str(uuid4()),
            },
        ).json()
        is None
    )
    claimed = client.post(f"{GATEWAY}/claim", headers=gateway_headers, json=claim).json()
    assert claimed["id"] == sent.json()["id"]
    assert claimed["target_component"] == 42
    assert client.post(f"{GATEWAY}/claim", headers=gateway_headers, json=claim).json() is None

    proof = heartbeat(armed=observed)
    report = {
        "transmitted": True,
        "ack_result": ack,
        "confirmed_snapshot_id": proof["health"]["id"] if ack == 0 else None,
        "detail": "Resultado do transporte de teste",
    }
    result_path = f"{GATEWAY}/{claimed['id']}/result"
    for _ in range(2):
        result = client.post(result_path, headers=gateway_headers, json=report)
        assert result.status_code == 204, result.text
    read = client.get(ADMIN, headers=admin_headers).json()
    assert read["request"]["status"] == status
    assert read["target"]["armed"] == observed
    assert read["request"]["ack_result"] == ack


def test_reconnection_and_authentication_fail_closed(
    client: TestClient, admin_headers, gateway_headers, customer_headers, bench_profile, publish
):
    heartbeat, session_id = publish
    vehicle = heartbeat()["vehicle"]["id"]
    payload = {"session_id": session_id, "confirmed": True}
    headers = {**admin_headers, "Idempotency-Key": str(uuid4())}
    assert (
        client.post(
            f"{ADMIN}/{vehicle}",
            headers={
                **customer_headers,
                "Idempotency-Key": str(uuid4()),
            },
            json=payload,
        ).status_code
        == 403
    )
    assert client.post(f"{ADMIN}/{vehicle}", headers=headers, json=payload).status_code == 202
    new_session_id = str(uuid4())
    heartbeat(bench_arm_session_id=new_session_id)
    claim = {"vehicle_id": vehicle, "session_id": new_session_id}
    assert (
        client.post(
            f"{GATEWAY}/claim",
            headers={
                **gateway_headers,
                "X-Gateway-ID": "intruder",
            },
            json=claim,
        ).status_code
        == 401
    )
    assert client.post(f"{GATEWAY}/claim", headers=gateway_headers, json=claim).json() is None
    assert client.get(ADMIN, headers=admin_headers).json()["request"]["status"] == "EXPIRED"


def test_disabled_profile(client: TestClient, admin_headers):
    assert client.get(ADMIN, headers=admin_headers).json()["enabled"] is False
    assert (
        client.post(
            f"{ADMIN}/{uuid4()}",
            headers={
                **admin_headers,
                "Idempotency-Key": str(uuid4()),
            },
            json={"confirmed": True, "session_id": str(uuid4())},
        ).status_code
        == 404
    )
