import hashlib

from app.core.exceptions import MissionValidationError
from app.models import MissionWaypoint

HEADER = "QGC WPL 110"


def render_qgc_wpl(waypoints: list[MissionWaypoint]) -> str:
    ordered = sorted(waypoints, key=lambda waypoint: waypoint.sequence)
    lines = [HEADER]
    for waypoint in ordered:
        lines.append(
            "\t".join(
                (
                    str(waypoint.sequence),
                    str(waypoint.current),
                    str(waypoint.frame),
                    str(waypoint.command),
                    f"{waypoint.param1:.6f}",
                    f"{waypoint.param2:.6f}",
                    f"{waypoint.param3:.6f}",
                    f"{waypoint.param4:.6f}",
                    f"{waypoint.latitude:.7f}",
                    f"{waypoint.longitude:.7f}",
                    f"{waypoint.altitude_m:.3f}",
                    str(waypoint.autocontinue),
                )
            )
        )
    return "\n".join(lines) + "\n"


def parse_qgc_wpl(content: str) -> list[MissionWaypoint]:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines or lines[0] != HEADER:
        raise MissionValidationError("Arquivo não possui cabeçalho QGC WPL 110.")
    waypoints: list[MissionWaypoint] = []
    for line_number, line in enumerate(lines[1:], start=2):
        fields = line.split()
        if len(fields) != 12:
            raise MissionValidationError(
                f"Linha {line_number} deve possuir 12 campos; recebeu {len(fields)}."
            )
        try:
            waypoints.append(
                MissionWaypoint(
                    sequence=int(fields[0]),
                    current=int(fields[1]),
                    frame=int(fields[2]),
                    command=int(fields[3]),
                    param1=float(fields[4]),
                    param2=float(fields[5]),
                    param3=float(fields[6]),
                    param4=float(fields[7]),
                    latitude=float(fields[8]),
                    longitude=float(fields[9]),
                    altitude_m=float(fields[10]),
                    autocontinue=int(fields[11]),
                )
            )
        except ValueError as exc:
            raise MissionValidationError(f"Linha {line_number} inválida.") from exc
    if not waypoints:
        raise MissionValidationError("Missão não possui waypoints.")
    return waypoints


def mission_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
