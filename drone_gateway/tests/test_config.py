import pytest

from app.core.config import GatewayRuntime, MavlinkMode, Settings
from app.core.exceptions import ConfigurationError


def test_canonical_mavlink_baud_environment_name(monkeypatch) -> None:
    monkeypatch.setenv("MAVLINK_BAUD", "115200")
    monkeypatch.delenv("MAVLINK_BAUD_RATE", raising=False)

    settings = Settings(_env_file=None)

    assert settings.mavlink_baud_rate == 115200


def test_vehicle_arm_gate_uses_canonical_environment_name_and_is_fail_closed(
    monkeypatch,
) -> None:
    assert not Settings(_env_file=None).allow_vehicle_arm

    monkeypatch.setenv("ALLOW_VEHICLE_ARM", "true")
    monkeypatch.setenv("ALLOW_FLIGHT_COMMANDS", "true")
    monkeypatch.setenv("ALLOW_MISSION_START", "true")

    assert Settings(_env_file=None).allow_vehicle_arm


@pytest.mark.parametrize(
    ("allow_flight_commands", "allow_mission_start"),
    [(False, False), (False, True)],
)
def test_vehicle_arm_gate_requires_flight_gate(
    allow_flight_commands: bool,
    allow_mission_start: bool,
) -> None:
    with pytest.raises(ConfigurationError, match="ALLOW_VEHICLE_ARM=true exige"):
        Settings(
            _env_file=None,
            allow_vehicle_arm=True,
            allow_flight_commands=allow_flight_commands,
            allow_mission_start=allow_mission_start,
        )

    settings = Settings(
        _env_file=None,
        allow_vehicle_arm=True,
        allow_flight_commands=True,
        allow_mission_start=False,
    )
    assert settings.allow_vehicle_arm
    assert not settings.allow_mission_start


def test_legacy_mavlink_baud_rate_name_remains_compatible(monkeypatch) -> None:
    monkeypatch.delenv("MAVLINK_BAUD", raising=False)
    monkeypatch.setenv("MAVLINK_BAUD_RATE", "57600")

    settings = Settings(_env_file=None)

    assert settings.mavlink_baud_rate == 57600


def test_direct_uses_serial_connection_and_safe_defaults() -> None:
    settings = Settings(
        _env_file=None,
        mavlink_mode=MavlinkMode.DIRECT,
        mavlink_connection="COM7",
    )

    assert settings.effective_mavlink_connection == "COM7"
    assert settings.connection_topology == "direct"
    assert settings.mavlink_source_component_id == 190
    assert not settings.real_hardware_acknowledged
    assert not settings.allow_mission_upload
    assert not settings.allow_flight_commands
    assert not settings.allow_mission_start
    assert not settings.allow_vehicle_arm


def test_mission_planner_forward_uses_dedicated_udp_endpoint() -> None:
    settings = Settings(
        _env_file=None,
        mavlink_mode=MavlinkMode.MISSION_PLANNER_FORWARD,
        mavlink_connection="COM7",
        mavlink_forward_connection="udpin:127.0.0.1:14551",
    )

    assert settings.effective_mavlink_connection == "udpin:127.0.0.1:14551"
    assert settings.connection_topology == "mission_planner_forward"
    assert settings.mavlink_baud_rate == 57600


def test_qgroundcontrol_forward_uses_passive_udp_endpoint() -> None:
    settings = Settings(
        _env_file=None,
        autopilot_system="PX4",
        mavlink_mode=MavlinkMode.QGROUNDCONTROL_FORWARD,
        mavlink_connection="udpin:127.0.0.1:14551",
    )
    assert settings.effective_mavlink_connection == "udpin:127.0.0.1:14551"
    assert settings.connection_topology == "qgroundcontrol_forward"
    assert settings.is_hardware_mode


def test_container_qgroundcontrol_forward_only_accepts_loopback_sitl() -> None:
    options = {
        "_env_file": None,
        "autopilot_system": "PX4",
        "gateway_runtime": "container",
        "mavlink_mode": "qgroundcontrol_forward",
        "mavlink_forward_source": "SITL",
        "mavlink_connection": "udpin:127.0.0.1:14558",
    }
    assert Settings(**options).effective_mavlink_connection == "udpin:127.0.0.1:14558"
    with pytest.raises(ConfigurationError, match="hardware"):
        Settings(**{**options, "mavlink_forward_source": "HARDWARE_REAL"})
    with pytest.raises(ConfigurationError, match="hardware"):
        Settings(**{**options, "mavlink_connection": "udpin:0.0.0.0:14558"})
    with pytest.raises(ConfigurationError, match="somente recepção"):
        Settings(**options, allow_telemetry_requests=True)


