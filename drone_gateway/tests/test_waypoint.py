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
