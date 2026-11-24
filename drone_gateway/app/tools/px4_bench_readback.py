"""Submit and service a local, read-only PX4 bench verification."""

import argparse
import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.core.exceptions import GatewayError
from app.mavlink.pymavlink_gateway import PymavlinkVehicleGateway
from app.models import MissionWaypoint, VehicleEvent

logger = logging.getLogger(__name__)
REQUEST_LIFETIME_SECONDS = 30
MAX_PLAN_BYTES = 65536


class ReadbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system_id: StrictInt = Field(ge=1, le=255)
    component_id: StrictInt = Field(ge=1, le=255)
    plan: str = Field(min_length=1, max_length=MAX_PLAN_BYTES)


def default_directory() -> Path:
    return Path(os.environ["LOCALAPPDATA"]) / "DevCoreMavlinkRouter" / "bench"


def _write_atomic(path: Path, content: str) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _parse_waypoints(plan: bytes) -> list[MissionWaypoint]:
    if not plan or len(plan) > MAX_PLAN_BYTES:
        raise ValueError("O arquivo .plan deve ter até 64 KiB.")
    document = json.loads(plan)
    if document.get("fileType") != "Plan" or document["mission"].get("firmwareType") != 12:
        raise ValueError("Selecione um arquivo .plan do QGroundControl para PX4.")
    items = document["mission"]["items"]
    if items and items[0].get("command") == 530:
        items = items[1:]
    if not 1 <= len(items) <= 20 or any(item["type"] != "SimpleItem" for item in items):
        raise ValueError("A releitura aceita de 1 a 20 itens simples do plano.")
    waypoints = []
    for sequence, item in enumerate(items):
        hold, radius, pass_radius, yaw, latitude, longitude, altitude = item["params"]
        command = item["command"]
        if command not in {16, 19, 20, 21, 22}:
            raise ValueError(f"Item {sequence}: comparação indisponível para o comando {command}.")
        if command != 20 and any(value is None for value in (latitude, longitude, altitude)):
            raise ValueError(f"Item {sequence}: coordenadas e altitude ausentes.")
        waypoints.append(
            MissionWaypoint(
                sequence=sequence,
                command=command,
                frame=item["frame"],
                autocontinue=int(item["autoContinue"]),
                param1=0 if hold is None else hold,
                param2=0 if radius is None else radius,
                param3=0 if pass_radius is None else pass_radius,
                param4=yaw,
                latitude=0 if latitude is None else latitude,
                longitude=0 if longitude is None else longitude,
                altitude_m=0 if altitude is None else altitude,
            )
        )
    return waypoints


def _next_request(directory: Path) -> Path | None:
    return next(directory.glob("request-*.json"), None)


def _read_request(path: Path) -> ReadbackRequest:
    if time.time() - path.stat().st_mtime > REQUEST_LIFETIME_SECONDS:
        raise ValueError("Solicitação de bancada expirada.")
    with path.open("rb") as source:
        return ReadbackRequest.model_validate_json(source.read(MAX_PLAN_BYTES * 6 + 1024))


def _finish_request(claimed: Path, response: Path, result: dict[str, object]) -> None:
    _write_atomic(response, json.dumps(result, ensure_ascii=False))
    claimed.unlink(missing_ok=True)


async def service_next_readback(
    directory: Path, vehicle: PymavlinkVehicleGateway
) -> VehicleEvent | None:
    path = await asyncio.to_thread(_next_request, directory)
    if path is None:
        return
    try:
        identifier = UUID(path.stem.removeprefix("request-"))
    except ValueError:
        return
    claimed = path.with_suffix(".processing")
    try:
        await asyncio.to_thread(path.replace, claimed)
    except FileNotFoundError:
        return
    result: dict[str, object] = {"verified": False}
    observation = None
    try:
        request = await asyncio.to_thread(_read_request, claimed)
        plan = request.plan.encode("utf-8")
        waypoints = _parse_waypoints(plan)
        native_plan_id = await vehicle.verify_bench_readback(
            waypoints, request.system_id, request.component_id
        )
        evidence = {
            "system_id": request.system_id,
            "component_id": request.component_id,
            "plan_sha256": hashlib.sha256(plan).hexdigest(),
            "item_count": len(waypoints),
            "native_plan_id": native_plan_id,
        }
        result = {"verified": True, **evidence}
        # A new readback without an ID also supersedes any older evidence.
        observation = VehicleEvent(
            event_type="PX4_PHYSICAL_PLAN_READBACK",
            severity="INFO",
            message="A releitura da missão física conferiu o arquivo revisado.",
            metadata=evidence,
            occurred_at=datetime.now(UTC),
        )
    except (GatewayError, KeyError, TypeError, ValueError, OSError) as exc:
        result["detail"] = str(exc)
    finally:
        await asyncio.to_thread(
            _finish_request, claimed, directory / f"result-{identifier}.json", result
        )
    logger.info("Releitura de bancada concluída", extra={"verified": result["verified"]})
    return observation


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Conferir um .plan com a missão gravada na Pixhawk."
    )
    parser.add_argument("plan", type=Path)
    parser.add_argument("--system-id", type=int, required=True)
    parser.add_argument("--component-id", type=int, required=True)
    args = parser.parse_args()
    try:
        with args.plan.open("rb") as plan:
            plan_bytes = plan.read(MAX_PLAN_BYTES + 1)
        _parse_waypoints(plan_bytes)
        request = ReadbackRequest(
            system_id=args.system_id,
            component_id=args.component_id,
            plan=plan_bytes.decode("utf-8"),
        )
        directory = default_directory()
        if not directory.is_dir():
            raise ValueError("O diretório de releitura do gateway Windows está indisponível.")
        identifier = uuid4()
        path = directory / f"request-{identifier}.json"
        response = directory / f"result-{identifier}.json"
        _write_atomic(path, request.model_dump_json())
        try:
            deadline = time.monotonic() + 65
            while time.monotonic() < deadline:
                if response.is_file():
                    result = json.loads(response.read_text(encoding="utf-8"))
                    response.unlink()
                    print(json.dumps(result, ensure_ascii=False))
                    raise SystemExit(0 if result["verified"] else 1)
                time.sleep(0.25)
            raise ValueError("O gateway não devolveu um resultado de releitura dentro do prazo.")
        finally:
            path.unlink(missing_ok=True)
    except (KeyError, TypeError, ValueError, OSError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
