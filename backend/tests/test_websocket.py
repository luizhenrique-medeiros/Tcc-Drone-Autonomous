from fastapi.testclient import TestClient


def test_admin_websocket_authenticates_in_first_message(client: TestClient) -> None:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.local", "password": "Admin-pass-123"},
    )
    token = login.json()["access_token"]
    with client.websocket_connect("/api/v1/ws/admin/operations") as websocket:
        websocket.send_json({"type": "AUTH", "token": token})
        assert websocket.receive_json() == {"type": "operations.connected"}
        websocket.send_text("ping")
        assert websocket.receive_json() == {"type": "pong"}


def test_websocket_ignores_query_token_and_requires_auth_message(client: TestClient) -> None:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.local", "password": "Admin-pass-123"},
    )
    token = login.json()["access_token"]
    with client.websocket_connect(
        "/api/v1/ws/admin/operations?token=must-not-be-read"
    ) as websocket:
        websocket.send_json({"type": "AUTH", "token": token})
        assert websocket.receive_json() == {"type": "operations.connected"}
