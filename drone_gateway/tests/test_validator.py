from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.exceptions import MissionValidationError
from app.mission_planner.waypoint import mission_sha256, render_qgc_wpl
from app.missions.validator import validate_claimed_mission
from app.models import AuthorizedMission, MissionStatus, MissionWaypoint


def _waypoints() -> list[MissionWaypoint]:
    origin = (-23.1175, -46.5502)
    destination = (-23.118, -46.551)
    return [
        MissionWaypoint(
            sequence=0,
            current=1,
            command=16,
            latitude=origin[0],
            longitude=origin[1],
            altitude_m=0,
            label="Origem",
        ),
        MissionWaypoint(
            sequence=1,
            command=22,
            latitude=origin[0],
            longitude=origin[1],
            altitude_m=10,
            label="Decolagem",
        ),
        MissionWaypoint(
            sequence=2,
            command=16,
            latitude=destination[0],
            longitude=destination[1],
            altitude_m=10,
            label="Destino",
        ),
        MissionWaypoint(
            sequence=3,
            command=19,
            param1=5,
            latitude=destination[0],
            longitude=destination[1],
            altitude_m=10,
            label="Espera",
        ),
        MissionWaypoint(
            sequence=4,
            command=211,
            latitude=destination[0],
            longitude=destination[1],
            altitude_m=10,
            label="Entrega",
        ),
        MissionWaypoint(
            sequence=5,
            command=16,
            latitude=origin[0],
            longitude=origin[1],
            altitude_m=10,
            label="Retorno",
        ),
        MissionWaypoint(
            sequence=6,
            command=21,
            latitude=origin[0],
            longitude=origin[1],
            altitude_m=0,
            label="Pouso",
        ),
    ]


def _mission(waypoints: list[MissionWaypoint], content: str) -> AuthorizedMission:
    return AuthorizedMission(
        id=uuid4(),
        order_id=uuid4(),
        vehicle_id=uuid4(),
        status=MissionStatus.AUTHORIZED,
        origin_latitude=-23.1175,
        origin_longitude=-46.5502,
        destination_latitude=-23.118,
        destination_longitude=-46.551,
        takeoff_altitude_m=10,
        estimated_distance_m=100,
        mission_sha256=mission_sha256(content),
        version=1,
        waypoints=waypoints,
    )


def test_validator_accepts_canonical_round_trip() -> None:
    waypoints = _waypoints()
    content = render_qgc_wpl(waypoints)

    validate_claimed_mission(_mission(waypoints, content), content, Settings(_env_file=None))


def test_validator_rejects_api_route_that_differs_from_hashed_file() -> None:
    waypoints = _waypoints()
    content = render_qgc_wpl(waypoints)
    changed = list(waypoints)
    changed[2] = changed[2].model_copy(update={"latitude": -23.1179})

    with pytest.raises(MissionValidationError, match="latitude"):
        validate_claimed_mission(_mission(changed, content), content, Settings(_env_file=None))


@pytest.mark.parametrize(
    ("sequence", "update", "message"),
    [
        (4, {"command": 400}, "Comando MAVLink não permitido"),
        (5, {"altitude_m": 50}, "excede a altitude"),
    ],
)
def test_validator_rejects_unsafe_command_or_altitude(
    sequence: int, update: dict[str, int], message: str
) -> None:
    waypoints = _waypoints()
    waypoints[sequence] = waypoints[sequence].model_copy(update=update)
    content = render_qgc_wpl(waypoints)

    with pytest.raises(MissionValidationError, match=message):
        validate_claimed_mission(_mission(waypoints, content), content, Settings(_env_file=None))
