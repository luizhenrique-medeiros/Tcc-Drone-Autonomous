"""Loopback-only MAVLink transport test; no simulator or hardware is contacted."""

import asyncio
import socket

import pytest
from pymavlink import mavutil

from app.core.config import MavlinkMode, Settings
from app.main import runtime_observation_only
from app.mavlink.pymavlink_gateway import PymavlinkVehicleGateway
from app.models import OperationalSource


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", [MavlinkMode.QGROUNDCONTROL_FORWARD, MavlinkMode.MAVLINK_ROUTER])
async def test_px4_forward_receives_mavlink_on_loopback_without_sending(mode: MavlinkMode) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]

    settings = Settings(
        _env_file=None,
        autopilot_system="PX4",
        mavlink_mode=mode,
        mavlink_connection=f"udpin:127.0.0.1:{port}",
        heartbeat_timeout_seconds=2,
    )
    gateway = PymavlinkVehicleGateway(settings)
    encoder = mavutil.mavlink.MAVLink(None, srcSystem=42, srcComponent=1)
    packet = encoder.heartbeat_encode(2, 12, 0, 0, 4, 3).pack(encoder)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
        sender.bind(("127.0.0.1", 0))
        sender.setblocking(False)
        connect_task = asyncio.create_task(
            gateway.connect(passive=runtime_observation_only(settings))
        )
        try:
            for _ in range(30):
                if gateway._connection is not None or connect_task.done():
                    break
                await asyncio.sleep(0.01)
            assert gateway._connection is not None
            for _ in range(30):
                sender.sendto(packet, ("127.0.0.1", port))
                if connect_task.done():
                    break
                await asyncio.sleep(0.03)
            await connect_task
            health = await gateway.read_health()
            assert health.connected and health.heartbeat
            assert health.mavlink_system_id == 42
            assert health.mavlink_component_id == 1
            assert health.connection_topology == mode.value
            assert health.source is OperationalSource.UNKNOWN
            assert health.serial_port is None
            assert health.current_ground_speed_m_s is None
            assert health.battery_percent is None
            position = encoder.global_position_int_encode(
                0, -231170000, -465500000, 710000, 10000, 300, 400, 0, 9000
            )
            sender.sendto(position.pack(encoder), ("127.0.0.1", port))
            for _ in range(30):
                health = await gateway.read_health()
                if health.current_ground_speed_m_s is not None:
                    break
                await asyncio.sleep(0.01)
            assert health.current_latitude == pytest.approx(-23.117)
            assert health.current_altitude_m == 10
            assert health.current_ground_speed_m_s == 5
            assert health.battery_percent is None
            assert health.px4_flight is not None
            assert health.px4_flight.position_at is not None
            assert health.px4_flight.landed_state is None
            assert health.px4_flight.sequence is None
            extended = encoder.extended_sys_state_encode(0, 2)
            current = encoder.mission_current_encode(1)
            reached = encoder.mission_item_reached_encode(1)
            for message in (extended, current, reached):
                sender.sendto(message.pack(encoder), ("127.0.0.1", port))
            for _ in range(30):
                health = await gateway.read_health()
                if health.px4_flight and health.px4_flight.sequence == 1:
                    break
                await asyncio.sleep(0.01)
            assert health.px4_flight is not None
            assert health.px4_flight.landed_state == 2
            assert health.px4_flight.sequence == 1
            assert health.px4_flight.mission_at is not None
            assert [
                event.metadata.get("system_id")
                for event in await gateway.drain_events()
                if event.event_type == "MAVLINK_MISSION_ITEM_REACHED"
            ] == [42]
            with pytest.raises(BlockingIOError):
                sender.recvfrom(4096)
        finally:
            if not connect_task.done():
                connect_task.cancel()
            await gateway.close()


def test_qgroundcontrol_source_requires_explicit_operator_declaration() -> None:
    settings = Settings(
        _env_file=None,
        mavlink_mode=MavlinkMode.QGROUNDCONTROL_FORWARD,
        mavlink_connection="udpin:127.0.0.1:14445",
        mavlink_forward_source="HARDWARE_REAL",
    )
    assert (
        PymavlinkVehicleGateway(settings)._operational_source() is OperationalSource.HARDWARE_REAL
    )


def test_router_source_requires_explicit_operator_declaration() -> None:
    settings = Settings(
        _env_file=None,
        autopilot_system="PX4",
        mavlink_mode=MavlinkMode.MAVLINK_ROUTER,
        mavlink_connection="udpin:127.0.0.1:14600",
    )
    assert PymavlinkVehicleGateway(settings)._operational_source() is OperationalSource.UNKNOWN
    declared = Settings(
        _env_file=None,
        autopilot_system="PX4",
        mavlink_mode=MavlinkMode.MAVLINK_ROUTER,
        mavlink_connection="udpin:127.0.0.1:14600",
        mavlink_forward_source="HARDWARE_REAL",
    )
    assert (
        PymavlinkVehicleGateway(declared)._operational_source() is OperationalSource.HARDWARE_REAL
    )
