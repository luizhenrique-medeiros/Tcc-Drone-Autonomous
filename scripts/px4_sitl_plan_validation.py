"""Exercise the administrative HTTP flow against PX4 in an isolated SITL container."""

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import httpx

from app.clients.backend_client import BackendClient
from app.core.config import Settings
from app.mavlink.pymavlink_gateway import PymavlinkVehicleGateway
from app.missions.executor import MissionExecutor
from app.models import VehicleHealth


def prepare_and_request_upload(
    api: httpx.Client, health: VehicleHealth, vehicle_id: str, password: str
) -> tuple[str, str]:
    assert health.current_latitude is not None and health.current_longitude is not None

    def post(path: str, data: dict, headers: dict | None = None) -> dict:
        response = api.post(path, json=data, headers=headers)
        if not response.is_success:
            raise RuntimeError(f"{path}: {response.status_code} {response.text}")
        return response.json()

    def login(email: str) -> dict[str, str]:
        token = post("/auth/login", {"email": email, "password": password})["access_token"]
        return {"Authorization": f"Bearer {token}"}

    email = f"sitl-{uuid4().hex[:8]}@example.test"
    post(
        "/auth/register",
        {
            "email": email,
            "password": password,
            "name": "Cliente SITL",
            "phone": "+5511999999999",
        },
    )
    customer = login(email)
    admin = login("admin@sitl.example")
    point = post(
        "/delivery-points",
        {
            "searched_address": "Referência sintética do simulador",
            "selection_source": "ADDRESS_SEARCH",
            "approximate_latitude": health.current_latitude,
            "approximate_longitude": health.current_longitude,
            "final_latitude": round(health.current_latitude + 0.0001, 7),
            "final_longitude": round(health.current_longitude + 0.0001, 7),
            "label": "Waypoint SITL",
            "instructions": "Destino sintético em rede isolada.",
            "map_provider": "maptiler",
            "map_type": "hybrid",
            "accuracy_meters": 3,
            "region_confirmed": True,
            "exact_point_selected": True,
            "user_confirmed": True,
            "user_confirmed_safe_area": True,
        },
        customer,
    )
    products = api.get("/products", headers=customer).raise_for_status().json()
    order = post(
        "/orders",
        {
            "delivery_point_id": point["id"],
            "payment_method": "PIX",
            "items": [{"product_id": products[0]["id"], "quantity": 1}],
        },
        customer,
    )
    post(f"/orders/{order['id']}/submit", {}, customer)
    post(f"/admin/orders/{order['id']}/approve", {}, admin)
    mission = post(f"/admin/orders/{order['id']}/prepare-mission", {}, admin)
    path = f"/admin/missions/{mission['id']}"
    draft = post(
        f"{path}/qgroundcontrol-draft",
        {"vehicle_id": vehicle_id, "home_amsl_m": 488},
        admin,
    )
    waypoint = draft["mission"]["items"][1]
    assert waypoint["command"] == 16 and waypoint["params"][0] == 5
    waypoint["Altitude"] = waypoint["params"][6] = 9.5
    review = post(
        f"{path}/qgroundcontrol-review",
        {
            "expected_version": mission["version"],
            "expected_sha256": mission["mission_sha256"],
            "plan": json.dumps(draft),
            "confirmed": True,
        },
        admin,
    )
    detail = api.get(path, headers=admin).raise_for_status().json()
    assert detail["qgroundcontrol_sitl_review_event_id"] == review["event_id"]
    upload_headers = {**admin, "Idempotency-Key": str(uuid4())}
    payload = {
        "vehicle_id": vehicle_id,
        "qgroundcontrol_review_event_id": review["event_id"],
        "confirmed": True,
    }
    assert (
        api.post(
            f"{path}/px4-sitl/upload",
            headers={**customer, "Idempotency-Key": str(uuid4())},
            json=payload,
        ).status_code
        == 403
    )
    uploaded = post(f"{path}/px4-sitl/upload", payload, upload_headers)
    assert uploaded["status"] == "AUTHORIZED"
    assert post(f"{path}/px4-sitl/upload", payload, upload_headers) == uploaded
    print("Upload explícito aceito pela API; repetição devolveu a mesma solicitação.", flush=True)
    return mission["id"], admin["Authorization"]


