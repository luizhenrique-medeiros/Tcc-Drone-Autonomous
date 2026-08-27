"""Passive MAVLink diagnostics; no bytes are sent by this command."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from typing import Any

from app.core.config import MavlinkMode, Settings
from app.core.exceptions import GatewayError
from app.mavlink.ports import list_serial_ports
from app.mavlink.pymavlink_gateway import PymavlinkVehicleGateway


def _configured_serial_port(settings: Settings) -> str | None:
    network_prefixes = ("udp:", "udpin:", "udpout:", "tcp:", "tcpin:", "mcast:")
    if settings.mavlink_mode is MavlinkMode.MISSION_PLANNER_FORWARD:
        candidate = settings.mavlink_connection.strip()
    else:
        candidate = settings.effective_mavlink_connection.strip()
    return None if candidate.lower().startswith(network_prefixes) else candidate


def _base_report(settings: Settings) -> dict[str, Any]:
    serial_port = _configured_serial_port(settings)
    return {
        "mode": settings.mavlink_mode.value,
        "topology": settings.connection_topology,
        "effective_connection": settings.sanitized_connection,
        "serial_port": serial_port,
        "baud": settings.mavlink_baud_rate if serial_port is not None else None,
        "source_system": settings.mavlink_source_system_id,
        "source_component": settings.mavlink_source_component_id,
        "autopilot_system": settings.autopilot_system,
        "receive_only": True,
        "serial_ports": [asdict(port) for port in list_serial_ports()],
        "connection_attempted": False,
        "telemetry_received": False,
        "status": "unavailable",
        "guidance": (
            "Por padrão nenhuma porta é aberta. Use --connect para apenas receber heartbeat "
            "e telemetria. Se a COM estiver ocupada ou com acesso negado, feche o Mission "
            "Planner para direct ou use mission_planner_forward com forwarding UDP."
        ),
    }


async def diagnose(
    settings: Settings,
    *,
    connect: bool,
    observe_seconds: float,
) -> dict[str, Any]:
    report = _base_report(settings)
    if not connect:
        return report

    # The diagnostic is always receive-only, independent of runtime flags.
    safe_settings = settings.model_copy(
        update={
            "allow_mission_upload": False,
            "allow_flight_commands": False,
            "allow_mission_start": False,
            "allow_vehicle_arm": False,
        }
    )
    gateway = PymavlinkVehicleGateway(safe_settings)
    report["connection_attempted"] = True
    try:
        await gateway.connect(passive=True)
        deadline = asyncio.get_running_loop().time() + observe_seconds
        health = await gateway.read_health()
        while asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(min(0.2, max(0.0, deadline - asyncio.get_running_loop().time())))
            health = await gateway.read_health()
        report["telemetry_received"] = health.heartbeat
        report["status"] = (
            f"{health.source.value.lower()}_telemetry" if health.heartbeat else "unavailable"
        )
        report["health"] = health.model_dump(mode="json")
    except GatewayError as exc:
        report["status"] = "unavailable"
        report["error_code"] = exc.code
        report["error"] = str(exc)
    finally:
        await gateway.close()
    return report


def _positive_seconds(value: str) -> float:
    parsed = float(value)
    if not 0 <= parsed <= 60:
        raise argparse.ArgumentTypeError("deve estar entre 0 e 60 segundos")
    return parsed


def _display(value: object) -> str:
    return "indisponível" if value is None else str(value)


def _print_human(report: dict[str, Any]) -> None:
    print(f"Modo/topologia: {report['mode']} / {report['topology']}")
    print(f"Endpoint efetivo: {report['effective_connection']}")
    print(f"Porta serial upstream: {report['serial_port'] or 'não configurada'}")
    print(f"Estado: {report['status']} (receive-only)")
    if error := report.get("error"):
        print(f"Erro: {error}")
    health = report.get("health")
    if isinstance(health, dict):
        print(f"Origem operacional: {_display(health.get('source'))}")
        print(
            "System/component: "
            f"{_display(health.get('mavlink_system_id'))}/"
            f"{_display(health.get('mavlink_component_id'))}"
        )
        print(
            f"Autopilot/version: {report['autopilot_system']}/"
            f"{_display(health.get('autopilot_version'))}"
        )
        print(
            f"Flight mode/armed: {_display(health.get('flight_mode'))}/"
            f"{_display(health.get('armed'))}"
        )
        print(
            f"GPS fix/satélites: {_display(health.get('gps_fix_type'))}/"
            f"{_display(health.get('satellites'))}"
        )
        print(
            "Posição/altitude m: "
            f"{_display(health.get('current_latitude'))}, "
            f"{_display(health.get('current_longitude'))}, "
            f"{_display(health.get('current_altitude_m'))}"
        )
        print(
            "Bateria %/V: "
            f"{_display(health.get('battery_percent'))}/"
            f"{_display(health.get('battery_voltage'))}"
        )
        print(f"EKF: {_display(health.get('ekf_ok'))}")
        print(
            "Home: "
            f"{_display(health.get('origin_latitude'))}, "
            f"{_display(health.get('origin_longitude'))}"
        )
        print(f"Heartbeat age s: {_display(health.get('heartbeat_age_seconds'))}")
    print(str(report["guidance"]))
    ports = report["serial_ports"]
    if not ports:
        print("Nenhuma porta serial encontrada.")
    for port in ports:
        print(f"{port['device']} - {port['description'] or 'sem descrição'}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Lista portas e, somente com --connect, recebe MAVLink passivamente. "
            "Nunca envia requests, heartbeat GCS, missão ou comando."
        )
    )
    parser.add_argument(
        "--connect",
        action="store_true",
        help="Abre o endpoint configurado apenas para recepção e aguarda heartbeat.",
    )
    parser.add_argument(
        "--observe-seconds",
        type=_positive_seconds,
        default=3.0,
        help="Tempo adicional de observação passiva após o heartbeat (0-60).",
    )
    parser.add_argument("--json", action="store_true", help="Emite JSON estruturado.")
    args = parser.parse_args()
    report = asyncio.run(
        diagnose(
            Settings(),
            connect=args.connect,
            observe_seconds=args.observe_seconds,
        )
    )
    failed_connection = args.connect and not report["telemetry_received"]
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)
    if failed_connection:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
