import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from app.clients.backend_client import BackendClient
from app.core.config import Settings
from app.core.exceptions import BackendContractError
from app.models import HeartbeatResponse, VehicleHealth


def healthy_vehicle() -> VehicleHealth:
    return VehicleHealth(
        connected=True,
        heartbeat=True,
        gps_fix_type=3,
        satellites=14,
        ekf_ok=True,
        battery_percent=80,
        flight_mode="AUTO",
        armed=False,
        preflight_ok=True,
        rtl_configured=True,
        geofence_enabled=True,
        origin_latitude=-23.1175,
        origin_longitude=-46.5502,
    )


@pytest.mark.asyncio
async def test_heartbeat_rejects_invalid_success_json() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text="not-json", request=request)
    )
    async with httpx.AsyncClient(base_url="http://backend", transport=transport) as http:
        client = BackendClient(Settings(_env_file=None), http)

        with pytest.raises(BackendContractError, match="JSON"):
            await client.heartbeat(healthy_vehicle())


@pytest.mark.asyncio
async def test_heartbeat_rejects_invalid_success_schema() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"vehicle": {"id": str(uuid4())}},
            request=request,
        )
    )
    async with httpx.AsyncClient(base_url="http://backend", transport=transport) as http:
        client = BackendClient(Settings(_env_file=None), http)

        with pytest.raises(BackendContractError, match="HeartbeatResponse"):
            await client.heartbeat(healthy_vehicle())


@pytest.mark.asyncio
async def test_heartbeat_returns_typed_contract() -> None:
    vehicle_id = uuid4()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "vehicle": {
                    "id": str(vehicle_id),
                    "identifier": "academic-vehicle-01",
                    "gateway_id": "dev-gateway-01",
                },
                "authorization_eligible": True,
                "failures": [],
            },
            request=request,
        )
    )
    async with httpx.AsyncClient(base_url="http://backend", transport=transport) as http:
        client = BackendClient(Settings(_env_file=None), http)

        result = await client.heartbeat(healthy_vehicle())

    assert isinstance(result, HeartbeatResponse)
    assert result.vehicle.id == vehicle_id


@pytest.mark.asyncio
async def test_event_payload_stays_within_backend_severity_contract() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={}, request=request)

    occurred_at = datetime.now(UTC)
    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(base_url="http://backend", transport=transport) as http:
        client = BackendClient(Settings(_env_file=None), http)
        await client.report_event(
            uuid4(),
            event_type="MAVLINK_STATUSTEXT",
            severity="CRITICAL",
            message="failsafe",
            occurred_at=occurred_at,
        )

    assert captured["severity"] == "ERROR"
    assert "occurred_at" not in captured
    assert captured["metadata"] == {"source_occurred_at": occurred_at.isoformat()}
