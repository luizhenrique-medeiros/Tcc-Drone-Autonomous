import pytest

from app.core.exceptions import MissionValidationError
from app.mission_planner.waypoint import mission_sha256, parse_qgc_wpl, render_qgc_wpl
from app.models import MissionWaypoint


def test_qgc_wpl_roundtrip_is_stable() -> None:
    waypoints = [
        MissionWaypoint(
            sequence=0,
            current=1,
            frame=3,
            command=16,
            latitude=-23.1175,
            longitude=-46.5502,
            altitude_m=10,
            label="origem",
        ),
        MissionWaypoint(
            sequence=1,
            frame=3,
            command=16,
            latitude=-23.118,
            longitude=-46.551,
            altitude_m=10,
            label="destino",
        ),
    ]

    content = render_qgc_wpl(waypoints)
    parsed = parse_qgc_wpl(content)

    assert content.startswith("QGC WPL 110\n")
    assert [item.sequence for item in parsed] == [0, 1]
    assert parsed[1].latitude == -23.118
    assert len(mission_sha256(content)) == 64


def test_legacy_wpl_refuses_unspecified_yaw() -> None:
    waypoint = MissionWaypoint(
        sequence=0, command=16, param4=None, latitude=1, longitude=2, altitude_m=10
    )
    with pytest.raises(MissionValidationError, match="orientação nula"):
        render_qgc_wpl([waypoint])


@pytest.mark.parametrize("invalid", [float("nan"), float("inf")])
def test_json_waypoint_rejects_nonfinite_yaw(invalid: float) -> None:
    with pytest.raises(ValueError):
        MissionWaypoint(
            sequence=0, command=16, param4=invalid, latitude=1, longitude=2, altitude_m=10
        )
