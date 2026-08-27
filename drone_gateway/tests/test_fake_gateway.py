from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.exceptions import MissionUploadError, UnsafeOperationError
from app.mavlink.fake_gateway import FakeVehicleGateway
from app.mission_planner.waypoint import mission_sha256, render_qgc_wpl
from app.models import AuthorizedMission, MissionStatus, MissionWaypoint


def build_mission() -> tuple[AuthorizedMission, str]:
    waypoints = [
        MissionWaypoint(
            sequence=0,
            command=16,
            latitude=-23.1175,
            longitude=-46.5502,
            altitude_m=10,
        )
    ]
    content = render_qgc_wpl(waypoints)
    return (
        AuthorizedMission(
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
        ),
        content,
    )


@pytest.mark.asyncio
async def test_fake_upload_is_idempotent_for_same_hash() -> None:
    gateway = FakeVehicleGateway(Settings(_env_file=None, allow_mission_upload=True))
    mission, content = build_mission()
    await gateway.connect()

    first = await gateway.upload_mission(mission, content)
    second = await gateway.upload_mission(mission, content)

    assert first.acknowledged and second.acknowledged


@pytest.mark.asyncio
async def test_fake_upload_rejects_hash_change_for_same_mission() -> None:
    gateway = FakeVehicleGateway(Settings(_env_file=None, allow_mission_upload=True))
    mission, content = build_mission()
    await gateway.connect()
    await gateway.upload_mission(mission, content)
    changed = mission.model_copy(update={"mission_sha256": "a" * 64})

    with pytest.raises(MissionUploadError):
        await gateway.upload_mission(changed, content)


@pytest.mark.asyncio
async def test_fake_arm_is_explicitly_gated_and_only_changes_simulated_state() -> None:
    disabled = FakeVehicleGateway(Settings(_env_file=None))
    await disabled.connect()

    with pytest.raises(UnsafeOperationError, match="ALLOW_VEHICLE_ARM"):
        await disabled.arm_vehicle()

    enabled = FakeVehicleGateway(
        Settings(
            _env_file=None,
            allow_vehicle_arm=True,
            allow_flight_commands=True,
            allow_mission_start=True,
        )
    )
    await enabled.connect()
    before = await enabled.read_health()
    await enabled.arm_vehicle()
    after = await enabled.read_health()

    assert before.vehicle_arm_enabled
    assert before.armed is False
    assert before.flight_mode == "STABILIZE"
    assert after.armed is True
