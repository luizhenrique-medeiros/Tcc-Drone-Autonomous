import math

from app.core.config import Settings
from app.core.exceptions import MissionValidationError
from app.core.geo import distance_m
from app.mission_planner.waypoint import mission_sha256, parse_qgc_wpl
from app.models import AuthorizedMission, MissionStatus, MissionWaypoint

ALLOWED_COMMANDS = frozenset({16, 19, 21, 22, 211})
ALLOWED_GLOBAL_FRAMES = frozenset({3})
POSITION_TOLERANCE_M = 2.0
CANONICAL_COMMANDS = (16, 22, 16, 19, 211, 16, 21)


def _close(left: float, right: float, *, absolute_tolerance: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-7, abs_tol=absolute_tolerance)


def _validate_waypoint_equivalence(
    parsed: MissionWaypoint, supplied: MissionWaypoint, sequence: int
) -> None:
    scalar_fields = ("sequence", "command", "frame", "current", "autocontinue")
    for field in scalar_fields:
        if getattr(parsed, field) != getattr(supplied, field):
            raise MissionValidationError(
                f"Waypoint {sequence} diverge no campo {field} entre arquivo e API."
            )
    for field in ("param1", "param2", "param3", "param4"):
        if not _close(getattr(parsed, field), getattr(supplied, field), absolute_tolerance=1e-6):
            raise MissionValidationError(
                f"Waypoint {sequence} diverge no campo {field} entre arquivo e API."
            )
    for field in ("latitude", "longitude"):
        if not _close(getattr(parsed, field), getattr(supplied, field), absolute_tolerance=1e-7):
            raise MissionValidationError(
                f"Waypoint {sequence} diverge no campo {field} entre arquivo e API."
            )
    if not _close(parsed.altitude_m, supplied.altitude_m, absolute_tolerance=1e-3):
        raise MissionValidationError(
            f"Waypoint {sequence} diverge na altitude entre arquivo e API."
        )


def _near(
    waypoint: MissionWaypoint,
    latitude: float,
    longitude: float,
    *,
    tolerance_m: float = POSITION_TOLERANCE_M,
) -> bool:
    return distance_m(waypoint.latitude, waypoint.longitude, latitude, longitude) <= tolerance_m


def validate_claimed_mission(
    mission: AuthorizedMission, mission_file: str, settings: Settings
) -> None:
    if mission.status not in {MissionStatus.AUTHORIZED, MissionStatus.UPLOADING}:
        raise MissionValidationError("Claim não contém missão em estado AUTHORIZED/UPLOADING.")
    calculated_distance = distance_m(
        mission.origin_latitude,
        mission.origin_longitude,
        mission.destination_latitude,
        mission.destination_longitude,
    )
    if calculated_distance > settings.max_mission_distance_m:
        raise MissionValidationError("Distância da missão excede o limite local do gateway.")
    declared_tolerance = max(10.0, calculated_distance * 0.05)
    if not _close(
        mission.estimated_distance_m,
        calculated_distance,
        absolute_tolerance=declared_tolerance,
    ):
        raise MissionValidationError("Distância declarada diverge das coordenadas da missão.")
    if mission.takeoff_altitude_m > settings.default_takeoff_altitude_m:
        raise MissionValidationError("Altitude excede o limite configurado no gateway.")
    parsed = parse_qgc_wpl(mission_file)
    supplied = sorted(mission.waypoints, key=lambda item: item.sequence)
    if len(parsed) != len(supplied):
        raise MissionValidationError("Contagem do arquivo difere dos waypoints da API.")
    if mission_sha256(mission_file) != mission.mission_sha256:
        raise MissionValidationError("SHA-256 da missão não corresponde ao arquivo recebido.")
    expected_sequences = list(range(len(supplied)))
    if [item.sequence for item in supplied] != expected_sequences:
        raise MissionValidationError("Sequência deve ser contígua e iniciar em zero.")
    if [item.sequence for item in parsed] != expected_sequences:
        raise MissionValidationError("Sequência do arquivo não é canônica.")
    for sequence, (parsed_waypoint, supplied_waypoint) in enumerate(
        zip(parsed, supplied, strict=True)
    ):
        _validate_waypoint_equivalence(parsed_waypoint, supplied_waypoint, sequence)

    for item in supplied:
        if item.command not in ALLOWED_COMMANDS:
            raise MissionValidationError(f"Comando MAVLink não permitido: {item.command}.")
        if item.frame not in ALLOWED_GLOBAL_FRAMES:
            raise MissionValidationError(f"Frame MAVLink não permitido: {item.frame}.")
        if item.altitude_m > settings.default_takeoff_altitude_m + 1e-3:
            raise MissionValidationError(
                f"Waypoint {item.sequence} excede a altitude local configurada."
            )
        if (
            distance_m(
                mission.origin_latitude,
                mission.origin_longitude,
                item.latitude,
                item.longitude,
            )
            > settings.max_mission_distance_m
        ):
            raise MissionValidationError(
                f"Waypoint {item.sequence} excede o raio operacional configurado."
            )

    if len(supplied) != len(CANONICAL_COMMANDS):
        raise MissionValidationError(
            "Missão deve conter exatamente os sete waypoints da rota canônica."
        )
    if tuple(item.command for item in supplied) != CANONICAL_COMMANDS:
        raise MissionValidationError("Comandos não seguem a rota canônica autorizada.")
    if supplied[0].current != 1 or any(item.current != 0 for item in supplied[1:]):
        raise MissionValidationError("Somente o waypoint inicial deve estar marcado como current.")

    origin_indexes = (0, 1, 5, 6)
    destination_indexes = (2, 3, 4)
    if any(
        not _near(supplied[index], mission.origin_latitude, mission.origin_longitude)
        for index in origin_indexes
    ):
        raise MissionValidationError("Waypoints de origem/retorno divergem da origem declarada.")
    if any(
        not _near(supplied[index], mission.destination_latitude, mission.destination_longitude)
        for index in destination_indexes
    ):
        raise MissionValidationError("Waypoints de entrega divergem do destino declarado.")

    expected_altitudes = (
        0.0,
        mission.takeoff_altitude_m,
        mission.takeoff_altitude_m,
        mission.takeoff_altitude_m,
        mission.takeoff_altitude_m,
        mission.takeoff_altitude_m,
        0.0,
    )
    for item, expected_altitude in zip(supplied, expected_altitudes, strict=True):
        if not _close(item.altitude_m, expected_altitude, absolute_tolerance=1e-3):
            raise MissionValidationError(
                f"Waypoint {item.sequence} possui altitude diferente da rota canônica."
            )
        if item.autocontinue != 1:
            raise MissionValidationError(
                f"Waypoint {item.sequence} deve possuir autocontinue habilitado."
            )

    for index, item in enumerate(supplied):
        expected_param1 = 5.0 if index == 3 else 0.0
        if not _close(item.param1, expected_param1, absolute_tolerance=1e-6) or any(
            not _close(value, 0.0, absolute_tolerance=1e-6)
            for value in (item.param2, item.param3, item.param4)
        ):
            raise MissionValidationError(
                f"Waypoint {item.sequence} possui parâmetros fora da rota canônica."
            )
