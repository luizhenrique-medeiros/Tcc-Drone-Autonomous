"""Manual PX4 protocol probe; run only inside a network-isolated Linux container.

This deliberately exercises private adapter methods without enabling production
gates. It never arms, starts a mission, or contacts the backend.
"""

import asyncio
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from app.core.config import Settings
from app.core.exceptions import MissionUploadError
from app.mavlink.pymavlink_gateway import PymavlinkVehicleGateway
from app.models import AuthorizedMission, MissionStatus, MissionWaypoint


def assert_isolated() -> None:
    if os.environ.get("DEVCORE_ISOLATED_SITL_PROBE") != "1":
        raise RuntimeError("Explicit isolated SITL probe confirmation is required.")
    if not Path("/.dockerenv").is_file() or {
        p.name for p in Path("/sys/class/net").iterdir()
    } != {"lo"}:
        raise RuntimeError(
            "Refusing to run outside a container with loopback as its only interface."
        )


def synthetic_route() -> list[MissionWaypoint]:
    origin = (47.397742, 8.545594)
    destination = (47.397842, 8.545694)
    return [
        MissionWaypoint(
            sequence=0,
            command=22,
            param4=None,
            latitude=origin[0],
            longitude=origin[1],
            altitude_m=10,
        ),
        MissionWaypoint(
            sequence=1,
            command=16,
            param4=None,
            latitude=destination[0],
            longitude=destination[1],
            altitude_m=10,
        ),
        MissionWaypoint(
            sequence=2, command=20, frame=2, latitude=0, longitude=0, altitude_m=0
        ),
    ]


def reviewed_route(path: Path, expected_sha256: str) -> list[MissionWaypoint]:
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != expected_sha256:
        raise ValueError("O hash do candidato diverge do hash da revisão.")
    candidate = json.loads(content)
    if candidate["format"] != "devcore-px4-mission-candidate-v1":
        raise ValueError("Formato de candidato inválido.")
    items = candidate["items"]
    if [item["command"] for item in items] != [22, 16, 20]:
        raise ValueError("Este teste exige uma rota sintética de três itens.")
    points = []
    for item in items:
        param1, param2, param3, param4, latitude, longitude, altitude = item["params"]
        points.append(
            MissionWaypoint(
                sequence=item["sequence"],
                command=item["command"],
                frame=item["frame"],
                autocontinue=int(item["autocontinue"]),
                param1=param1,
                param2=param2,
                param3=param3,
                param4=param4,
                latitude=latitude,
                longitude=longitude,
                altitude_m=altitude,
            )
        )
    return points


async def main() -> None:
    assert_isolated()
    settings = Settings(
        _env_file=None,
        autopilot_system="PX4",
        mavlink_mode="mavlink_router",
        mavlink_connection="udpin:127.0.0.1:14610",
        mission_command_timeout_seconds=25,
        mission_protocol_step_timeout_seconds=3,
    )
    candidate_path = os.environ.get("DEVCORE_SITL_CANDIDATE")
    if candidate_path:
        candidate_hash = os.environ["DEVCORE_SITL_CANDIDATE_SHA256"]
        points = reviewed_route(Path(candidate_path), candidate_hash)
        print("Candidate hash verified before connecting to SITL", flush=True)
    else:
        candidate_hash = "0" * 64
        points = synthetic_route()
    gateway = PymavlinkVehicleGateway(settings)
    takeoff, destination, _rtl = points
    mission = AuthorizedMission(
        id=uuid4(),
        order_id=uuid4(),
        status=MissionStatus.AUTHORIZED,
        origin_latitude=takeoff.latitude,
        origin_longitude=takeoff.longitude,
        destination_latitude=destination.latitude,
        destination_longitude=destination.longitude,
        takeoff_altitude_m=takeoff.altitude_m,
        estimated_distance_m=20,
        mission_sha256=candidate_hash,
        version=1,
        waypoints=points,
    )
    try:
        await gateway.connect()
        print(
            "PX4 heartbeat received; uploading synthetic route to isolated simulator",
            flush=True,
        )
        # Private protocol methods bypass public safety gates strictly in this isolated probe.
        gateway._passive_connection = False
        await asyncio.to_thread(gateway._upload_sync, mission)
        print("MISSION_ACK accepted; reading stored mission back", flush=True)
        await asyncio.to_thread(gateway._verify_mission_sync, mission)
        print("Stored mission matches all three items", flush=True)
        altered = destination.model_copy(
            update={"latitude": destination.latitude + 0.001}
        )
        altered_mission = mission.model_copy(
            update={"waypoints": [points[0], altered, points[2]]}
        )
        try:
            await asyncio.to_thread(gateway._verify_mission_sync, altered_mission)
        except MissionUploadError as exc:
            if "Coordenadas relidas divergem" not in str(exc):
                raise
            print("Changed waypoint correctly rejected by readback", flush=True)
        else:
            raise RuntimeError("Changed waypoint was incorrectly accepted")
        altered_yaw = points[1].model_copy(update={"param4": 0})
        altered_mission = mission.model_copy(
            update={"waypoints": [points[0], altered_yaw, points[2]]}
        )
        try:
            await asyncio.to_thread(gateway._verify_mission_sync, altered_mission)
        except MissionUploadError as exc:
            if "param4" not in str(exc):
                raise
            print(
                "Specified yaw correctly rejected when stored yaw is unspecified",
                flush=True,
            )
        else:
            raise RuntimeError("Changed yaw was incorrectly accepted")
    finally:
        await gateway.close()


if __name__ == "__main__":
    asyncio.run(main())
