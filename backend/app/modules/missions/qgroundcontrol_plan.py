"""Draft .plan creation; no review or flight authorization is implied."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import TypedDict

CAMERA_MODE_COMMAND = 530
QGC_REVIEW_EVENT = "QGROUNDCONTROL_PLAN_REVIEW_RECORDED"
DELIVERY_WAYPOINT_HOLD_SECONDS = 5


@dataclass(frozen=True)
class PlanPosition:
    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        if not (math.isfinite(self.latitude) and -90 <= self.latitude <= 90):
            raise ValueError("Latitude inválida")
        if not (math.isfinite(self.longitude) and -180 <= self.longitude <= 180):
            raise ValueError("Longitude inválida")


def create_draft_plan(
    origin: PlanPosition,
    destination: PlanPosition,
    *,
    home_amsl_m: float | None,
    altitude_m: float,
) -> str:
    """Create a draft for human review; home altitude is AMSL, not relative altitude."""
    if home_amsl_m is not None and not math.isfinite(home_amsl_m):
        raise ValueError("Altitude AMSL da origem inválida")
    if not math.isfinite(altitude_m) or altitude_m <= 0:
        raise ValueError("Altitude relativa inválida")

    def item(command: int, number: int, params: list[float | None]) -> dict[str, object]:
        return {
            "type": "SimpleItem",
            "command": command,
            "doJumpId": number,
            "frame": 3 if command != 20 else 2,
            "autoContinue": True,
            "params": params,
            **(
                {"AMSLAltAboveTerrain": None, "Altitude": altitude_m, "AltitudeMode": 1}
                if command != 20
                else {}
            ),
        }

    plan = {
        "fileType": "Plan",
        "groundStation": "QGroundControl",
        "version": 1,
        "geoFence": {"circles": [], "polygons": [], "version": 2},
        "rallyPoints": {"points": [], "version": 2},
        "mission": {
            "version": 2,
            "firmwareType": 12,
            "vehicleType": 2,
            "globalPlanAltitudeMode": 1,
            "cruiseSpeed": 15,
            "hoverSpeed": 5,
            "plannedHomePosition": [origin.latitude, origin.longitude, home_amsl_m],
            "items": [
                item(22, 1, [0, 0, 0, None, origin.latitude, origin.longitude, altitude_m]),
                item(
                    16,
                    2,
                    [
                        DELIVERY_WAYPOINT_HOLD_SECONDS,
                        0,
                        0,
                        None,
                        destination.latitude,
                        destination.longitude,
                        altitude_m,
                    ],
                ),
                # Match the reserved parameters in plans saved by QGroundControl Daily.
                item(20, 3, [0.0] * 7),
            ],
        },
    }
    return json.dumps(plan, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def plan_sha256(content: bytes) -> str:
    """Identify the exact saved artifact, including edits, not a normalized substitute."""
    return hashlib.sha256(content).hexdigest()


@dataclass(frozen=True)
class QGroundControlCandidate:
    """An auditable candidate only; it is not an authorization or vehicle readback."""

    content: str
    sha256: str
    ignored_camera_item: bool


def build_reviewed_candidate(
    reviewed_items: list[ReviewedPlanItem],
    *,
    plan_digest: str,
    mission_version: int,
    mission_digest: str,
) -> QGroundControlCandidate:
    """Bind the reviewed file and mission revision to the route for a camera-free drone."""
    ignored_camera_item = reviewed_items[0]["command"] == CAMERA_MODE_COMMAND
    route_items = reviewed_items[1:] if ignored_camera_item else reviewed_items
    waypoints: list[dict[str, object]] = []
    for sequence, item in enumerate(route_items):
        params = item["params"]
        rtl = item["command"] == 20
        # RTL values are reserved; null and zero have the same defined empty meaning.
        encoded = [0 if value is None else value for value in params] if rtl else params
        waypoints.append(
            {
                "sequence": sequence,
                "command": item["command"],
                "frame": item["frame"],
                "autocontinue": item["autocontinue"],
                "params": encoded,
            }
        )
    artifact = {
        "format": "devcore-px4-mission-candidate-v1",
        "plan_sha256": plan_digest,
        "mission_version": mission_version,
        "mission_sha256": mission_digest,
        "items": waypoints,
    }
    content = json.dumps(artifact, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return QGroundControlCandidate(
        content=content,
        sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        ignored_camera_item=ignored_camera_item,
    )


class ReviewedPlanItem(TypedDict):
    sequence: int
    command: int
    frame: int
    autocontinue: bool
    params: list[int | float | None]


def validate_reviewed_plan(content: str, destination: PlanPosition) -> list[ReviewedPlanItem]:
    """Accept only the supported PX4 mission subset; never infer vehicle upload."""

    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("O plano contém campos duplicados")
            result[key] = value
        return result

    def finite_number(value: object) -> bool:
        if type(value) not in (int, float):
            return False
        try:
            return math.isfinite(value)
        except OverflowError:
            return False

    def reject_constant(_value: str) -> None:
        raise ValueError("O plano contém número inválido")

    try:
        plan = json.loads(content, object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("Arquivo .plan inválido") from exc
    if not isinstance(plan, dict) or plan.get("fileType") != "Plan" or plan.get("version") != 1:
        raise ValueError("Formato de plano QGroundControl inválido")
    mission = plan.get("mission")
    if (
        not isinstance(mission, dict)
        or mission.get("version") != 2
        or mission.get("firmwareType") != 12
    ):
        raise ValueError("O plano deve usar o formato de missão PX4")
    home = mission.get("plannedHomePosition")
    if (
        not isinstance(home, list)
        or len(home) != 3
        or not all(finite_number(v) for v in home[:2])
        or (home[2] is not None and not finite_number(home[2]))
    ):
        raise ValueError("Origem planejada inválida")
    PlanPosition(home[0], home[1])
    items = mission.get("items")
    if not isinstance(items, list) or not 3 <= len(items) <= 100:
        raise ValueError("A missão deve conter Takeoff, waypoints e RTL")
    if any(not isinstance(item, dict) or item.get("type") != "SimpleItem" for item in items):
        raise ValueError("Apenas itens simples são suportados")
    original_items = items
    if items[0].get("command") == CAMERA_MODE_COMMAND:
        camera = items[0]
        camera_params = camera.get("params")
        if (
            camera.get("frame") != 2
            or camera.get("autoContinue") is not True
            or not isinstance(camera_params, list)
            or len(camera_params) != 7
            or not all(finite_number(v) for v in camera_params[:2])
            or not all(v is None for v in camera_params[2:])
        ):
            raise ValueError("Configuração inicial de câmera inválida")
        items = items[1:]
    commands = [item.get("command") for item in items]
    if 20 not in commands:
        if commands[-1] == 21:
            raise ValueError(
                "O plano termina com Land (Pousar). Use Return to Launch (RTL) "
                "após o waypoint do destino."
            )
        raise ValueError("O arquivo não contém Return To Launch (RTL)")
    if (
        len(commands) < 3
        or commands[0] != 22
        or commands[-1] != 20
        or any(c != 16 for c in commands[1:-1])
    ):
        raise ValueError("A sequência deve ser Takeoff, waypoints e RTL")
    for item in items[:-1]:
        params = item.get("params")
        if item.get("frame") != 3 or item.get("autoContinue") is not True:
            raise ValueError("Os pontos devem usar altitude relativa e continuação automática")
        if (
            not isinstance(params, list)
            or len(params) != 7
            or not all(finite_number(v) for v in params[4:])
        ):
            raise ValueError("Coordenadas e altitude dos pontos são obrigatórias")
        if not all(finite_number(v) for v in params[:3]) or not (
            params[3] is None or finite_number(params[3])
        ):
            raise ValueError("Parâmetros dos pontos são inválidos")
        PlanPosition(params[4], params[5])
        if not 0 < params[6] <= 120:
            raise ValueError("Altitude relativa deve estar entre 0 e 120 metros")
        altitude = item.get("Altitude")
        if altitude is not None and (
            not finite_number(altitude) or not math.isclose(altitude, params[6], abs_tol=1e-6)
        ):
            raise ValueError("Altitude exibida diverge da altitude do ponto")
    takeoff_params = items[0]["params"]
    if [round(value, 7) for value in takeoff_params[4:6]] != [
        round(value, 7) for value in home[:2]
    ]:
        raise ValueError("O Home planejado deve coincidir com o ponto de decolagem")
    rtl = items[-1]
    rtl_params = rtl.get("params")
    if (
        rtl.get("frame") != 2
        or rtl.get("autoContinue") is not True
        or not isinstance(rtl_params, list)
        or len(rtl_params) != 7
        or any(
            value is not None and (not finite_number(value) or value != 0) for value in rtl_params
        )
    ):
        raise ValueError("RTL deve usar frame de missão e parâmetros reservados vazios ou zero")
    destination_params = items[-2]["params"]
    if (round(destination_params[4], 7), round(destination_params[5], 7)) != (
        round(destination.latitude, 7),
        round(destination.longitude, 7),
    ):
        raise ValueError("O último waypoint deve corresponder ao destino do pedido")
    # Keep all seven source values, including null yaw and the camera item.
    # This is review evidence, not an executable MAVLink conversion.
    return [
        {
            "sequence": index,
            "command": item["command"],
            "frame": item["frame"],
            "autocontinue": item["autoContinue"],
            "params": item["params"],
        }
        for index, item in enumerate(original_items)
    ]