@pytest.mark.parametrize("mode", [MavlinkMode.QGROUNDCONTROL_FORWARD, MavlinkMode.MAVLINK_ROUTER])
@pytest.mark.parametrize(
    "flag",
    [
        "allow_mission_upload",
        "allow_flight_commands",
        "allow_mission_start",
        "allow_vehicle_arm",
        "allow_telemetry_requests",
    ],
)
def test_qgroundcontrol_forward_rejects_all_send_gates(flag: str, mode: MavlinkMode) -> None:
    with pytest.raises(ConfigurationError, match="somente recepção"):
        Settings(
            _env_file=None,
            mavlink_mode=mode,
            mavlink_connection="udpin:127.0.0.1:14551",
            **{flag: True},
        )


def test_qgroundcontrol_forward_requires_udp_listener() -> None:
    with pytest.raises(ConfigurationError, match="exige conexão udpin"):
        Settings(
            _env_file=None,
            mavlink_mode=MavlinkMode.QGROUNDCONTROL_FORWARD,
            mavlink_connection="COM7",
        )


@pytest.mark.parametrize("endpoint", ["COM7", "udpin:0.0.0.0:14600", "udpout:127.0.0.1:14600"])
def test_mavlink_router_requires_loopback_udp_listener(endpoint: str) -> None:
    with pytest.raises(ConfigurationError, match=r"127\.0\.0\.1"):
        Settings(
            _env_file=None, mavlink_mode=MavlinkMode.MAVLINK_ROUTER, mavlink_connection=endpoint
        )


def test_forward_requires_serial_upstream_and_udpin_endpoint() -> None:
    with pytest.raises(ConfigurationError, match="porta serial upstream"):
        Settings(
            _env_file=None,
            mavlink_mode=MavlinkMode.MISSION_PLANNER_FORWARD,
            mavlink_connection="udp:127.0.0.1:14550",
        )

    with pytest.raises(ConfigurationError, match="udpin"):
        Settings(
            _env_file=None,
            mavlink_mode=MavlinkMode.MISSION_PLANNER_FORWARD,
            mavlink_connection="COM7",
            mavlink_forward_connection="udpout:127.0.0.1:14551",
        )


def test_hardware_mutation_flags_require_explicit_acknowledgement() -> None:
    with pytest.raises(ConfigurationError, match="REAL_HARDWARE_ACKNOWLEDGED"):
        Settings(
            _env_file=None,
            mavlink_mode=MavlinkMode.DIRECT,
            mavlink_connection="COM7",
            allow_mission_upload=True,
        )

    with pytest.raises(ConfigurationError, match="REAL_HARDWARE_ACKNOWLEDGED"):
        Settings(
            _env_file=None,
            mavlink_mode=MavlinkMode.DIRECT,
            mavlink_connection="COM7",
            allow_vehicle_arm=True,
            allow_flight_commands=True,
            allow_mission_start=True,
        )


@pytest.mark.parametrize(
    ("mode", "connection"),
    [
        (MavlinkMode.REAL, "COM7"),
        (MavlinkMode.DIRECT, "COM7"),
        (MavlinkMode.MISSION_PLANNER_FORWARD, "COM7"),
        (MavlinkMode.QGROUNDCONTROL_FORWARD, "udpin:127.0.0.1:14551"),
    ],
)
def test_container_runtime_rejects_hardware_modes(
    mode: MavlinkMode,
    connection: str,
) -> None:
    with pytest.raises(ConfigurationError, match="container Linux"):
        Settings(
            _env_file=None,
            gateway_runtime=GatewayRuntime.CONTAINER,
            mavlink_mode=mode,
            mavlink_connection=connection,
            mavlink_forward_connection="udpin:127.0.0.1:14551",
        )


@pytest.mark.parametrize("mode", [MavlinkMode.SIMULATION, MavlinkMode.SITL])
def test_container_runtime_allows_non_hardware_modes(mode: MavlinkMode) -> None:
    settings = Settings(
        _env_file=None,
        gateway_runtime=GatewayRuntime.CONTAINER,
        mavlink_mode=mode,
        mavlink_connection="udp:0.0.0.0:14550",
    )

    assert settings.gateway_runtime is GatewayRuntime.CONTAINER
    assert settings.mavlink_mode is mode


def test_px4_plan_validation_cannot_enable_upload_on_the_host() -> None:
    with pytest.raises(ConfigurationError, match="somente loopback"):
        Settings(
            _env_file=None,
            autopilot_system="PX4",
            mavlink_mode=MavlinkMode.SITL,
            mavlink_connection="udpin:127.0.0.1:14550",
            gateway_runtime=GatewayRuntime.HOST,
            px4_sitl_plan_validation=True,
            allow_mission_upload=True,
        )
