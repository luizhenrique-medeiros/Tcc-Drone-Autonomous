from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from app.core.config import MavlinkMode, Settings
from app.mavlink.ports import SerialPortInfo
from app.models import OperationalSource, VehicleHealth
from app.tools import mavlink_diagnose


@pytest.mark.asyncio
async def test_default_diagnostic_only_lists_ports_and_never_opens_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        _env_file=None,
        mavlink_mode=MavlinkMode.MISSION_PLANNER_FORWARD,
        mavlink_connection="COM7",
        mavlink_forward_connection="udpin:127.0.0.1:14551",
    )
    monkeypatch.setattr(
        mavlink_diagnose,
        "list_serial_ports",
        lambda: [
            SerialPortInfo(
                device="COM7",
                description="CP210x",
                manufacturer=None,
                product=None,
                serial_number=None,
                vid=None,
                pid=None,
            )
        ],
    )

    class MustNotInstantiate:
        def __init__(self, settings: Settings) -> None:
            raise AssertionError(f"endpoint was opened: {settings.sanitized_connection}")

    monkeypatch.setattr(mavlink_diagnose, "PymavlinkVehicleGateway", MustNotInstantiate)

    report = await mavlink_diagnose.diagnose(
        settings,
        connect=False,
        observe_seconds=0,
    )

    assert not report["connection_attempted"]
    assert report["status"] == "unavailable"
    assert report["effective_connection"] == "udpin:127.0.0.1:14551"
    assert report["serial_port"] == "COM7"
    assert report["baud"] == 57600


@pytest.mark.asyncio
async def test_connect_diagnostic_forces_passive_flags_and_reports_real_health(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = SimpleNamespace(passive=None, closed=False)

    class PassiveGateway:
        def __init__(self, settings: Settings) -> None:
            assert not settings.allow_mission_upload
            assert not settings.allow_flight_commands
            assert not settings.allow_mission_start

        async def connect(self, *, passive: bool = False) -> None:
            calls.passive = passive

        async def read_health(self) -> VehicleHealth:
            return VehicleHealth(
                source=OperationalSource.SITL,
                connected=True,
                heartbeat=True,
                mavlink_system_id=1,
                mavlink_component_id=1,
                flight_mode="AUTO",
                armed=False,
            )

        async def close(self) -> None:
            calls.closed = True

    monkeypatch.setattr(mavlink_diagnose, "PymavlinkVehicleGateway", PassiveGateway)
    monkeypatch.setattr(mavlink_diagnose, "list_serial_ports", lambda: [])

    report = await mavlink_diagnose.diagnose(
        Settings(_env_file=None, mavlink_mode=MavlinkMode.SITL),
        connect=True,
        observe_seconds=0,
    )

    assert calls.passive is True
    assert calls.closed
    assert report["status"] == "real_telemetry"


def test_human_formatter_prints_unknown_fields_as_unavailable(
    capsys: pytest.CaptureFixture,
) -> None:
    report = {
        "mode": "direct",
        "topology": "direct",
        "effective_connection": "COM7",
        "serial_port": "COM7",
        "status": "real_telemetry",
        "autopilot_system": "ARDUPILOT",
        "guidance": "guidance",
        "serial_ports": [],
        "health": {
            "mavlink_system_id": 1,
            "mavlink_component_id": 1,
            "autopilot_version": None,
            "flight_mode": "AUTO",
            "armed": False,
            "gps_fix_type": None,
            "satellites": None,
            "current_latitude": None,
            "current_longitude": None,
            "current_altitude_m": None,
            "battery_percent": None,
            "battery_voltage": None,
            "ekf_ok": None,
            "origin_latitude": None,
            "origin_longitude": None,
            "heartbeat_age_seconds": 0.4,
        },
    }

    mavlink_diagnose._print_human(report)

    output = capsys.readouterr().out
    assert "System/component: 1/1" in output
    assert "Autopilot/version: ARDUPILOT/indisponível" in output
    assert "GPS fix/satélites: indisponível/indisponível" in output
    assert "Heartbeat age s: 0.4" in output


def test_cli_exits_nonzero_when_connect_does_not_obtain_heartbeat(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    async def unavailable(*args: object, **kwargs: object) -> dict[str, object]:
        return {
            "mode": "direct",
            "topology": "direct",
            "effective_connection": "COM7",
            "serial_port": "COM7",
            "status": "unavailable",
            "autopilot_system": "ARDUPILOT",
            "guidance": "porta ocupada ou sem heartbeat",
            "serial_ports": [],
            "error": "heartbeat indisponível",
        }

    monkeypatch.setattr(mavlink_diagnose, "diagnose", unavailable)
    monkeypatch.setattr(mavlink_diagnose, "Settings", lambda: object())
    monkeypatch.setattr(sys, "argv", ["drone-gateway-diagnose", "--connect"])

    with pytest.raises(SystemExit) as exc_info:
        mavlink_diagnose.main()

    assert exc_info.value.code == 2
    assert "heartbeat indisponível" in capsys.readouterr().out