async def main() -> None:
    settings = Settings(
        _env_file=None,
        px4_sitl_plan_validation=True,
        autopilot_system="PX4",
        gateway_runtime="container",
        mavlink_mode="sitl",
        mavlink_connection="udpin:127.0.0.1:14550",
        mavlink_dialect="common",
        api_base_url="http://127.0.0.1:18081",
        gateway_api_key=os.environ["PX4_VALIDATION_GATEWAY_KEY"],
        gateway_id="gateway-sitl-1",
        vehicle_identifier=f"isolated-px4-{uuid4().hex[:8]}",
        allow_mission_upload=True,
        allow_flight_commands=True,
        allow_vehicle_arm=True,
        allow_mission_start=True,
        mission_command_timeout_seconds=8,
        mission_protocol_step_timeout_seconds=3,
        gateway_journal_path=Path(f"/tmp/px4-review-{uuid4().hex}.json"),
    )
    vehicle = PymavlinkVehicleGateway(settings)
    backend = BackendClient(settings)
    try:
        await vehicle.connect()
        for _ in range(36):
            health = await vehicle.read_health()
            if (
                health.armed is False
                and health.current_latitude is not None
                and health.current_longitude is not None
            ):
                break
            await asyncio.sleep(0.5)
        else:
            raise RuntimeError("PX4 SITL não publicou posição e heartbeat desarmado.")
        heartbeat = await backend.heartbeat(health)
        with httpx.Client(base_url=f"{settings.api_base_url}/api/v1") as api:
            mission_id, authorization = await asyncio.to_thread(
                prepare_and_request_upload,
                api,
                health,
                str(heartbeat.vehicle.id),
                os.environ["PX4_VALIDATION_ADMIN_PASSWORD"],
            )
            executor = MissionExecutor(settings, backend, vehicle)
            admin = {"Authorization": authorization}
            path = f"/admin/missions/{mission_id}"

            async def get_json(endpoint: str) -> dict:
                response = await asyncio.to_thread(api.get, endpoint, headers=admin)
                return response.raise_for_status().json()

            for _ in range(10):
                await executor.run_cycle()
                status = (await get_json(path))["status"]
                if status == "VERIFIED":
                    break
                if status == "FAILED":
                    raise RuntimeError("Gateway failed to validate or upload the reviewed plan.")
                await asyncio.sleep(1)
            else:
                raise RuntimeError(f"Readback was not confirmed; final mission state: {status}")
            assert (await vehicle.read_health()).armed is False
            print("PX4 aceitou o upload e a releitura conferiu a rota: VERIFIED.", flush=True)

            async def command(
                action: str, headers: dict[str, str], *, confirmed: bool = True
            ) -> httpx.Response:
                return await asyncio.to_thread(
                    api.post,
                    f"{path}/px4-sitl/commands/{action}",
                    headers=headers,
                    json={"confirmed": confirmed},
                )

            def action_headers() -> dict[str, str]:
                return {**admin, "Idempotency-Key": str(uuid4())}

            assert (await command("ARM", action_headers(), confirmed=False)).status_code == 422
            assert (await command("START", action_headers())).status_code == 409
            await vehicle.close()
            disconnected = await vehicle.read_health()
            assert not disconnected.connected and not disconnected.heartbeat
            await backend.heartbeat(disconnected)
            assert (await command("ARM", action_headers())).status_code == 409
            await vehicle.connect()
            await backend.heartbeat(await vehicle.read_health())
            print("API rejeitou confirmação falsa, START desarmado e ARM sem enlace.", flush=True)

            async def execute(action: str, expected_status: str = "COMPLETED") -> dict:
                headers = action_headers()
                queued = (await command(action, headers)).raise_for_status().json()
                assert queued["status"] == "PENDING"
                assert (await command(action, headers)).raise_for_status().json() == queued
                await executor.run_cycle()
                result = await get_json(f"{path}/commands/{queued['id']}")
                print(f"{action}: {result['status']} · {result['result_detail']}", flush=True)
                assert result["status"] == expected_status, result
                return result

            connection = vehicle._required_connection()
            with patch.object(connection.mav, "command_long_send") as dropped:
                timeout = await execute("ARM", "FAILED")
                assert "COMMAND_ACK" in timeout["result_detail"]
                assert dropped.call_count == 1
            assert (await vehicle.read_health()).armed is False
            print(
                "Perda simulada do pacote ARM: um envio, timeout auditado, sem reenvio.", flush=True
            )

            await execute("ARM")
            await execute("START")
            assert (await get_json(path))["status"] == "EXECUTING"
            # Drain the UDP receive buffer frequently enough to keep individual
            # waypoint transitions and fresh heartbeats during a simulated flight.
            for _ in range(400):
                await executor.run_cycle()
                mission = await get_json(path)
                if mission["status"] in {"DESTINATION_REACHED", "RETURNING", "COMPLETED"}:
                    break
                await asyncio.sleep(0.15)
            else:
                raise RuntimeError("PX4 não confirmou o waypoint do pedido.")
            if mission["status"] == "DESTINATION_REACHED":
                await execute("RTL")
            order = await get_json(f"/admin/orders/{mission['order_id']}")
            assert order["status"] in {"AT_DESTINATION", "RETURNING", "COMPLETED"}, order["status"]
            print(f"Progresso vinculado ao pedido: {order['status']}.", flush=True)
            for _ in range(650):
                await executor.run_cycle()
                mission = await get_json(path)
                if mission["status"] == "COMPLETED":
                    assert (await vehicle.read_health()).armed is False
                    print("Pouso e desarmamento do PX4 confirmados; missão concluída.", flush=True)
                    break
                await asyncio.sleep(0.15)
            else:
                raise RuntimeError("Voo SITL sem confirmação de pouso e desarmamento na API.")
    finally:
        await backend.close()
        await vehicle.close()


if __name__ == "__main__":
    asyncio.run(main())
