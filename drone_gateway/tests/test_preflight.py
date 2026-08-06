from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.core.config import Settings
from app.mission_planner.waypoint import mission_sha256, render_qgc_wpl
from app.models import (
    AuthorizedMission,
    ClaimResponse,
    MissionStatus,
    MissionWaypoint,
    VehicleHealth,
)
from app.safety.preflight import evaluate_preflight


def build_claim(expiry: datetime) -> ClaimResponse:
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
    mission = AuthorizedMission(
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
    )
    return ClaimResponse(
        mission=mission,
        mission_file=content,
        authorization_id=uuid4(),
        authorization_expires_at=expiry,
    )


def healthy_vehicle() -> VehicleHealth:
    return VehicleHealth(
        connected=True,
        heartbeat=True,
        gps_fix_type=3,
        satellites=14,
        ekf_ok=True,
        battery_percent=80,
        flight_mode="STANDBY",
        armed=False,
        preflight_ok=True,
        rtl_configured=True,
        geofence_enabled=True,
        origin_latitude=-23.1175,
        origin_longitude=-46.5502,
    )


def test_preflight_accepts_healthy_authorized_mission() -> None:
    now = datetime.now(UTC)
    result = evaluate_preflight(
        healthy_vehicle(),
        build_claim(now + timedelta(minutes=2)),
        Settings(_env_file=None),
        now=now,
    )
    assert result.passed


def test_preflight_rejects_expired_authorization_and_low_battery() -> None:
    now = datetime.now(UTC)
    health = healthy_vehicle().model_copy(update={"battery_percent": 10})
    result = evaluate_preflight(
        health,
        build_claim(now - timedelta(seconds=1)),
        Settings(_env_file=None),
        now=now,
    )
    assert not result.passed
    assert {"BATTERY", "AUTHORIZATION_EXPIRY"}.issubset(result.failures)
